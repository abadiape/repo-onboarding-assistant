"""Architecture components."""
from __future__ import annotations

import posixpath
import re
from pathlib import Path

from analyzers.architecture_concepts import (
    _concept_for,
    _concept_for_class,
    _concept_for_module,
    _framework_key,
)
from analyzers.architecture_evidence import (
    _IGNORED_AREAS,
    _parts,
    _public_imports,
    _source_code_lines,
)
from models.architecture_model import ArchitectureComponent
from models.models import RepositoryModel

_CLASS_DECLARATION = re.compile(
    r"^\s*(?:(?:export|default|public|private|internal|abstract|final|sealed|static|data|open|pub|partial)\s+)*(?:class|interface|struct|record|trait|enum|type)\s+([A-Z][A-Za-z0-9_]*)",
    re.MULTILINE,
)


def _discover_components(
    model: RepositoryModel, source_files: dict[str, str] | None = None, *, include_features: bool = True
) -> list[ArchitectureComponent]:
    framework = _framework_key(model)
    evidence: dict[str, set[str]] = {}
    definitions: dict[str, tuple[str, str, str, str]] = {}
    path_parts = {part for path in model.directories for part in _parts(path)}
    runtime_layout = bool(path_parts & {"runtime", "registries", "registry", "plugins", "skills", "artifacts"})

    for directory in model.directories:
        parts = _parts(directory)
        if not parts or set(parts) & _IGNORED_AREAS:
            continue
        for index, part in enumerate(parts):
            concept = _concept_for(part, framework, runtime_layout)
            if concept:
                name, component_type, subsystem, description = concept
                definitions[name] = (component_type, subsystem, description, part)
                evidence.setdefault(name, set()).add("/".join(directory.split("/")[:index + 1]))

    directories = set(model.directories)
    children_by_parent: dict[str, set[str]] = {}
    for directory in directories:
        parent, _, child = directory.rpartition("/")
        if parent:
            children_by_parent.setdefault(parent, set()).add(child.lower())
    for directory in sorted(directories) if include_features else []:
        parts = _parts(directory)
        if not parts or set(parts) & _IGNORED_AREAS:
            continue
        if _concept_for(parts[-1], framework, runtime_layout):
            continue
        children = children_by_parent.get(directory, set())
        layers = {"controller", "controllers", "service", "services", "repository", "repositories", "domain"}
        if len(children & layers) < 2:
            continue
        name = parts[-1].replace("_", " ").title()
        definitions[name] = (
            "feature", "Features", f"Groups the {name.lower()} application functionality.", parts[-1]
        )
        evidence.setdefault(name, set()).add(directory)

    for path, content in (source_files or {}).items():
        if not any(file.path == path and file.kind == "source" for file in model.files):
            continue
        module_concept = _concept_for_module(Path(path).stem, framework)
        if module_concept:
            name, component_type, subsystem, description = module_concept
            definitions[name] = (component_type, subsystem, description, Path(path).stem)
            evidence.setdefault(name, set()).add(path)
        source_lines = _source_code_lines(content)
        code = "\n".join(line for _, line in source_lines)
        for class_name in _CLASS_DECLARATION.findall(code):
            concept = _concept_for_class(class_name, framework)
            if concept:
                name, component_type, subsystem, description = concept
                definitions[name] = (component_type, subsystem, description, class_name)
                evidence.setdefault(name, set()).add(path)

    source_paths = {file.path for file in model.files if file.kind == "source"}
    for path, content in (source_files or {}).items():
        if path not in source_paths:
            continue
        for _, import_path in _public_imports(path, content):
            targets = _import_candidates(import_path, path, source_paths)
            if len(targets) != 1:
                continue
            target = targets[0]
            if any(
                target == location or target.startswith(location.rstrip("/") + "/")
                for locations in evidence.values() for location in locations
            ):
                continue
            stem = Path(target).stem
            if stem in {"__init__", "index", "lib"}:
                stem = Path(target).parent.name
            name = stem.replace("_", " ").replace("-", " ").title()
            if name:
                definitions[name] = ("module", "Application", f"Provides the public {name} functionality.", stem)
                evidence.setdefault(name, set()).add(target)

    if not evidence and model.entry_points:
        evidence["Application Entry Point"] = set(model.entry_points[:3])
        definitions["Application Entry Point"] = (
            "entry_point", "Application", "Starts or exposes the application.", "entry"
        )

    ids_by_name = {
        name: "component_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        for name in evidence
    }
    return [
        ArchitectureComponent(
            id=ids_by_name[name],
            name=name,
            type=definitions[name][0],
            description=definitions[name][2],
            responsibilities=[definitions[name][2]],
            evidence=sorted(evidence[name]),
            locations=sorted(evidence[name]),
        )
        for name in sorted(evidence)
    ]


