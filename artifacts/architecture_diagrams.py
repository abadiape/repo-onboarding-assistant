"""Architecture diagrams."""
from __future__ import annotations

from pathlib import Path

from analyzers.architecture_flows import _execution_flows
from analyzers.architecture_scoring import _significance_label
from models.architecture_model import ArchitectureModel, ArchitectureRelationship


def _mermaid_text(text: str) -> str:
    return text.replace(";", "#59;").replace('"', "#quot;").replace("\n", " ").replace("|", "#124;")


def _diagram_relationships(
    relationships: list[ArchitectureRelationship],
) -> list[ArchitectureRelationship]:
    priority = {
        "executes": 10,
        "produces": 10,
        "contains": 10,
        "tracks": 10,
        "handles": 9,
        "returns": 9,
        "delegates to": 9,
        "dispatches to": 9,
        "routes to": 9,
        "invokes": 9,
        "registers with": 8,
        "registers": 8,
        "makes available": 8,
        "uses": 7,
        "imports": 6,
        "re-exports": 6,
        "constructs": 5,
        "depends on": 4,
        "extends": 4,
        "implements": 4,
        "references": 3,
    }
    primary: dict[tuple[str, str], ArchitectureRelationship] = {}
    for relation in relationships:
        key = (relation.source, relation.target)
        current = primary.get(key)
        relation_rank = (relation.confidence, priority.get(relation.type, 0))
        current_rank = (
            current.confidence,
            priority.get(current.type, 0),
        ) if current else (-1, -1.0)
        if relation_rank > current_rank:
            primary[key] = relation
    return sorted(primary.values(), key=lambda item: (item.source, item.target))


def _needs_aggregation(model: ArchitectureModel) -> bool:
    return bool(model.repository_relevance.areas) or len(model.components) + len(model.subsystems) + 1 > 15


def _aggregated_graph(model: ArchitectureModel, detail: bool) -> str:
    groups: dict[str, list[str]] = {}
    labels = {
        "custom module": "Custom Modules",
        "workspace module": "Workspace Modules",
        "business area": "Business Areas",
        "theme": "Storefront Themes",
    }
    for area in model.repository_relevance.areas:
        groups.setdefault(labels[area.kind], []).append(f"{area.name} ({area.path})")
    if not groups and detail:
        components = {component.id: component.name for component in model.components}
        for subsystem in model.subsystems:
            groups[subsystem.name] = [components[item] for item in subsystem.components]
    elif not detail:
        for subsystem in model.subsystems:
            groups.setdefault(subsystem.name, [])
    if not detail and model.frameworks:
        groups.setdefault("Frameworks: " + ", ".join(model.frameworks), [])
    if not detail and model.repository_relevance.paths.get("low"):
        groups.setdefault("Vendor and third-party code", [])
    if not detail and model.repository_relevance.paths.get("medium") and any(
        "infra" in path.lower() or "deploy" in path.lower() or "config" in path.lower()
        for path in model.repository_relevance.paths["medium"]
    ):
        groups.setdefault("Configuration and infrastructure", [])

    ordered = list(groups.items())
    omitted_groups = max(0, len(ordered) - 13)
    if omitted_groups:
        ordered = ordered[:13] + [(f"Other groups ({omitted_groups})", [])]
    lines = ["flowchart TD", f'    system["{_mermaid_text(model.system_name)}"]']
    if not ordered:
        lines += ['    unknown["No architectural components identified"]', "    system --> unknown"]
        return "\n".join(lines) + "\n"
    for index, (name, children) in enumerate(ordered):
        label = f"{name} ({len(children)})" if children else name
        lines += [f'    group_{index}["{_mermaid_text(label)}"]', f"    system --> group_{index}"]
    if not detail:
        group_index = {name: index for index, (name, _) in enumerate(ordered)}
        component_group = {
            component_id: group_index[subsystem.name]
            for subsystem in model.subsystems if subsystem.name in group_index
            for component_id in subsystem.components
        }
        edges: dict[tuple[int, int], ArchitectureRelationship] = {}
        for relation in _diagram_relationships(model.relationships):
            source = component_group.get(relation.source)
            target = component_group.get(relation.target)
            if source is not None and target is not None and source != target:
                edges.setdefault((source, target), relation)
        for (source, target), relation in list(edges.items())[:20]:
            lines.append(f"    group_{source} -->|{_mermaid_text(relation.type)}| group_{target}")
    if detail:
        candidates = [(index, child) for index, (_, children) in enumerate(ordered) for child in children]
        available = 15 - 1 - len(ordered)
        shown = candidates[:available] if len(candidates) <= available else candidates[:max(0, available - 1)]
        for index, (group, child) in enumerate(shown):
            lines += [f'    area_{index}["{_mermaid_text(child)}"]', f"    group_{group} --> area_{index}"]
        remaining = len(candidates) - len(shown)
        if remaining and available:
            lines += [f'    more["Other areas ({remaining})"]', "    system --> more"]
    return "\n".join(lines) + "\n"


