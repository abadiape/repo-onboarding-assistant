"""Narrative generation."""
# Explicit aliases preserve the original import paths.
# ruff: noqa: PLC0414
from __future__ import annotations

from analyzers.narrative_workflows import (
    _FLOW_ORDER,
    _business_flow,
    _domain_interactions,
    _first_week_plan,
)
from analyzers.technical_onboarding import repository_purpose
from artifacts.narrative_business_reports import (
    render_business_story_markdown as render_business_story_markdown,
)
from artifacts.narrative_business_reports import (
    render_critical_workflows_markdown as render_critical_workflows_markdown,
)
from artifacts.narrative_business_reports import (
    render_first_week_story_markdown as render_first_week_story_markdown,
)
from artifacts.narrative_repository_reports import (
    render_business_risk_story_markdown as render_business_risk_story_markdown,
)
from artifacts.narrative_repository_reports import (
    render_first_day_briefing_markdown as render_first_day_briefing_markdown,
)
from artifacts.narrative_repository_reports import (
    render_repository_story_markdown as render_repository_story_markdown,
)
from models.architecture_model import ArchitectureModel
from models.business_insights import BusinessInsights, DomainImpact
from models.business_narrative import BusinessNarrative as BusinessNarrative
from models.business_narrative import DomainInteraction as DomainInteraction
from models.business_narrative import NarrativeCustomization as NarrativeCustomization
from models.business_narrative import NarrativeWorkflow as NarrativeWorkflow
from models.domain_discovery import BusinessCapability, DomainDiscovery
from models.models import RepositoryModel
from models.repository_archetype import ArchetypeResult, RepositoryArchetype


def generate_business_narrative(
    architecture: ArchitectureModel,
    domains: DomainDiscovery,
    insights: BusinessInsights,
    archetype: ArchetypeResult | None = None,
    model: RepositoryModel | None = None,
) -> BusinessNarrative:
    """Turn existing findings into a concise, evidence-grounded onboarding story."""
    if archetype is not None and archetype.archetype != RepositoryArchetype.BUSINESS_APPLICATION:
        if model is None:
            raise ValueError("A repository model is required for technical narratives")
        purpose = repository_purpose(model, f"Explore {model.repository_name} using its repository evidence.")
        return BusinessNarrative(
            system_name=architecture.system_name,
            system_purpose=purpose,
            differentiators=[
                f"{item['title']}: {', '.join(str(path) for path in item['evidence'])}"
                for item in insights.technical_topics
            ],
            recommendations=insights.recommendations,
            first_week=[(f"Day {i}: {step['title']}", step["detail"]) for i, step in enumerate(insights.learning_plan, 1)],
        )
    primary_domains = [
        domain for domain in insights.domain_impacts
        if domain.modules or domain.integrations
    ][:8]
    customizations = _prioritized_customizations(domains, insights)
    actionable_capabilities = [
        capability for capability in insights.capabilities
        if capability.priority != "low"
    ][:6]

    flow_domain_names = {
        domain.name for domain in primary_domains
    }
    for capability in actionable_capabilities:
        flow_domain_names.update(capability.domains)
    flow_domains = sorted(
        flow_domain_names,
        key=lambda name: (_FLOW_ORDER.get(name, len(_FLOW_ORDER)), name.casefold()),
    )

    workflows = [
        NarrativeWorkflow(
            name=capability.name,
            purpose=_capability_workflow_purpose(capability),
            domains=list(capability.domains),
            modules=list(capability.modules),
            onboarding_significance=(
                "High" if capability.priority == "high" else "Medium"
            ),
        )
        for capability in actionable_capabilities
    ]

    purpose = _repository_interpretation(
        architecture, primary_domains, customizations
    )
    business_flow = _business_flow(
        flow_domains, primary_domains, insights
    )
    first_week = _first_week_plan(primary_domains, workflows)
    return BusinessNarrative(
        system_name=architecture.system_name,
        system_purpose=purpose,
        core_flow_domains=flow_domains,
        core_flow_capabilities=[
            capability.name for capability in actionable_capabilities
        ],
        primary_domains=primary_domains,
        domain_interactions=_domain_interactions(insights),
        differentiators=_repository_differentiators(
            domains, primary_domains, insights
        ),
        customized_domains=sorted(
            (item for item in primary_domains if item.modules),
            key=lambda item: (-len(item.modules), item.name.casefold()),
        )[:5],
        narrative_insights=_narrative_insights(primary_domains, insights),
        business_flow=business_flow,
        notable_patterns=architecture.detected_patterns[:5],
        customizations=customizations,
        workflows=workflows,
        critical_integrations=insights.critical_integrations[:5],
        recommendations=insights.recommendations[:5],
        first_week=first_week,
    )


def _capability_workflow_purpose(capability: BusinessCapability) -> str:
    evidence = []
    if capability.domains:
        evidence.append("domains " + ", ".join(capability.domains))
    if capability.modules:
        evidence.append(
            "modules " + ", ".join(f"`{name}`" for name in capability.modules[:4])
        )
    if evidence:
        return (
            f"The scan associates {capability.name} with "
            + " and ".join(evidence)
            + ". Trace these components to understand the repository's implementation."
        )
    return (
        f"The repository identifies {capability.name} as a business capability, "
        "but did not match it to a specific domain or module."
    )