def _component_owner(
    path: str, components: list[ArchitectureComponent]
) -> ArchitectureComponent | None:
    normalized_path = path.replace("\\", "/").strip("/")
    matches = [
        (0 if Path(evidence).suffix else 1, len(evidence), component)
        for component in components
        for evidence in component.locations
        if normalized_path == evidence.replace("\\", "/").strip("/")
        or normalized_path.startswith(evidence.replace("\\", "/").strip("/") + "/")
    ]
    if not matches:
        return None
    best_rank = max((directory_rank, length) for directory_rank, length, _ in matches)
    best = [
        component for directory_rank, length, component in matches
        if (directory_rank, length) == best_rank
    ]
    return best[0] if len(best) == 1 else None


def _source_owner(
    path: str, components: list[ArchitectureComponent]
) -> ArchitectureComponent | None:
    normalized_path = path.replace("\\", "/").strip("/")
    directory_matches = [
        (len(evidence), component)
        for component in components
        for evidence in component.locations
        if not Path(evidence).suffix
        and normalized_path.startswith(evidence.replace("\\", "/").strip("/") + "/")
    ]
    if directory_matches:
        best_length = max(length for length, _ in directory_matches)
        best = [component for length, component in directory_matches if length == best_length]
        if len(best) == 1:
            return best[0]
    module_concept = _concept_for_module(Path(path).stem)
    if module_concept:
        component = next(
            (item for item in components if item.name == module_concept[0]),
            None,
        )
        if component:
            return component
    return _component_owner(path, components)


def _component_aliases(component: ArchitectureComponent) -> list[str]:
    candidates = [component.name]
    for location in component.locations:
        path = Path(location)
        if not path.suffix:
            concept = _concept_for(path.name.lower(), None, False)
            if concept and concept[0] == component.name:
                candidates.append(location)
        else:
            concept = _concept_for_module(path.stem)
            if concept and concept[0] == component.name:
                candidates.append(location)
    aliases: set[str] = set()
    for candidate in candidates:
        value = Path(candidate).stem.replace("_", " ").replace("-", " ").lower()
        words = re.findall(r"[a-z0-9]+", value)
        if not words:
            continue
        aliases.add(" ".join(words))
        aliases.add("".join(words))
        if len(words) == 1:
            word = words[0]
            aliases.add(word)
            if word.endswith("ies"):
                aliases.add(word[:-3] + "y")
            elif word.endswith("s") and len(word) > 3:
                aliases.add(word[:-1])
    return sorted(aliases, key=lambda value: (-len(value), value))


def _alias_pattern(alias: str) -> str:
    return r"(?<!\w)" + re.escape(alias).replace(r"\ ", r"[\s_-]+") + r"(?!\w)"


def _import_candidates(import_path: str, source_path: str, source_paths: set[str]) -> list[str]:
    if import_path.startswith(("./", "../")):
        module_path = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), import_path))
        if Path(module_path).suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            module_path = str(Path(module_path).with_suffix(""))
        relative = True
    elif import_path.startswith("."):
        prefix_length = len(import_path) - len(import_path.lstrip("."))
        base = posixpath.dirname(source_path)
        for _ in range(max(prefix_length - 1, 0)):
            base = posixpath.dirname(base)
        module_path = posixpath.normpath(posixpath.join(base, import_path[prefix_length:].replace(".", "/")))
        relative = True
    else:
        module_path = import_path.replace(".", "/").replace("\\", "/")
        relative = False
    module_path = module_path.strip("/")
    candidates: list[tuple[int, str]] = []
    for path in source_paths:
        path_without_suffix = str(Path(path).with_suffix("")).replace("\\", "/")
        if path_without_suffix.endswith(("/__init__", "/index")):
            path_without_suffix = path_without_suffix.rsplit("/", 1)[0]
        if path_without_suffix == module_path:
            candidates.append((len(module_path), path))
        elif not relative and (
            path_without_suffix.endswith("/" + module_path)
            or ("/" in path_without_suffix and module_path.endswith("/" + path_without_suffix))
        ):
            candidates.append((min(len(path_without_suffix), len(module_path)), path))
    if not candidates:
        return []
    best_score = max(score for score, _ in candidates)
    return sorted(path for score, path in candidates if score == best_score)


def _target_component(
    import_path: str, source_path: str, components: list[ArchitectureComponent],
    source_paths: set[str],
) -> ArchitectureComponent | None:
    owners = {
        component.id: component
        for path in _import_candidates(import_path, source_path, source_paths)
        for component in [_source_owner(path, components)]
        if component is not None
    }
    return next(iter(owners.values())) if len(owners) == 1 else None
