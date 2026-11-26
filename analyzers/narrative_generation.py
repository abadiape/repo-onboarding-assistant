"""Synthesize onboarding narratives from architecture and business findings."""
from __future__ import annotations

from dataclasses import dataclass, field

from analyzers.business_insights import BusinessInsights, DomainImpact
from analyzers.domain_discovery import BusinessCapability, DomainDiscovery
from models.architecture_model import ArchitectureModel


_FLOW_ORDER = {
    name: index for index, name in enumerate((
        "Customer Experience",
        "Catalog",
        "Search",
        "Orders",
        "Payments",
        "ERP Integrations",
        "Inventory",
        "Shipping",
        "Marketing",
        "Loyalty",
    ))
}


@dataclass
class NarrativeWorkflow:
    name: str
    purpose: str
    domains: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    onboarding_significance: str = "Medium"


@dataclass
class DomainInteraction:
    domains: list[str]
    evidence: list[str] = field(default_factory=list)


@dataclass
class NarrativeCustomization:
    name: str
    path: str
    domains: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    owner: str | None = None
    explanation: str = ""


@dataclass
class BusinessNarrative:
    system_name: str
    system_purpose: str
    core_flow_domains: list[str] = field(default_factory=list)
    core_flow_capabilities: list[str] = field(default_factory=list)
    primary_domains: list[DomainImpact] = field(default_factory=list)
    domain_interactions: list[DomainInteraction] = field(default_factory=list)
    differentiators: list[str] = field(default_factory=list)
    customized_domains: list[DomainImpact] = field(default_factory=list)
    narrative_insights: list[str] = field(default_factory=list)
    business_flow: str = ""
    notable_patterns: list[str] = field(default_factory=list)
    customizations: list[NarrativeCustomization] = field(default_factory=list)
    workflows: list[NarrativeWorkflow] = field(default_factory=list)
    critical_integrations: list[dict[str, str | list[str]]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    first_week: list[tuple[str, str]] = field(default_factory=list)


def generate_business_narrative(
    architecture: ArchitectureModel,
    domains: DomainDiscovery,
    insights: BusinessInsights,
) -> BusinessNarrative:
    """Turn existing findings into a concise, evidence-grounded onboarding story."""
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


def _business_flow(
    flow_domains: list[str],
    primary_domains: list[DomainImpact],
    insights: BusinessInsights,
) -> str:
    if not flow_domains:
        return (
            "No cross-domain business flow can be grounded in the current findings; "
            "ask a maintainer to trace a representative user or operational journey."
        )
    domains_by_name = {domain.name: domain for domain in primary_domains}
    capabilities_by_domain: dict[str, list[str]] = {}
    modules_by_domain: dict[str, list[str]] = {}
    for capability in insights.capabilities:
        for domain in capability.domains:
            capabilities_by_domain.setdefault(domain, []).append(capability.name)
            modules_by_domain.setdefault(domain, []).extend(capability.modules)

    phrases = []
    for name in flow_domains:
        domain = domains_by_name.get(name)
        modules = list(dict.fromkeys(
            (domain.modules if domain else []) + modules_by_domain.get(name, [])
        ))[:3]
        module_detail = (
            " through customizations such as "
            + ", ".join(f"`{module}`" for module in modules)
            if modules else ""
        )
        phrases.append(_domain_flow_phrase(name, module_detail))
    return (
        "The discovered areas suggest that customers may "
        + "; then ".join(phrases)
        + ". This is a conceptual narrative assembled from domain and module matches, "
        "not proof of runtime sequence."
    )


def _domain_flow_phrase(domain: str, module_detail: str) -> str:
    descriptions = {
        "Customer Experience": "use account and registration features",
        "Catalog": "browse product information",
        "Search": "find products and content",
        "Orders": "create and manage orders",
        "Payments": "complete payment",
        "ERP Integrations": "synchronize business data with ERP systems",
        "Inventory": "check or update stock availability",
        "Shipping": "coordinate delivery and fulfillment",
        "Marketing": "encounter promotions and campaigns",
        "Loyalty": "use rewards and loyalty features",
    }
    activity = descriptions.get(domain, f"interact with {domain.lower()} functionality")
    return f"{activity}{module_detail}"


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


def _domain_learning_advice(domain: DomainImpact) -> str:
    subjects = {
        "Payments": "how payment behavior is implemented",
        "Orders": "how orders are created and managed",
        "ERP Integrations": "how business data is synchronized with ERP systems",
        "Inventory": "how stock availability is managed",
        "Shipping": "how delivery and fulfillment are coordinated",
        "Customer Experience": "how customer registration and accounts work",
        "Catalog": "how product information is customized",
        "Search": "how customers find products and content",
        "Marketing": "how promotions and campaigns are implemented",
        "Loyalty": "how customer rewards are managed",
    }
    modules = list(dict.fromkeys(
        ([domain.starting_module] if domain.starting_module else [])
        + domain.learning_order
        + domain.modules
    ))[:2]
    subject = subjects.get(domain.name, domain.name.lower())
    if not modules:
        return (
            f"To understand {subject}, ask a maintainer for the relevant code entry "
            "point; no starting module was matched."
        )
    module_text = " and ".join(f"`{name}`" for name in modules)
    return (
        f"If you want to understand {subject}, start with {module_text}. "
        f"The scan associates these modules with {domain.name}."
    )


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


def _domain_interactions(insights: BusinessInsights) -> list[DomainInteraction]:
    interactions: dict[tuple[str, str], set[str]] = {}

    def connect(domains: list[str], reason: str) -> None:
        unique_domains = sorted(set(domains), key=str.casefold)
        for index, first in enumerate(unique_domains):
            for second in unique_domains[index + 1:]:
                interactions.setdefault((first, second), set()).add(reason)

    for capability in insights.capabilities:
        if capability.priority != "low" and len(capability.domains) > 1:
            connect(capability.domains, f"shared capability: {capability.name}")

    module_owners: dict[str, list[str]] = {}
    for domain in insights.domain_impacts:
        for module in domain.modules:
            module_owners.setdefault(module, []).append(domain.name)
    for module, owners in module_owners.items():
        if len(set(owners)) > 1:
            connect(owners, f"shared module: {module}")

    for integration in insights.critical_integrations:
        domains = integration["domains"]
        if isinstance(domains, list):
            connect(domains, f"shared integration: {integration['name']}")

    return [
        DomainInteraction(domains=list(domains), evidence=sorted(evidence))
        for domains, evidence in sorted(interactions.items())
    ]


def _first_week_plan(
    domains: list[DomainImpact], workflows: list[NarrativeWorkflow]
) -> list[tuple[str, str]]:
    days = [
        (
            "Day 1: Build the system map",
            "Read this story and the architecture overview. Confirm the main users, "
            "business purpose, and inferred value flow with a maintainer.",
        )
    ]
    for index, domain in enumerate(domains[:3], start=2):
        starting_point = (
            f"Start with `{domain.starting_module}`. "
            if domain.starting_module else
            "Ask a maintainer for the best code entry point. "
        )
        days.append((
            f"Day {index}: Understand {domain.name}",
            f"{starting_point}{domain.rationale} Trace one relevant capability and "
            "confirm the domain boundary with its maintainer.",
        ))

    if len(days) < 5:
        if workflows:
            workflow = workflows[0]
            days.append((
                f"Day {len(days) + 1}: Trace {workflow.name}",
                f"Follow the capability through {', '.join(workflow.domains) or 'its inferred application boundary'}. "
                f"Review {', '.join(f'`{name}`' for name in workflow.modules) or 'the relevant implementation'} "
                "and identify how the team verifies the behavior.",
            ))
        else:
            days.append((
                f"Day {len(days) + 1}: Find a representative change",
                "Ask a maintainer to walk through one recent business change and its tests.",
            ))
    while len(days) < 5:
        days.append((
            f"Day {len(days) + 1}: Validate the learning",
            "Trace a small behavior from its entry point to its outcome, run the "
            "documented tests, and confirm any assumptions with a maintainer.",
        ))
    return days[:5]


def render_business_story_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# Business Story — {narrative.system_name}",
        "",
        "## What This System Does",
        "",
        narrative.system_purpose,
        "",
        "## Core Business Flow",
        "",
    ]
    if narrative.core_flow_domains or narrative.core_flow_capabilities:
        flow = narrative.core_flow_domains or narrative.core_flow_capabilities
        lines += [
            "A useful inferred path for learning how value moves through this repository is:",
            "",
            " → ".join(flow),
        ]
        if narrative.core_flow_capabilities:
            lines += [
                "",
                "Related capabilities identified in the repository: "
                + ", ".join(narrative.core_flow_capabilities) + ".",
            ]
    else:
        lines.append(
            "The available findings do not establish a business flow. Start with the "
            "repository overview and ask a maintainer which workflow is most important."
        )
    lines += [
        "",
        "This is an onboarding hypothesis from discovered areas, not an observed runtime trace.",
        "",
        "## Primary Domains",
        "",
    ]
    if narrative.primary_domains:
        for domain in narrative.primary_domains:
            modules = ", ".join(f"`{name}`" for name in domain.modules[:4])
            lines.append(
                f"- **{domain.name}** — {domain.description} "
                f"Impact: {domain.business_impact}; onboarding priority: "
                f"{domain.onboarding_importance}."
                + (f" Start with {modules}." if modules else "")
            )
    else:
        lines.append("No directly supported business domain was identified.")
    lines += ["", "## How Domains Connect", ""]
    if narrative.domain_interactions:
        lines += [
            "The following links are supported by a shared capability, module, or "
            "business-critical integration; they do not prove runtime call order.",
            "",
        ]
        for interaction in narrative.domain_interactions:
            lines.append(
                f"- **{' ↔ '.join(interaction.domains)}** — "
                + "; ".join(interaction.evidence)
                + "."
            )
    else:
        lines.append(
            "The current findings do not establish direct links between business domains. "
            "Confirm cross-domain handoffs with a maintainer."
        )
    lines += ["", "## Critical Integrations", ""]
    if narrative.critical_integrations:
        for integration in narrative.critical_integrations:
            domains = ", ".join(integration["domains"]) or "no assigned domain"
            lines.append(
                f"- **{integration['name']}** — associated with {domains}. "
                "Confirm runtime use and ownership with a maintainer."
            )
    else:
        lines.append(
            "No specific business-critical external integration was identified in the "
            "existing findings; confirm integration boundaries with a maintainer."
        )
    lines += ["", "## What Matters Most", ""]
    if narrative.recommendations:
        lines.extend(f"- {item}" for item in narrative.recommendations)
    else:
        lines.append("Start with the README and ask which workflows are most active.")
    lines += [
        "",
        "Impact and priority are heuristic onboarding signals, not measured business "
        "risk or revenue. Validate critical paths and ownership with the team.",
        "",
    ]
    return "\n".join(lines)


