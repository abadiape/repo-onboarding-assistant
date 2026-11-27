"""Build structured knowledge-hub data from analysis results."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from analyzers.business_insights import first_week_onboarding_plan
from analyzers.technical_onboarding import repository_purpose, technical_topics
from models.architecture_model import ArchitectureModel
from models.business_insights import BusinessInsights
from models.business_narrative import BusinessNarrative
from models.domain_discovery import DomainDiscovery
from models.models import RepositoryModel
from models.repository_archetype import ArchetypeResult, RepositoryArchetype


def build_knowledge_hub(
    model: RepositoryModel,
    architecture: ArchitectureModel,
    domains: DomainDiscovery,
    insights: BusinessInsights,
    narrative: BusinessNarrative,
    artifact_names: list[str],
    archetype: ArchetypeResult | None = None,
) -> dict[str, Any]:
    """Aggregate analyzer results without reading generated Markdown."""
    components = {item.id: item.name for item in architecture.components}
    relationships = [
        {"source": components[item.source], "target": components[item.target], "label": item.type,
         **({"evidence": item.evidence} if item.evidence else {})}
        for item in architecture.relationships
        if item.source in components and item.target in components
    ]
    flow_edges = []
    for flow in architecture.execution_flows:
        for path in flow.get("paths", []):
            ids = path["component_ids"]
            evidence = path.get("relationship_evidence", [])
            for index, (source, target, label) in enumerate(zip(ids, ids[1:], path["relationship_types"])):
                if source in components and target in components:
                    flow_edges.append({
                        "source": components[source], "target": components[target],
                        "label": label + (" (optional)" if path.get("kind") == "optional" else ""),
                        **({"evidence": evidence[index]} if index < len(evidence) and evidence[index] else {}),
                    })
    actionable = [
        item for item in insights.domain_impacts
        if item.onboarding_importance in {"Very High", "High"}
    ]
    starting_domains = actionable or [
        item for item in insights.domain_impacts if item.onboarding_importance == "Medium"
    ]
    purpose = narrative.system_purpose
    if archetype is None and not narrative.primary_domains and architecture.description.strip():
        purpose = architecture.description.strip()
    elif archetype and archetype.archetype == RepositoryArchetype.BUSINESS_APPLICATION and not narrative.primary_domains:
        purpose = repository_purpose(model, purpose)
    workflow_edges = [
        {"source": workflow.name, "target": domain, "label": "associated with"}
        for workflow in narrative.workflows for domain in workflow.domains
    ]
    technical = archetype is not None and archetype.archetype != RepositoryArchetype.BUSINESS_APPLICATION
    topics = technical_topics(model, archetype.archetype) if technical and archetype else []
    observations = []
    for domain in domains.domains:
        paths = [module.path for module in domains.custom_modules if module.name in domain.modules]
        if paths:
            observations.append(f"{domain.name}: matched module paths include {', '.join(paths[:3])}.")
        if len(observations) == 5:
            break
    if architecture.entry_points:
        observations.append("Potential entry points: " + ", ".join(architecture.entry_points[:3]) + ".")
    if architecture.external_dependencies or architecture.data_stores:
        observations.append(
            "Detected external technology signals: "
            + ", ".join((architecture.external_dependencies + architecture.data_stores)[:6])
            + ". Confirm runtime configuration."
        )
    if architecture.optional_integrations:
        observations.append(
            "Optional integrations (not proof of activation or deployment): "
            + "; ".join(architecture.optional_integrations) + "."
        )
    if architecture.relationships and not architecture.execution_flows:
        observations.append(
            "The available relationships do not establish an execution sequence; "
            "inspect their evidence in the visualizations."
        )
    return {
        "schema_version": 1,
        **({"repository_archetype": archetype.to_dict()} if archetype else {}),
        "technical_topics": [asdict(item) for item in topics],
        "api_inventory": model.api_inventory,
        "overview": {
            "repository_name": model.repository_name,
            "purpose": purpose,
            "business_focus": [item.name for item in actionable[:5]],
            "starting_areas": [item.name for item in starting_domains[:4]],
            "defer": domains.deferred_areas,
            "defer_guidance": (
                "Defer framework internals and vendor or generated code initially, where present; "
                "revisit them when a task requires it."
            ),
        },
        "business_domains": [asdict(item) for item in insights.domain_impacts],
        "critical_modules": [asdict(item) for item in insights.ranked_modules[:10]],
        "architecture": {
            "description": architecture.description,
            "system_type": architecture.system_type,
            "frameworks": architecture.frameworks,
            "languages": model.languages,
            "layers": [asdict(item) for item in architecture.layers],
            "components": [asdict(item) for item in architecture.components],
            "execution_flows": architecture.execution_flows,
            "observations": observations,
            "optional_integrations": architecture.optional_integrations,
        },
        "learning_path": first_week_onboarding_plan(insights),
        "workflows": [asdict(item) for item in narrative.workflows],
        "visualizations": [
            {"title": "Architecture relationships", "edges": relationships[:20],
             "omitted": max(0, len(relationships) - 20)},
            {"title": "Conceptual execution flow", "edges": flow_edges, "omitted": 0},
            {"title": "Workflow associations", "edges": workflow_edges[:20],
             "omitted": max(0, len(workflow_edges) - 20)},
        ],
        "artifacts": artifact_names,
    }
