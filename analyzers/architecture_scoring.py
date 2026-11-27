"""Rank architectural components by evidence and significance."""
from __future__ import annotations

import re
from pathlib import Path

from analyzers.architecture_components import (
    _alias_pattern,
    _component_aliases,
    _target_component,
)
from analyzers.architecture_concepts import _concept_for, _framework_key
from analyzers.architecture_evidence import (
    _DOC_EXTENSIONS,
    _is_config_file,
    _parts,
    _public_imports,
)
from models.architecture_model import ArchitectureComponent, ArchitectureRelationship
from models.models import RepositoryModel


def _rank_components(
    model: RepositoryModel,
    components: list[ArchitectureComponent],
    relationships: list[ArchitectureRelationship],
    files: dict[str, str],
    entry_points: list[str],
) -> None:
    kinds = {file.path: file.kind for file in model.files}
    sources: dict[str, dict[str, list[str]]] = {
        component.id: {} for component in components
    }

    def add(component: ArchitectureComponent, category: str, evidence: str) -> None:
        group = sources[component.id].setdefault(category, [])
        if evidence not in group and len(group) < 3:
            group.append(evidence)

    framework = _framework_key(model)
    aliases = {
        component.id: [re.compile(_alias_pattern(alias), re.IGNORECASE) for alias in _component_aliases(component)]
        for component in components
    }
    for component in components:
        for path in component.locations:
            category = "source" if kinds.get(path) == "source" else "structure"
            add(component, category, f"{path} ({category})")
            if path in entry_points:
                add(component, "entry_point", f"{path} (entry point)")
        concepts = (
            _concept_for(part, framework, False)
            for path in component.locations for part in _parts(path)
        )
        if framework and any(concept and concept[0] == component.name for concept in concepts):
            add(component, "framework", f"{framework} framework convention")

    source_paths = {file.path for file in model.files if file.kind == "source"}
    for path, content in files.items():
        name = Path(path).name.lower()
        if kinds.get(path) == "source":
            for number, import_path in _public_imports(path, content):
                target = _target_component(import_path, path, components, source_paths)
                if target:
                    add(target, "public_api", f"{path}:{number} (public API export)")
            continue
        is_readme = name.startswith("readme")
        is_doc = Path(path).suffix.lower() in _DOC_EXTENSIONS
        is_config = _is_config_file(Path(path), kinds.get(path, ""))
        if not (is_doc or is_config):
            continue
        lead = is_readme and len(Path(path).parts) == 1
        for number, line in enumerate(content.splitlines(), 1):
            if lead and (re.match(r"^##\s+", line) or number > 40):
                lead = False
            category = "readme_lead" if lead else "readme" if is_readme else "documentation" if is_doc else "configuration"
            for component in components:
                if any(pattern.search(line) for pattern in aliases[component.id]):
                    add(component, category, f"{path}:{number} ({category.replace('_', ' ')})")

    by_id = {component.id: component for component in components}
    for relationship in relationships:
        for location in relationship.evidence:
            if location.startswith("layout convention:"):
                continue
            category = "reference"
            for component_id in (relationship.source, relationship.target):
                add(by_id[component_id], category, location)
            path = location.split(":", 1)[0]
            if path in entry_points:
                add(by_id[relationship.target], "entry_point", f"{location} (entry point reference)")

    confidence_weights = {
        "structure": 0.30, "source": 0.28, "framework": 0.10,
        "readme_lead": 0.18, "readme": 0.08, "documentation": 0.12,
        "public_api": 0.18, "configuration": 0.10, "reference": 0.15,
        "entry_point": 0.15,
    }
    relevance_weights = {
        "structure": 0.05, "source": 0.08, "framework": 0.05,
        "readme_lead": 0.35, "readme": 0.12, "documentation": 0.12,
        "public_api": 0.20, "configuration": 0.08, "reference": 0.15,
        "entry_point": 0.25,
    }
    for component in components:
        evidence = sources[component.id]
        component.confidence = round(min(0.98, sum(confidence_weights[key] for key in evidence)), 2)
        component.relevance = round(min(1.0, sum(relevance_weights[key] for key in evidence)), 2)
        component.evidence = [
            item for category in confidence_weights for item in evidence.get(category, [])
        ]
    components.sort(key=lambda component: (-component.relevance, -component.confidence, component.name))


def _score_significance(
    components: list[ArchitectureComponent],
    relationships: list[ArchitectureRelationship],
    flows: list[dict],
) -> None:
    by_id = {component.id: component for component in components}
    neighbors: dict[str, set[str]] = {component.id: set() for component in components}
    incoming_major: dict[str, set[str]] = {component.id: set() for component in components}
    for relationship in relationships:
        if all(item.startswith("layout convention:") for item in relationship.evidence):
            continue
        neighbors[relationship.source].add(relationship.target)
        neighbors[relationship.target].add(relationship.source)
        if by_id[relationship.source].relevance >= 0.4:
            incoming_major[relationship.target].add(relationship.source)
    flow_ids = {
        component_id
        for flow in flows for path in flow["paths"] for component_id in path["component_ids"]
    }
    for component in components:
        component.significance = round(min(
            1.0,
            0.72 * component.relevance
            + min(0.12, 0.03 * len(neighbors[component.id]))
            + min(0.09, 0.03 * len(incoming_major[component.id]))
            + (0.07 if component.id in flow_ids else 0.0),
        ), 2)
    components.sort(key=lambda component: (-component.significance, -component.confidence, component.name))


def _significance_label(component: ArchitectureComponent) -> str:
    if component.significance >= 0.55:
        return "High"
    if component.significance >= 0.20:
        return "Medium"
    return "Low"