def _repository_interpretation(
    architecture: ArchitectureModel,
    domains: list[DomainImpact],
    customizations: list[NarrativeCustomization],
) -> str:
    areas = [
        f"{domain.name} ({', '.join(domain.modules[:3])})"
        for domain in domains
        if domain.modules
    ][:4]
    platform = ", ".join(architecture.frameworks[:2]) or architecture.system_type
    if areas:
        module_count = len(customizations)
        areas_text = "; ".join(areas)
        return (
            f"This {platform} implementation appears to concentrate custom business "
            f"behavior in {areas_text}. The analyzer prioritized {module_count} "
            "representative customizations for onboarding; trace these modules to "
            "understand how this repository extends its platform."
        )
    if customizations:
        examples = ", ".join(f"`{item.name}`" for item in customizations[:4])
        return (
            f"This {platform} repository contains project-owned customizations, "
            f"including {examples}, but their business domains were not confidently "
            "matched by the current findings."
        )
    return (
        f"The available architecture findings describe a {architecture.system_type} "
        "repository, but do not yet identify repository-specific business behavior. "
        "Use the repository overview as context and confirm the active workflows "
        "with a maintainer."
    )


def _narrative_insights(
    domains: list[DomainImpact], insights: BusinessInsights
) -> list[str]:
    capabilities_by_domain: dict[str, list[str]] = {}
    for capability in insights.capabilities:
        for domain in capability.domains:
            capabilities_by_domain.setdefault(domain, []).append(capability.name)

    observations = []
    for domain in domains:
        if not domain.modules and not domain.integrations:
            continue
        evidence = []
        if domain.modules:
            evidence.append(
                f"custom modules {', '.join(f'`{name}`' for name in domain.modules[:4])}"
            )
        if domain.integrations:
            evidence.append(
                f"configured integrations {', '.join(f'`{name}`' for name in domain.integrations[:3])}"
            )
        capabilities = capabilities_by_domain.get(domain.name, [])
        capability_detail = (
            f" Related discovered capabilities include {', '.join(capabilities[:3])}."
            if capabilities else ""
        )
        starting_point = (
            f" {domain.starting_module} is the suggested starting module."
            if domain.starting_module else ""
        )
        observations.append(
            f"{domain.name} has repository-specific evidence: "
            + " and ".join(evidence)
            + f". It is rated {domain.business_impact} impact by the onboarding "
            f"heuristic.{capability_detail}{starting_point}"
        )
    return observations[:6]


def _prioritized_customizations(
    discovery: DomainDiscovery, insights: BusinessInsights
) -> list[NarrativeCustomization]:
    discovered_modules = {module.name: module for module in discovery.custom_modules}
    ranked = [item for item in insights.ranked_modules if item.tier != "Supporting"]
    if not ranked:
        ranked = insights.ranked_modules

    customizations = []
    for item in ranked[:5]:
        discovered = discovered_modules.get(item.name)
        domains = item.domains
        capabilities = [
            capability.name for capability in insights.capabilities
            if item.name in capability.modules
        ][:3]
        if domains:
            associations = [", ".join(domains)]
            if capabilities:
                associations.append(", ".join(capabilities))
            explanation = (
                f"Discovery matches this module to {', '.join(associations)}. "
                "It is an evidence-backed starting point for these workflows; "
                "confirm its runtime role with a maintainer."
            )
        else:
            explanation = (
                "This module is in the discovered project-owned inventory, but no "
                "business domain was confidently matched. Follow a relevant change "
                "or ask a maintainer before assigning it a business role."
            )
        customizations.append(NarrativeCustomization(
            name=item.name,
            path=item.path,
            domains=domains,
            capabilities=capabilities,
            owner=discovered.owner if discovered else None,
            explanation=explanation,
        ))
    return customizations


def _repository_differentiators(
    discovery: DomainDiscovery,
    primary_domains: list[DomainImpact],
    insights: BusinessInsights,
) -> list[str]:
    differentiators = []
    if primary_domains:
        strongest = primary_domains[0]
        modules = ", ".join(f"`{name}`" for name in strongest.modules[:4])
        differentiators.append(
            f"{strongest.name} is the highest-priority discovered business area"
            + (f", with repository modules including {modules}." if modules else ".")
        )
    if discovery.custom_modules:
        names = ", ".join(
            f"`{module.name}`" for module in insights.ranked_modules[:4]
        )
        differentiators.append(
            f"The repository contains {len(discovery.custom_modules)} project-owned "
            "modules or business areas"
            + (f"; prioritized examples include {names}." if names else ".")
        )
    integrations = list(dict.fromkeys(
        name
        for domain in primary_domains
        for name in domain.integrations
    ))
    if integrations:
        differentiators.append(
            "Configured integration evidence connects business areas to "
            + ", ".join(f"`{name}`" for name in integrations[:4]) + "."
        )
    if not differentiators:
        differentiators.append(
            "The available findings do not establish repository-specific business "
            "differentiators; start with documented project behavior and confirm it "
            "with a maintainer."
        )
    return differentiators