def render_system_overview_mermaid(model: ArchitectureModel) -> str:
    if _needs_aggregation(model):
        return _aggregated_graph(model, detail=False)
    lines = ["flowchart TD", f'    system["{_mermaid_text(model.system_name)}"]']
    if not model.components:
        lines += ['    unknown["No architectural components identified"]', "    system --> unknown"]
    for subsystem in model.subsystems:
        lines.append(f'    {subsystem.id}["{_mermaid_text(subsystem.name)}"]')
        lines.append(f"    system --> {subsystem.id}")
        for component_id in subsystem.components:
            lines.append(f"    {subsystem.id} --> {component_id}")
    for component in model.components:
        lines.append(f'    {component.id}["{_mermaid_text(component.name)}"]')
    if model.components:
        lines += [
            "    classDef high fill:#dbeafe,stroke:#1d4ed8,stroke-width:3px",
            "    classDef medium fill:#f0f9ff,stroke:#0284c7,stroke-width:2px",
            "    classDef low fill:#f8fafc,stroke:#94a3b8,stroke-width:1px",
        ]
        for component in model.components:
            lines.append(f"    class {component.id} {_significance_label(component).lower()}")
    for relation in _diagram_relationships(model.relationships):
        lines.append(f"    {relation.source} -->|{_mermaid_text(relation.type)}| {relation.target}")
    return "\n".join(lines) + "\n"


def render_execution_flow_mermaid(model: ArchitectureModel) -> str:
    lines = ["sequenceDiagram", "    actor User"]
    components = {component.id: component for component in model.components}
    flows = model.execution_flows
    if not flows:
        if any("magento" in framework.lower() for framework in model.frameworks):
            relationships = [
                relation for relation in model.relationships
                if relation.source in components and relation.target in components
            ]
            associations = _execution_flows(
                model.components, relationships, model.entry_points, [], [],
            )
            if associations:
                path = associations[0]["paths"][0]
                notice = "association_notice"
                while notice in components:
                    notice += "_"
                graph = [
                    "flowchart LR",
                    f'    {notice}["Associations only - not a verified execution sequence or runtime calls"]',
                ]
                for component_id in path["component_ids"]:
                    graph.append(f'    {component_id}["{_mermaid_text(components[component_id].name)}"]')
                for source, target, relation in zip(
                    path["component_ids"], path["component_ids"][1:], path["relationship_types"],
                ):
                    graph.append(f"    {source} -->|{_mermaid_text(relation)}| {target}")
                return "\n".join(graph) + "\n"
        lines.append("    Note over User: No component execution path could be inferred")
        return "\n".join(lines) + "\n"

    lines.append("    Note over User: Conceptual flow inferred from relationships, not a runtime trace")
    flow = flows[0]
    used = set()
    for path in flow["paths"]:
        for component_id in path["component_ids"]:
            component = components[component_id]
            if component_id not in used:
                lines.append(f"    participant {component.id} as {_mermaid_text(component.name)}")
                used.add(component_id)
    for path in flow["paths"]:
        ids = path["component_ids"]
        first = components[ids[0]]
        optional = path.get("kind") == "optional"
        if optional:
            lines.append("    opt Optional integration")
        elif flow["entry_points"] and all(
            Path(entry).name == "__init__.py" for entry in flow["entry_points"]
        ):
            lines.append(
                f"    Note over {first.id}: Public API: "
                f"{_mermaid_text(', '.join(flow['entry_points']))}"
            )
        else:
            lines.append(
                f"    User->>{first.id}: Start at "
                f"{_mermaid_text(', '.join(flow['entry_points']) or 'application entry')}"
            )
        for source_id, target_id, relation in zip(
            ids, ids[1:], path["relationship_types"]
        ):
            lines.append(f"    {source_id}->>{target_id}: {_mermaid_text(relation)}")
        if optional:
            lines.append("    end")
    return "\n".join(lines) + "\n"


def render_subsystem_map_mermaid(model: ArchitectureModel) -> str:
    if _needs_aggregation(model):
        return _aggregated_graph(model, detail=True)
    lines = ["flowchart TD", f'    system["{_mermaid_text(model.system_name)}"]']
    if not model.subsystems:
        lines += ['    unknown["No subsystem boundaries identified"]', "    system --> unknown"]
        return "\n".join(lines) + "\n"
    components = {component.id: component for component in model.components}
    for subsystem in model.subsystems:
        lines.append(f'    subgraph {subsystem.id}["{_mermaid_text(subsystem.name)}"]')
        for component_id in subsystem.components:
            lines.append(
                f'        {component_id}["{_mermaid_text(components[component_id].name)}"]'
            )
        lines.append("    end")
        for component_id in subsystem.components:
            lines.append(f"    system --> {component_id}")
    for relationship in _diagram_relationships(model.relationships):
        lines.append(
            f"    {relationship.source} -->|{_mermaid_text(relationship.type)}| "
            f"{relationship.target}"
        )
    return "\n".join(lines) + "\n"


def render_module_graph_mermaid(model: ArchitectureModel, module_path: str) -> str:
    area = next((item for item in model.repository_relevance.areas if item.path == module_path), None)
    if area is None:
        raise ValueError(f"Unknown module or business area: {module_path}")
    prefix = area.path.rstrip("/") + "/"
    components = [
        component for component in model.components
        if any(location == area.path or location.startswith(prefix) for location in component.locations)
        and not (component.type == "feature" and area.path in component.locations)
    ]
    ids = {component.id for component in components}
    lines = ["flowchart TD", f'    module["{_mermaid_text(area.name)} ({_mermaid_text(area.path)})"]']
    if not components:
        lines += ['    unknown["No module-level components identified"]', "    module --> unknown"]
    for component in components:
        lines += [
            f'    {component.id}["{_mermaid_text(component.name)}"]',
            f"    module --> {component.id}",
        ]
    scoped_relationships = [
        relation for relation in model.relationships
        if relation.source in ids and relation.target in ids
        and any(evidence.startswith(prefix) for evidence in relation.evidence)
    ]
    for relation in _diagram_relationships(scoped_relationships):
        lines.append(f"    {relation.source} -->|{_mermaid_text(relation.type)}| {relation.target}")
    return "\n".join(lines) + "\n"
