"""Small, convention-based analyzers that enrich RepositoryModel."""
from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from models.models import RepositoryModel


class Analyzer(Protocol):
    """Interface implemented by repository-specific model enrichers."""

    def supports(self, model: RepositoryModel) -> bool: ...

    def analyze(self, model: RepositoryModel) -> None: ...


def _file_names(model: RepositoryModel) -> set[str]:
    return {item.path.rsplit("/", 1)[-1].lower() for item in model.files}


def _has_file(model: RepositoryModel, *names: str) -> bool:
    return bool(_file_names(model) & {name.lower() for name in names})


def _has_path(model: RepositoryModel, *paths: str) -> bool:
    known = {item.path.strip("/").lower() for item in model.files}
    return bool(known & {path.strip("/").lower() for path in paths})


def _has_directory(model: RepositoryModel, *paths: str) -> bool:
    known = {path.strip("/").lower() for path in model.directories}
    return bool(known & {path.strip("/").lower() for path in paths})


def _has_path_part(model: RepositoryModel, *names: str) -> bool:
    wanted = {name.lower() for name in names}
    return any(
        wanted & {part.lower() for part in path.split("/") if part}
        for path in model.directories
    )


def _read_manifest_text(model: RepositoryModel, names: set[str]) -> str:
    if not model.root_path:
        return ""
    text: list[str] = []
    for item in model.files:
        if item.path.rsplit("/", 1)[-1].lower() not in names:
            continue
        try:
            text.append((Path(model.root_path) / item.path).read_text(
                encoding="utf-8", errors="replace"
            )[:200_000].lower())
        except OSError:
            continue
    return "\n".join(text)


def _add_pattern(model: RepositoryModel, pattern: str) -> None:
    if pattern not in model.detected_patterns:
        model.detected_patterns.append(pattern)


def _add_framework(model: RepositoryModel, framework: str) -> None:
    if framework not in model.frameworks:
        model.frameworks.append(framework)


def _dependency_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _mark_dependencies(
    model: RepositoryModel, names: set[str], category: str, *, prefixes: bool = False
) -> None:
    for dependency in model.dependencies:
        name = _dependency_name(dependency.name)
        if name in names or (prefixes and any(name.startswith(prefix) for prefix in names)):
            dependency.category = category


class GenericAnalyzer:
    """Detect repository-wide structure and classify dependencies by scope."""

    def supports(self, model: RepositoryModel) -> bool:
        return isinstance(model, RepositoryModel)

    def analyze(self, model: RepositoryModel) -> None:
        for dependency in model.dependencies:
            if dependency.category != "unclassified":
                continue
            if dependency.scope == "build":
                dependency.category = "build-tool"
            elif dependency.scope == "development":
                dependency.category = "development"
            elif dependency.scope.startswith("optional"):
                dependency.category = "optional"
            elif dependency.scope == "peer":
                dependency.category = "peer"
            else:
                dependency.category = "library"

        for name, pattern in (
            ("src", "structure:src"),
            ("tests", "structure:tests"),
            ("test", "structure:tests"),
            ("docs", "structure:docs"),
            ("packages", "structure:packages"),
            ("app", "structure:app"),
        ):
            if _has_path_part(model, name):
                _add_pattern(model, pattern)

        for names, pattern in (
            ({"readme.md", "readme.rst", "readme.txt", "readme"}, "convention:readme"),
            ({"contributing.md", "contributing.rst"}, "convention:contributing"),
            ({"makefile"}, "convention:makefile"),
            ({".editorconfig"}, "convention:editorconfig"),
            ({"env.example", ".env.example"}, "convention:env-example"),
        ):
            if _file_names(model) & names:
                _add_pattern(model, pattern)

        dependency_names = {
            _dependency_name(dependency.name) for dependency in model.dependencies
        }
        java_manifest_text = _read_manifest_text(
            model, {"pom.xml", "build.gradle", "build.gradle.kts"}
        )
        if (
            any("spring-boot" in name or "springframework" in name for name in dependency_names)
            or "spring-boot" in java_manifest_text
            or "springframework" in java_manifest_text
        ):
            _add_framework(model, "Spring Boot")
            _mark_dependencies(
                model,
                {name for name in dependency_names if "spring" in name},
                "framework",
            )
        if any(name.endswith(".csproj") for name in _file_names(model)):
            _add_framework(model, ".NET")


