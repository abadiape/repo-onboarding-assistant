"""Classify repository areas and aggregate dependency declarations."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath

from models import Dependency, RepositoryModel


_IGNORED = {
    ".git", ".hg", ".svn", "__pycache__", ".pytest_cache", ".venv", "venv",
    ".cache", ".ruff_cache", ".mypy_cache", ".tox", ".nox", ".next",
    "generated", "cache", "caches", "build", "dist", "target", "coverage",
    "tmp", "temp", "temporary", ".idea", ".vscode",
}
_VENDOR = {"vendor", "node_modules", "third_party", "third-party", "thirdparty", "external"}
_INFRASTRUCTURE = {
    "config", "configs", "configuration", "infra", "infrastructure", "deployment",
    "deploy", "terraform", "k8s", "kubernetes", "docker", ".github", ".circleci",
}
_SUPPORTING = {"test", "tests", "docs", "examples", "example"}


def classify_path(path: str) -> tuple[str, str]:
    """Return a relevance level and origin inferred from path conventions."""
    parts = [part.lower() for part in PurePosixPath(path.replace("\\", "/")).parts]
    if set(parts) & _IGNORED:
        return "ignored", "generated"
    if set(parts) & _VENDOR:
        return "low", "vendor"
    if set(parts) & _INFRASTRUCTURE:
        return "medium", "infrastructure"
    if set(parts) & _SUPPORTING:
        return "medium", "supporting"
    return "high", "application"


@dataclass
class RepositoryArea:
    name: str
    path: str
    kind: str


@dataclass
class DependencyGroup:
    name: str
    packages: list[str] = field(default_factory=list)
    origin: str = "dependency"


@dataclass
class RepositoryRelevance:
    paths: dict[str, list[str]] = field(default_factory=dict)
    origins: dict[str, list[str]] = field(default_factory=dict)
    areas: list[RepositoryArea] = field(default_factory=list)
    dependency_groups: list[DependencyGroup] = field(default_factory=list)


def _areas(model: RepositoryModel) -> list[RepositoryArea]:
    directories = set(model.directories)
    workspace_roots = set()
    manifests = {
        "package.json", "composer.json", "pyproject.toml", "pom.xml", "go.mod",
        "Cargo.toml", "build.gradle", "build.gradle.kts", "Dockerfile",
    }
    for item in model.files:
        if classify_path(item.path)[0] != "high":
            continue
        parts = item.path.split("/")
        if len(parts) >= 3 and parts[0] in {"packages", "apps", "services"} and (
            parts[-1] in manifests or parts[-1].endswith(".csproj")
        ):
            workspace_roots.add("/".join(parts[:2]))
    areas: dict[str, RepositoryArea] = {}
    for path in sorted(directories):
        if classify_path(path)[0] != "high":
            continue
        parts = path.split("/")
        if len(parts) == 4 and parts[:2] == ["app", "code"]:
            areas[path] = RepositoryArea(parts[-1], path, "custom module")
        elif len(parts) == 5 and parts[:2] == ["app", "design"]:
            areas[path] = RepositoryArea(parts[-1], path, "theme")
        elif len(parts) == 2 and parts[0] in {"packages", "apps", "services"}:
            if path in workspace_roots:
                areas[path] = RepositoryArea(parts[-1], path, "workspace module")
    children: dict[str, set[str]] = {}
    for path in directories:
        parent, _, name = path.rpartition("/")
        children.setdefault(parent, set()).add(name.lower())
    for path, names in children.items():
        if path and path.lower() not in {"src", "app", "lib", "source"} and classify_path(path)[0] == "high" and len(names & {
            "controller", "controllers", "service", "services", "domain", "repository", "repositories"
        }) >= 2:
            areas.setdefault(path, RepositoryArea(path.split("/")[-1], path, "business area"))
    return list(areas.values())


def aggregate_dependencies(
    dependencies: list[Dependency], frameworks: list[str] | None = None
) -> list[DependencyGroup]:
    """Group distinct package names by namespace; declarations may occur in multiple manifests."""
    packages = {
        dependency.name.casefold(): dependency.name for dependency in dependencies
        if classify_path(dependency.source)[0] not in {"low", "ignored"}
    }
    framework_names = {
        framework.casefold().split()[0].replace(".js", "")
        for framework in frameworks or []
        if framework.split()
    }
    framework_packages = {
        dependency.name.casefold() for dependency in dependencies if dependency.category == "framework"
    }

    def is_framework(namespace: str, names: list[str]) -> bool:
        return any(framework in namespace.casefold() for framework in framework_names) or any(
            package.casefold() in framework_packages for package in names
        )

    grouped: dict[str, list[str]] = {}
    for name in sorted(packages.values(), key=str.casefold):
        if "/" in name:
            namespace = name.split("/", 1)[0]
        elif ":" in name:
            namespace = name.split(":", 1)[0]
        else:
            namespace = "Other"
        grouped.setdefault(namespace, []).append(name)
    other = grouped.pop("Other", [])
    for namespace in list(grouped):
        if len(grouped[namespace]) == 1 and not is_framework(namespace, grouped[namespace]):
            other.extend(grouped.pop(namespace))
    groups = sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0].casefold()))
    for _, names in groups[11:]:
        other.extend(names)
    result = [
        DependencyGroup(
            f"{name} packages",
            names,
            "framework" if is_framework(name, names) else "dependency",
        )
        for name, names in groups[:11]
    ]
    other_framework = [name for name in other if name.casefold() in framework_packages or name.casefold() in framework_names]
    other = [name for name in other if name not in other_framework]
    if other_framework:
        result.append(DependencyGroup("Framework dependencies", sorted(other_framework, key=str.casefold), "framework"))
    if other:
        result.append(DependencyGroup("Other dependencies", sorted(other, key=str.casefold)))
    return result


def analyze_relevance(model: RepositoryModel) -> RepositoryRelevance:
    paths: dict[str, list[str]] = {"high": [], "medium": [], "low": [], "ignored": []}
    origins: dict[str, list[str]] = {
        "application": [], "infrastructure": [], "supporting": [], "vendor": [], "generated": [],
    }
    for path in sorted(set(model.directories)):
        level, origin = classify_path(path)
        paths[level].append(path)
        origins[origin].append(path)
    return RepositoryRelevance(
        paths=paths,
        origins=origins,
        areas=_areas(model),
        dependency_groups=aggregate_dependencies([*model.dependencies, *model.locked_dependencies], model.frameworks),
    )


def relevant_model(model: RepositoryModel) -> RepositoryModel:
    """Exclude vendor and generated facts from architecture inference, not the inventory."""
    keep = lambda path: classify_path(path)[0] not in {"low", "ignored"}
    return replace(
        model,
        files=[item for item in model.files if keep(item.path)],
        directories=[path for path in model.directories if keep(path)],
        dependencies=[item for item in model.dependencies if keep(item.source)],
        entry_points=[path for path in model.entry_points if keep(path)],
        onboarding_docs=[path for path in model.onboarding_docs if keep(path)],
        important_files=[path for path in model.important_files if keep(path)],
        setup_guides=[path for path in model.setup_guides if keep(path)],
        top_level_directories=[path for path in model.top_level_directories if keep(path)],
    )