def render_critical_workflows_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# Critical Workflows — {narrative.system_name}",
        "",
        "These workflow guides are synthesized from discovered capabilities and their "
        "domain/module associations. The repository findings do not prove runtime call order.",
        "",
    ]
    if not narrative.workflows:
        lines.append(
            "No actionable business capability was identified. Ask a maintainer to name "
            "a workflow before tracing implementation details."
        )
    for workflow in narrative.workflows:
        lines += [
            f"## {workflow.name}",
            "",
            f"**Business purpose:** {workflow.purpose}",
            "",
            "**Involved domains:** "
            + (", ".join(workflow.domains) or "No domain confidently assigned"),
            "",
            "**Involved modules:** "
            + (", ".join(f"`{name}`" for name in workflow.modules)
               or "No matching custom module identified"),
            "",
            f"**Onboarding significance:** {workflow.onboarding_significance}.",
            "",
        ]
    return "\n".join(lines)


def render_first_week_story_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# First-Week Story — {narrative.system_name}",
        "",
        "A senior-developer-style learning sequence based on this repository's inferred "
        "business priorities. Confirm assumptions as you go.",
        "",
    ]
    for title, advice in narrative.first_week:
        lines += [f"## {title}", "", advice, ""]
    return "\n".join(lines)


def render_repository_story_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# Repository Story — {narrative.system_name}",
        "",
        "## What Makes This Repository Different",
        "",
        narrative.system_purpose,
        "",
    ]
    lines.extend(f"- {item}" for item in narrative.differentiators)
    if narrative.notable_patterns:
        lines += [
            "",
            "Detected architecture patterns: "
            + ", ".join(narrative.notable_patterns) + ".",
        ]
    lines += ["", "## What Appears Most Customized", ""]
    if narrative.customized_domains:
        for domain in narrative.customized_domains:
            modules = ", ".join(f"`{name}`" for name in domain.modules[:6])
            lines.append(
                f"- **{domain.name}** has {len(domain.modules)} matched project modules: "
                f"{modules}. These matches suggest where to "
                "start reading; they do not measure code volume or runtime traffic."
            )
    else:
        lines.append("No domain had enough direct module evidence to compare customization.")
    lines += ["", "## How Value Moves Through The System", ""]
    if narrative.business_flow:
        lines += [narrative.business_flow, ""]
    if narrative.core_flow_domains:
        domains_by_name = {domain.name: domain for domain in narrative.primary_domains}
        flow_steps = []
        for name in narrative.core_flow_domains:
            domain = domains_by_name.get(name)
            modules = domain.modules[:2] if domain else []
            flow_steps.append(
                f"{name} ({', '.join(modules)})" if modules else name
            )
        lines += [
            "A conceptual reading path, ordered from the current domain and capability "
            "findings (not an observed runtime sequence):",
            "",
            " → ".join(flow_steps),
        ]
        if narrative.core_flow_capabilities:
            lines += [
                "",
                "Capabilities associated with this path: "
                + ", ".join(narrative.core_flow_capabilities) + ".",
            ]
    else:
        lines.append(
            "The available evidence does not establish a cross-domain flow. Ask a "
            "maintainer to walk through a customer or operational journey."
        )
    lines += ["", "## Major Business Areas", ""]
    if narrative.primary_domains:
        for domain in narrative.primary_domains:
            components = []
            if domain.modules:
                components.append(
                    "repository modules: "
                    + ", ".join(f"`{name}`" for name in domain.modules[:5])
                )
            if domain.integrations:
                components.append(
                    "configured integrations: "
                    + ", ".join(f"`{name}`" for name in domain.integrations[:3])
                )
            detail = (
                " Evidence points to " + " and ".join(components) + "."
                if components else
                " No directly matched module or integration was identified."
            )
            start = (
                f" Begin exploration with `{domain.starting_module}`."
                if domain.starting_module else ""
            )
            lines.append(
                f"- **{domain.name}:** {domain.description}{detail}{start}"
            )
    else:
        lines.append("No directly supported business areas were identified.")
    lines += ["", "## What Appears Business Critical", ""]
    critical_domains = [
        domain for domain in narrative.primary_domains
        if domain.business_impact in {"Critical", "High"}
    ]
    if critical_domains:
        for domain in critical_domains:
            modules = ", ".join(f"`{name}`" for name in domain.modules[:4])
            lines.append(
                f"- **{domain.name}** is rated {domain.business_impact} by the "
                "onboarding heuristic"
                + (f" and is associated with {modules}." if modules else ".")
                + f" {domain.rationale}"
            )
    else:
        lines.append("No directly supported Critical or High business area was identified.")
    lines += ["", "## Repository-Specific Insights", ""]
    if narrative.narrative_insights:
        lines.extend(f"- {item}" for item in narrative.narrative_insights)
    else:
        lines.append("No repository-specific domain observations were supported by direct evidence.")
    lines += ["", "## Most Important Customizations", ""]
    if narrative.customizations:
        for module in narrative.customizations:
            ownership = f" Owner namespace: `{module.owner}`." if module.owner else ""
            lines.append(
                f"- **`{module.name}`** (`{module.path}`): {module.explanation}"
                f"{ownership}"
            )
    else:
        lines.append("No project-owned custom modules were ranked for onboarding.")
    lines += [
        "",
        "These associations are repository-derived onboarding hypotheses. Confirm "
        "module responsibilities, runtime activation, and workflow order with maintainers.",
        "",
    ]
    return "\n".join(lines)


