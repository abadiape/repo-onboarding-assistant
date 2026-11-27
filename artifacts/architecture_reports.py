"""Architecture reports."""
from __future__ import annotations

import json

from analyzers.architecture_scoring import _significance_label
from artifacts.architecture_diagrams import _diagram_relationships
from models.architecture_model import ArchitectureModel


def render_architecture_summary_markdown(model: ArchitectureModel) -> str:
    components_by_id = {component.id: component for component in model.components}
    high = [component for component in model.components if _significance_label(component) == "High"]
    central = high[:6]
    if not central:
        central = model.components[:min(3, len(model.components))]
    central_ids = {component.id for component in central}
    additional_central = [component for component in high if component.id not in central_ids]
    supporting = [component for component in model.components if component.id not in central_ids and component not in additional_central]
    lines = [
        "# Architecture Overview",
        "",
        f"**{model.system_name}** is a **{model.system_type}**. {model.description}",
        "",
    ]
    if central:
        lines += [
            "The main concepts to understand first are "
            + ", ".join(f"**{component.name}**" for component in central)
            + ".",
            "",
        ]
    areas = model.repository_relevance.areas
    if areas:
        lines += [
            "The repository contains identifiable application or workspace areas: "
            + ", ".join(f"**{area.name}** (`{area.path}`)" for area in areas[:8])
            + (f", and {len(areas) - 8} more" if len(areas) > 8 else "")
            + ". Start with these project-owned areas before framework internals.",
            "",
        ]
    if model.repository_relevance.paths.get("low"):
        lines += [
            "Vendor and third-party directories are supporting dependencies, not primary onboarding material.",
            "",
        ]
    lines += ["## Main Components", ""]
    for component in central:
        priority_evidence = sorted(
            component.evidence,
            key=lambda item: (
                0 if "(readme lead)" in item else
                1 if "(public API export)" in item else
                2 if "(entry point" in item else
                3 if "(documentation)" in item else
                4 if "(structure)" in item or "(source)" in item else 5,
                item,
            ),
        )[:4]
        lines.append(
            f"- **{component.name}** — {component.description} "
            f"(significance: {_significance_label(component)}; confidence: {component.confidence:.0%}). "
            f"Evidence: {', '.join(f'`{path}`' for path in priority_evidence)}."
        )
    if not model.components:
        lines.append("- No major architectural components could be inferred.")
    if additional_central:
        lines += [
            "", "Other significant components: "
            + ", ".join(f"**{component.name}**" for component in additional_central[:8])
            + (f", and {len(additional_central) - 8} more" if len(additional_central) > 8 else "") + ".",
        ]
    if supporting:
        lines += [
            "", "## Supporting Subsystems", "",
            "Other detected components include "
            + ", ".join(
                f"**{component.name}** ({_significance_label(component)} significance, "
                f"{component.confidence:.0%} confidence)"
                for component in supporting[:8]
            )
            + (f", and {len(supporting) - 8} more" if len(supporting) > 8 else "")
            + ". Their roles and evidence are recorded in the architecture map.",
        ]
    if model.layers:
        lines += ["", "## Architectural Layers", "", "The following layers reflect the roles inferred for this repository:", ""]
        for layer in model.layers:
            names = ", ".join(components_by_id[component_id].name for component_id in layer.components[:6])
            if len(layer.components) > 6:
                names += f", and {len(layer.components) - 6} more"
            lines.append(f"- **{layer.name}**: {names}.")
    extensions = [component for component in model.components if component.type in {"extension", "registry"}]
    if extensions:
        lines += [
            "", "## Extension Points", "",
            "Potential extension or registration points include "
            + ", ".join(f"**{component.name}**" for component in extensions[:8])
            + (f", and {len(extensions) - 8} more" if len(extensions) > 8 else "")
            + "; inspect their implementations to see how capabilities are added.",
        ]
    if model.relationships:
        lines += ["", "## Relationships", ""]
        relations = sorted(
            _diagram_relationships(model.relationships),
            key=lambda relation: (
                -(components_by_id[relation.source].significance + components_by_id[relation.target].significance),
                -relation.confidence, relation.source, relation.target,
            ),
        )[:8]
        for relation in relations:
            evidence = ", ".join(f"`{item}`" for item in relation.evidence[:2])
            lines.append(
                f"- **{components_by_id[relation.source].name}** {relation.type} "
                f"**{components_by_id[relation.target].name}** "
                f"({relation.confidence:.0%} confidence). {relation.description} "
                f"Evidence: {evidence}."
            )
    lines += ["", "## Execution Flow", ""]
    for flow in model.execution_flows:
        lines.append(f"### {flow['name']}")
        lines.append(
            "This is an inferred conceptual path, not an observed runtime trace. "
            "Imports and references indicate dependencies, not necessarily calls."
        )
        for path in flow["paths"]:
            for index, (source_id, target_id, relation) in enumerate(zip(
                path["component_ids"], path["component_ids"][1:], path["relationship_types"]
            ), 1):
                lines.append(
                    f"{index}. **{components_by_id[source_id].name}** {relation} "
                    f"**{components_by_id[target_id].name}**."
                )
    if not model.execution_flows:
        lines.append("No component-to-component runtime flow could be inferred.")
    if model.entry_points:
        lines += ["", "Entry points: " + ", ".join(f"`{path}`" for path in model.entry_points) + "."]
    lines += ["", "## Key Concepts", ""]
    lines += [f"- {item}" for item in (responsibility for component in central for responsibility in component.responsibilities)] or ["- No responsibilities were inferred from repository structure."]
    if model.framework_architecture:
        lines += ["", "Framework architecture:", *[f"- {item}" for item in model.framework_architecture]]
    if model.external_dependencies or model.data_stores:
        lines += ["", "Declared or configured integrations and data stores (not proof of active deployment):"]
        lines += [f"- {item}" for item in [*model.external_dependencies, *model.data_stores]]
    if model.optional_integrations:
        lines += ["", "Optional integrations (not proof of activation or deployment):"]
        lines += [f"- {item}" for item in model.optional_integrations]
    if model.deployment_architecture:
        lines += ["", "Deployment architecture:", *[f"- {item}" for item in model.deployment_architecture]]
    lines += ["", "## Recommended Learning Path", ""]
    lines += [
        f"{index}. Explore `{path}`."
        for index, path in enumerate(model.recommended_learning_path, 1)
    ] or ["1. Start with the repository README and major subsystem directories."]
    return "\n".join(lines) + "\n"


def render_architecture_map_json(model: ArchitectureModel) -> str:
    return json.dumps(model.to_dict(), ensure_ascii=False, indent=2) + "\n"
