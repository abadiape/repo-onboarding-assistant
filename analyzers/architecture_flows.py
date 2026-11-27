"""Architecture flows."""
from __future__ import annotations

from analyzers.architecture_components import _source_owner
from models.architecture_model import ArchitectureComponent, ArchitectureRelationship


def _execution_flows(
    components: list[ArchitectureComponent],
    relationships: list[ArchitectureRelationship],
    entry_points: list[str],
    external_dependencies: list[str],
    public_entries: list[str],
    *,
    require_execution_evidence: bool = False,
) -> list[dict]:
    if not relationships:
        return []
    flow_types = {
        "executes", "invokes", "produces", "handles", "registers",
        "registers with", "returns", "contains", "uses",
        "dispatches to", "delegates to", "routes to", "creates", "populates",
        "renders", "reads and updates", "requests data through", "applies",
        "reads and writes through", "passes through", "authorizes", "wraps",
        "discovers through", "makes available", "tracks",
    }
    outgoing: dict[str, list[ArchitectureRelationship]] = {}
    incoming = set()
    for relation in relationships:
        if relation.type == "can expose as a tool":
            continue
        if require_execution_evidence and relation.type not in {
            "executes", "invokes", "dispatches to", "delegates to", "routes to",
        }:
            continue
        outgoing.setdefault(relation.source, []).append(relation)
        incoming.add(relation.target)
    roots = [
        component.id for component in components
        if component.id not in incoming and outgoing.get(component.id)
    ]
    entry_owners = [
        owner.id for entry in entry_points
        for owner in [_source_owner(entry, components)]
        if owner and outgoing.get(owner.id)
    ]
    if not entry_owners:
        entry_owners = [component_id for component_id in public_entries if outgoing.get(component_id)]
    if entry_owners:
        roots = list(dict.fromkeys(entry_owners))
    if not roots:
        roots = [component.id for component in components if outgoing.get(component.id)]
    by_id = {component.id: component for component in components}
    roots.sort(key=lambda item: (-by_id[item].significance, item))
    paths: list[tuple[list[str], list[ArchitectureRelationship]]] = []

    def walk(
        component_id: str,
        ids: list[str],
        relations: list[ArchitectureRelationship],
        root_paths: list[tuple[list[str], list[ArchitectureRelationship]]],
    ) -> None:
        if len(root_paths) >= 64:
            return
        if relations:
            root_paths.append((ids, relations))
        if len(ids) >= 8:
            return
        available_edges = [
            edge for edge in outgoing.get(component_id, []) if edge.target not in ids
        ]
        best_edges: dict[str, ArchitectureRelationship] = {}
        for edge in available_edges:
            existing = best_edges.get(edge.target)
            rank = (edge.type in flow_types, edge.confidence)
            if existing is None or rank > (existing.type in flow_types, existing.confidence):
                best_edges[edge.target] = edge
        next_edges = sorted(
            best_edges.values(),
            key=lambda edge: (edge.type not in flow_types, -edge.confidence, edge.target),
        )
        for edge in next_edges:
            walk(edge.target, [*ids, edge.target], [*relations, edge], root_paths)

    for root in roots[:20]:
        root_paths: list[tuple[list[str], list[ArchitectureRelationship]]] = []
        walk(root, [root], [], root_paths)
        paths.extend(root_paths)
    if not paths:
        return []
    component_order = {component.id: component.name for component in components}

    def path_score(path_item: tuple[list[str], list[ArchitectureRelationship]]) -> tuple[float, int, tuple[str, ...]]:
        path, path_relationships = path_item
        score = sum(
            relation.confidence * (1.0 if relation.type in flow_types else 0.7)
            for relation in path_relationships
        )
        return (
            score / len(path_relationships)
            + sum(by_id[item].significance for item in path) / len(path)
            + 0.08 * min(sum(relation.type in flow_types for relation in path_relationships), 4)
            + 0.12 * min(len(path_relationships), 4),
            len(path_relationships),
            tuple(component_order.get(component_id, "") for component_id in path),
        )

    path, path_relationships = max(
        paths,
        key=path_score,
    )
    flow_paths = [{
        "component_ids": path,
        "relationship_types": [relation.type for relation in path_relationships],
        "relationship_confidences": [relation.confidence for relation in path_relationships],
        "relationship_evidence": [relation.evidence for relation in path_relationships],
    }]
    for relation in relationships:
        if (
            relation.type == "can expose as a tool"
            and relation.source in path
            and relation.target not in path
        ):
            flow_paths.append({
                "component_ids": [relation.source, relation.target],
                "relationship_types": [relation.type],
                "relationship_confidences": [relation.confidence],
                "relationship_evidence": [relation.evidence],
                "kind": "optional",
            })
    return [{
        "name": "Likely conceptual flow",
        "paths": flow_paths,
        "entry_points": entry_points,
        "external_dependencies": external_dependencies,
    }]