class NodeJsAnalyzer:
    """Detect Node.js frameworks, dependency roles, and common project layouts."""

    def supports(self, model: RepositoryModel) -> bool:
        return _has_file(model, "package.json") or bool(
            {"JavaScript", "TypeScript"} & set(model.languages)
        )

    def analyze(self, model: RepositoryModel) -> None:
        frameworks = {
            "next": "Next.js",
            "react": "React",
            "express": "Express",
            "vue": "Vue",
            "@angular/core": "Angular",
            "svelte": "Svelte",
        }
        for dependency in model.dependencies:
            name = _dependency_name(dependency.name)
            framework = frameworks.get(name)
            if name == "nestjs" or name.startswith("@nestjs/"):
                framework = "NestJS"
            if framework:
                dependency.category = "framework"
                _add_framework(model, framework)

        _mark_dependencies(
            model,
            {"jest", "vitest", "mocha", "playwright", "@playwright/test", "cypress"},
            "testing",
        )
        _mark_dependencies(
            model,
            {"typescript", "eslint", "prettier", "webpack", "vite"},
            "tooling",
        )

        if _has_file(model, "package-lock.json"):
            _add_pattern(model, "node:npm-lockfile")
        if _has_file(model, "yarn.lock"):
            _add_pattern(model, "node:yarn-lockfile")
        if _has_file(model, "pnpm-lock.yaml"):
            _add_pattern(model, "node:pnpm-lockfile")

        if "Next.js" in model.frameworks:
            if _has_directory(model, "app", "src/app"):
                _add_pattern(model, "next:app-router")
            if _has_directory(model, "pages", "src/pages"):
                _add_pattern(model, "next:pages-router")


class PythonAnalyzer:
    """Detect Python frameworks, dependency roles, and package layouts."""

    def supports(self, model: RepositoryModel) -> bool:
        return "Python" in model.languages or _has_file(
            model, "pyproject.toml", "requirements.txt", "requirements-dev.txt",
            "setup.py", "pipfile", "manage.py",
        )

    def analyze(self, model: RepositoryModel) -> None:
        framework_dependencies = {
            "django": "Django",
            "flask": "Flask",
            "fastapi": "FastAPI",
        }
        python_manifest_text = _read_manifest_text(
            model,
            {"pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.py", "pipfile"},
        )
        has_django_file = _has_file(model, "manage.py")
        if has_django_file:
            _add_framework(model, "Django")
            _add_pattern(model, "django:manage-py")

        for dependency_name, framework in framework_dependencies.items():
            if dependency_name in python_manifest_text:
                _add_framework(model, framework)
        for dependency in model.dependencies:
            framework = framework_dependencies.get(_dependency_name(dependency.name))
            if framework:
                dependency.category = "framework"
                _add_framework(model, framework)

        _mark_dependencies(
            model,
            {"pytest", "coverage", "tox", "nox"},
            "testing",
        )
        _mark_dependencies(
            model,
            {"ruff", "mypy", "black", "isort", "flake8", "pylint"},
            "tooling",
        )

        if any(
            item.language == "Python" and item.path.startswith("src/")
            for item in model.files
        ):
            _add_pattern(model, "python:src-layout")
        if _has_file(model, "__init__.py"):
            _add_pattern(model, "python:package-layout")


class PhpAnalyzer:
    """Detect PHP frameworks, dependency roles, and common layouts."""

    def supports(self, model: RepositoryModel) -> bool:
        return "PHP" in model.languages or _has_file(model, "composer.json")

    def analyze(self, model: RepositoryModel) -> None:
        has_laravel = _has_file(model, "artisan")
        has_symfony = _has_path(model, "bin/console")
        has_magento = False
        for dependency in model.dependencies:
            name = _dependency_name(dependency.name)
            if name == "laravel/framework":
                dependency.category = "framework"
                has_laravel = True
            elif name.startswith("symfony/"):
                dependency.category = "framework"
                has_symfony = True
            elif name.startswith("magento/"):
                dependency.category = "framework"
                has_magento = True
            elif name in {"phpunit/phpunit"}:
                dependency.category = "testing"
            elif name in {"phpstan/phpstan", "friendsofphp/php-cs-fixer"}:
                dependency.category = "tooling"

        if has_laravel:
            _add_framework(model, "Laravel")
            _add_pattern(model, "laravel:artisan")
            if all(_has_directory(model, path) for path in ("app", "routes", "config")):
                _add_pattern(model, "laravel:directory-layout")
        if has_symfony:
            _add_framework(model, "Symfony")
            if all(_has_directory(model, path) for path in ("src", "config", "templates")):
                _add_pattern(model, "symfony:directory-layout")
        if has_magento:
            _add_framework(model, "Magento")
        if _has_file(model, "composer.json"):
            _add_pattern(model, "php:composer")


DEFAULT_ANALYZERS: tuple[Analyzer, ...] = (
    GenericAnalyzer(),
    NodeJsAnalyzer(),
    PythonAnalyzer(),
    PhpAnalyzer(),
)


def select_analyzers(
    model: RepositoryModel,
    analyzers: Sequence[Analyzer] = DEFAULT_ANALYZERS,
) -> list[Analyzer]:
    """Return analyzers applicable to the scanned repository, in pipeline order."""
    return [analyzer for analyzer in analyzers if analyzer.supports(model)]


def enrich_repository_model(
    model: RepositoryModel,
    analyzers: Sequence[Analyzer] = DEFAULT_ANALYZERS,
) -> RepositoryModel:
    """Run applicable analyzers in order and return the enriched model."""
    for analyzer in select_analyzers(model, analyzers):
        analyzer.analyze(model)
    return model