def render_business_risk_story_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# Business Risk Story — {narrative.system_name}",
        "",
        "This is onboarding prioritization, not an operational risk assessment. "
        "The observations below describe inferred business sensitivity, not guarantees "
        "about production impact.",
        "",
    ]
    sensitive_domains = [
        domain for domain in narrative.primary_domains
        if domain.business_impact in {"Critical", "High"}
    ]
    if sensitive_domains:
        for domain in sensitive_domains:
            modules = (
                ", ".join(f"`{name}`" for name in domain.modules[:4])
                or "no matching custom module identified"
            )
            integration_note = (
                " Related configured integrations: "
                + ", ".join(f"`{name}`" for name in domain.integrations[:3]) + "."
                if domain.integrations else ""
            )
            lines.append(
                f"- **{domain.name}** is rated {domain.business_impact} by the "
                f"existing heuristic findings and is associated with {modules}."
                f"{integration_note} Review these paths carefully and confirm the "
                "actual business consequence with a maintainer."
            )
    else:
        lines.append(
            "No directly supported Critical or High business area was identified. "
            "Ask a maintainer which workflows require the most care."
        )
    lines += [
        "",
        "Treat the ratings and module associations as hypotheses. They are based on "
        "repository evidence and do not establish outage likelihood, revenue exposure, "
        "or runtime coupling.",
        "",
    ]
    return "\n".join(lines)


