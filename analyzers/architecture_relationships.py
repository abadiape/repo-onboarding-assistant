"""Architecture relationships."""
from __future__ import annotations

import re
from pathlib import Path

from analyzers.architecture_components import (
    _CLASS_DECLARATION,
    _alias_pattern,
    _component_aliases,
    _component_owner,
    _source_owner,
    _target_component,
)
from analyzers.architecture_concepts import _concept_for_class
from analyzers.architecture_evidence import (
    _DOC_EXTENSIONS,
    _IGNORED_AREAS,
    _IGNORED_CONTEXT_AREAS,
    _IMPORT_PATTERNS,
    _parts,
    _source_code_lines,
)
from models.architecture_model import ArchitectureComponent, ArchitectureRelationship
from models.models import RepositoryModel

_RELATION_RULES = {
    "react": [
        ("Pages", "Components", "renders"),
        ("Pages", "Hooks", "uses"),
        ("Hooks", "State Management", "reads and updates"),
        ("Pages", "API Client Layer", "requests data through"),
    ],
    "laravel": [
        ("Routes", "Middleware", "passes through"),
        ("Middleware", "Controllers", "dispatches to"),
        ("Routes", "Controllers", "dispatches to"),
        ("Controllers", "Services", "delegates to"),
        ("Services", "Models", "uses"),
    ],
    "nestjs": [
        ("Modules", "Controllers", "registers"),
        ("Modules", "Providers", "registers"),
        ("Controllers", "Providers", "delegates to"),
        ("Guards", "Controllers", "authorizes"),
        ("Interceptors", "Controllers", "wraps"),
    ],
    "backend": [
        ("API Layer", "Controllers", "dispatches to"),
        ("Controllers", "Services", "delegates to"),
        ("Services", "Domain Layer", "applies"),
        ("Domain Layer", "Persistence Layer", "reads and writes through"),
        ("Persistence Layer", "Infrastructure Layer", "uses"),
    ],
    "runtime": [
        ("Runtime", "Registries", "discovers through"),
        ("Runtime", "Providers", "uses"),
        ("Runtime", "Skills", "executes"),
        ("Registries", "Skills", "makes available"),
        ("Registries", "Plugins", "makes available"),
        ("Skills", "Providers", "invokes"),
        ("Skills", "Artifacts", "produces"),
        ("Registries", "Artifacts", "tracks"),
        ("Artifacts", "Registries", "registers with"),
        ("Skills", "Skill Result", "returns"),
        ("Skill Result", "Artifacts", "contains"),
        ("Providers", "Model Requests", "handles"),
        ("Providers", "Model Responses", "returns"),
        ("Model Responses", "Skill Result", "populates"),
    ],
}


_RELATION_WORDS = {
    "produces": "produces",
    "produce": "produces",
    "contains": "contains",
    "executes": "executes",
    "handles": "handles",
    "tracks": "tracks",
    "track": "tracks",
    "registers": "registers",
    "uses": "uses",
    "creates": "creates",
    "provides": "provides",
    "returns": "returns",
    "populates": "populates",
    "invokes": "invokes",
    "delegates": "delegates to",
    "routes": "routes to",
    "dispatches": "dispatches to",
}


def _add_relationship(
    found: dict[tuple[str, str, str], ArchitectureRelationship],
    source: ArchitectureComponent,
    target: ArchitectureComponent,
    relation_type: str,
    confidence: float,
    evidence: str,
    description: str,
) -> None:
    if source.id == target.id:
        return
    key = (source.id, target.id, relation_type)
    relationship = found.get(key)
    if relationship is None:
        found[key] = ArchitectureRelationship(
            source=source.id,
            target=target.id,
            type=relation_type,
            description=description,
            confidence=confidence,
            evidence=[evidence],
        )
        return
    if confidence > relationship.confidence:
        relationship.confidence = confidence
        relationship.description = description
    if evidence not in relationship.evidence:
        relationship.evidence.append(evidence)