def render_first_day_briefing_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# First-Day Briefing — {narrative.system_name}",
        "",
        "A short first read. Use the linked maps and a maintainer conversation to verify "
        "these repository-derived hypotheses.",
        "",
        "## 1. What This Repository Appears to Do",
        "",
        narrative.system_purpose,
        "",
        "## 2. What Makes It Distinctive",
        "",
    ]
    lines.extend(f"- {item}" for item in narrative.differentiators[:3])
    if narrative.notable_patterns:
        lines.append(
            "- Detected architecture patterns: "
            + ", ".join(narrative.notable_patterns[:3]) + "."
        )
    lines += ["", "## 3. Important Business Areas and Workflows", ""]
    if narrative.primary_domains:
        for domain in narrative.primary_domains[:5]:
            matched_module_count = len(domain.modules)
            module_match_text = (
                "1 matched custom module"
                if matched_module_count == 1
                else f"{matched_module_count} matched custom modules"
            )
            lines.append(
                f"- **{domain.name}** — {domain.business_impact} business impact; "
                f"{module_match_text}."
            )
    else:
        lines.append("No business area has direct supporting evidence yet.")
    lines += ["", "## 4. Important Customizations", ""]
    if narrative.customizations:
        for module in narrative.customizations[:5]:
            lines.append(
                f"- **`{module.name}`** — {', '.join(module.domains) or 'business role unassigned'} "
                f"(`{module.path}`)."
            )
    else:
        lines.append("No project-owned customization was ranked.")
    lines += ["", "## 5. Recommended Learning Sequence", ""]
    if narrative.primary_domains:
        lines.extend(
            f"{index}. {_domain_learning_advice(domain)}"
            for index, domain in enumerate(narrative.primary_domains[:4], start=1)
        )
    else:
        lines.extend(
            f"{index}. {title.split(': ', 1)[-1]} — {advice}"
            for index, (title, advice) in enumerate(narrative.first_week[:3], start=1)
        )
    lines += [
        "",
        "Validate inferred roles and priorities with a maintainer before changing "
        "business-critical behavior.",
        "",
    ]
    return "\n".join(lines)