def _discover_relationships(
    model: RepositoryModel,
    components: list[ArchitectureComponent],
    framework: str | None,
    files: dict[str, str],
) -> list[ArchitectureRelationship]:
    found: dict[tuple[str, str, str], ArchitectureRelationship] = {}
    names = {component.name: component for component in components}
    runtime_names = {
        "Registries", "Plugins", "Skills", "Artifacts", "Providers",
        "Skill Result", "Model Requests", "Model Responses",
    }
    rule_set = framework or ("runtime" if runtime_names & names.keys() else "backend")
    for source_name, target_name, relation_type in _RELATION_RULES.get(rule_set, []):
        source, target = names.get(source_name), names.get(target_name)
        if source and target:
            _add_relationship(
                found,
                source,
                target,
                relation_type,
                0.55,
                f"layout convention: {source.name} -> {target.name}",
                f"Inferred from {rule_set} framework/layout conventions.",
            )

    class_owners: dict[str, dict[str, ArchitectureComponent]] = {}
    components_by_name = {component.name: component for component in components}
    source_paths = {
        file.path for file in model.files
        if file.kind == "source"
    }
    symbols_by_id = {symbol.id: symbol for symbol in model.symbols}
    ast_types = {
        "IMPORTS": "imports", "INHERITS": "AST inherits",
        "IMPLEMENTS": "AST implements", "DECORATES": "AST decorates",
        "REGISTERS": "AST registers", "EXPORTS": "AST exports",
    }
    for relationship in model.relationships:
        if relationship.relationship_type not in ast_types:
            continue
        source = symbols_by_id.get(relationship.source_id)
        target = symbols_by_id.get(relationship.target_id)
        if not source or not target or source.path not in source_paths or target.path not in source_paths:
            continue
        if set(_parts(source.path)) & (_IGNORED_AREAS | _IGNORED_CONTEXT_AREAS):
            continue
        if set(_parts(target.path)) & (_IGNORED_AREAS | _IGNORED_CONTEXT_AREAS):
            continue
        owner = _source_owner(source.path, components)
        target_owner = _source_owner(target.path, components)
        if owner and target_owner:
            for evidence in relationship.evidence:
                _add_relationship(
                    found, owner, target_owner, ast_types[relationship.relationship_type], relationship.confidence,
                    f"{evidence.path}:{evidence.line} (AST {relationship.relationship_type.lower().removesuffix('s')} {target.qualified_name})",
                    "Static AST relationship between local component symbols; not runtime execution.",
                )
    for path, content in files.items():
        if path not in source_paths:
            continue
        owner = _source_owner(path, components)
        if owner is None:
            continue
        source_lines = _source_code_lines(content)
        code = "\n".join(line for _, line in source_lines)
        for class_name in _CLASS_DECLARATION.findall(code):
            class_concept = _concept_for_class(class_name, framework)
            symbol_owner = (
                components_by_name.get(class_concept[0])
                if class_concept else None
            ) or owner
            class_owners.setdefault(class_name, {})[symbol_owner.id] = symbol_owner

        for line_number, line in source_lines:
            for pattern, relation_type in _IMPORT_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                imported_path = match.group(1)
                target = _target_component(imported_path, path, components, source_paths)
                if target:
                    _add_relationship(
                        found,
                        owner,
                        target,
                        relation_type,
                        0.9,
                        f"{path}:{line_number} (import {imported_path})",
                        "Lexically detected an import or re-export of a local component module.",
                    )
                break

    for path, content in files.items():
        if path not in source_paths:
            continue
        owner = _source_owner(path, components)
        if owner is None:
            continue
        for line_number, line in _source_code_lines(content):
            if re.match(r"\s*(?:from\s+\S+\s+import|import\s+)", line):
                continue
            for class_name, targets in class_owners.items():
                if len(targets) != 1:
                    continue
                if not re.search(rf"\b{re.escape(class_name)}\b", line):
                    continue
                for target in targets.values():
                    if target.id == owner.id:
                        continue
                    if re.search(r"\b(?:register|bind|provide|providers|inject)\b", line, re.IGNORECASE):
                        relation_type, confidence = "registers", 0.88
                    elif re.search(r"\bextends\b", line, re.IGNORECASE):
                        relation_type, confidence = "extends", 0.86
                    elif re.search(r"\bimplements\b", line, re.IGNORECASE):
                        relation_type, confidence = "implements", 0.86
                    elif re.search(rf"\bnew\s+{re.escape(class_name)}\b|\b{re.escape(class_name)}\s*\(", line):
                        relation_type, confidence = "constructs", 0.84
                    elif (
                        re.search(rf"->\s*{re.escape(class_name)}\b", line)
                        and (concept := _concept_for_class(class_name, framework))
                        and concept[0] == target.name
                    ):
                        relation_type, confidence = "returns", 0.82
                    elif re.search(rf"[:<]\s*{re.escape(class_name)}\b", line):
                        relation_type, confidence = "depends on", 0.78
                    else:
                        relation_type, confidence = "references", 0.65
                    _add_relationship(
                        found,
                        owner,
                        target,
                        relation_type,
                        confidence,
                        f"{path}:{line_number} (reference to {class_name})",
                        "Lexically detected a cross-component type or class reference.",
                    )

    for path, content in files.items():
        if path in source_paths or Path(path).suffix.lower() not in {".yaml", ".yml"}:
            continue
        owner = _component_owner(path, components)
        if owner is None:
            continue
        registration_indent: int | None = None
        for line_number, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            if registration_indent is not None and indent <= registration_indent:
                registration_indent = None
            if re.match(r"^(?:providers|bindings|registrations)\s*:", stripped, re.IGNORECASE):
                registration_indent = indent
            elif registration_indent is None:
                continue
            for class_name, targets in class_owners.items():
                if len(targets) == 1 and re.search(rf"\b{re.escape(class_name)}\b", stripped):
                    target = next(iter(targets.values()))
                    _add_relationship(
                        found, owner, target, "registers", 0.75,
                        f"{path}:{line_number} (registration of {class_name})",
                        "A configuration registration names a component class.",
                    )

    alias_patterns = {
        component.id: [re.compile(_alias_pattern(alias), re.IGNORECASE) for alias in _component_aliases(component)]
        for component in components
    }
    for path, content in files.items():
        if not any(
            file.path == path and (file.kind != "source" or Path(path).suffix.lower() in _DOC_EXTENSIONS)
            for file in model.files
        ):
            continue
        for line_number, line in enumerate(content.splitlines(), 1):
            if (
                Path(path).suffix.lower() in _DOC_EXTENSIONS
                and "Tools" in names and "Retrieval" in names
                and re.search(r"\b(?:rag|retrieval)(?:\s+operation)?\s+as\s+(?:an?\s+)?(?:regular\s+)?tool\b", line, re.IGNORECASE)
                and not re.search(r"\b(?:no|not|never|without)\b", line, re.IGNORECASE)
            ):
                _add_relationship(
                    found, names["Tools"], names["Retrieval"], "can expose as a tool",
                    0.82, f"{path}:{line_number} (documented optional retrieval tool)",
                    "Documentation describes retrieval as a tool; its use is optional.",
                )
            for sentence in re.split(r"(?<=[.!?;])\s+", line):
                if not any(re.search(rf"\b{verb}\b", sentence, re.IGNORECASE) for verb in _RELATION_WORDS):
                    continue
                mentions = []
                for component in components:
                    for pattern in alias_patterns[component.id]:
                        match = pattern.search(sentence)
                        if match:
                            mentions.append((component, match))
                            break
                for source, source_match in mentions:
                    for target, target_match in mentions:
                        if source.id == target.id:
                            continue
                        if target_match.start() <= source_match.end():
                            continue
                        relation_text = sentence[source_match.end():target_match.start()].lower()
                        relation_type = next(
                            (relation for verb, relation in _RELATION_WORDS.items() if re.search(rf"\b{verb}\b", relation_text)),
                            None,
                        )
                        if relation_type:
                            _add_relationship(
                                found,
                                source,
                                target,
                                relation_type,
                                0.82,
                                f"{path}:{line_number} (documented relationship)",
                                "Explicit relationship described in repository documentation/configuration.",
                            )

    for component in components:
        component.relationships.clear()
    relationships = sorted(
        found.values(),
        key=lambda item: (-item.confidence, item.source, item.target, item.type),
    )
    for relation in relationships:
        source = next(component for component in components if component.id == relation.source)
        source.relationships.append({
            "target": relation.target,
            "type": relation.type,
            "confidence": relation.confidence,
            "evidence": relation.evidence,
        })
    return relationships
