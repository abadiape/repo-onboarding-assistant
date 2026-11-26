"""Prioritize domain-discovery findings for actionable developer onboarding."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath

from models.architecture_model import ArchitectureModel
from analyzers.domain_discovery import BusinessCapability, DomainDiscovery


_HIGH_IMPACT_DOMAINS = {
    "Payments", "Orders", "Inventory", "ERP Integrations", "Shipping",
}
_DOMAIN_RATIONALES = {
    "Payments": "Payment and transaction customizations can affect revenue collection.",
    "Orders": "Order capture and lifecycle workflows are central commerce operations.",
    "Inventory": "Stock availability can affect purchasability and fulfillment.",
    "ERP Integrations": "External synchronization can affect order and inventory operations.",
    "Shipping": "Fulfillment and delivery workflows affect order completion.",
}
_IMPORTANCE_RANK = {"Very High": 4, "High": 3, "Medium": 2, "Low": 1}
_IMPACT_RANK = {"High": 3, "Medium": 2, "Low": 1}
_MODULE_TIER_RANK = {"Business Critical": 3, "Important": 2, "Supporting": 1}
_MAX_CRITICAL_MODULES = 10
_SOURCE_SUFFIXES = {".cs", ".go", ".java", ".js", ".php", ".py", ".rb", ".rs", ".ts"}


@dataclass
class DomainImpact:
    name: str
    confidence: float
    business_impact: str
    onboarding_importance: str
    rationale: str
    modules: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)


@dataclass
class ModulePriority:
    name: str
    path: str
    tier: str
    confidence: float
    business_impact: str
    domains: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class BusinessInsights:
    domain_impacts: list[DomainImpact] = field(default_factory=list)
    capabilities: list[BusinessCapability] = field(default_factory=list)
    ranked_modules: list[ModulePriority] = field(default_factory=list)
    critical_integrations: list[dict[str, str | list[str]]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _domain_confidence(
    has_documentation: bool,
    source_evidence_count: int,
    module_count: int,
    integration_count: int,
) -> float:
    score = 0.25 + (0.05 if has_documentation else 0)
    score += (0.20 + min(module_count - 1, 3) * 0.05) if module_count else 0
    score += min(source_evidence_count, 3) * 0.10
    score += 0.25 if integration_count else 0
    return round(min(score, 0.95), 2)


def analyze_business_insights(
    architecture: ArchitectureModel, domains: DomainDiscovery
) -> BusinessInsights:
    """Score evidence-backed domain value and rank custom modules for onboarding."""
    architecture_integrations = {
        item.casefold() for item in architecture.external_dependencies
    }
    domain_impacts = []
    for domain in domains.domains:
        related_integrations = [
            item.name for item in domains.integrations
            if domain.name in item.domains
            and item.name.casefold() in architecture_integrations
        ]
        source_evidence_count = sum(
            PurePosixPath(evidence).suffix.casefold() in _SOURCE_SUFFIXES
            for evidence in domain.evidence
        )
        has_direct_evidence = bool(
            domain.modules or related_integrations or source_evidence_count
        )
        impact = (
            "High" if has_direct_evidence and domain.name in _HIGH_IMPACT_DOMAINS
            else "Medium" if has_direct_evidence else "Low"
        )
        importance = (
            "Very High" if impact == "High" and domain.modules
            else "High" if impact == "High" or domain.modules or related_integrations
            else "Medium" if impact == "Medium" else "Low"
        )
        rationale = _DOMAIN_RATIONALES.get(
            domain.name,
            "This business area may shape customer-facing or operational behavior.",
        )
        if not has_direct_evidence:
            rationale = (
                "This term appears in documentation, but no matching custom module, "
                "source path, or configured integration was found."
            )
        domain_impacts.append(DomainImpact(
            name=domain.name,
            confidence=_domain_confidence(
                bool(domain.evidence),
                source_evidence_count,
                len(domain.modules),
                len(related_integrations),
            ),
            business_impact=impact,
            onboarding_importance=importance,
            rationale=rationale,
            modules=sorted(domain.modules, key=str.casefold),
            integrations=sorted(related_integrations, key=str.casefold),
        ))
    domain_impacts.sort(key=lambda item: (
        -_IMPORTANCE_RANK[item.onboarding_importance],
        -_IMPACT_RANK[item.business_impact],
        item.name.casefold(),
    ))
    impact_by_name = {item.name: item for item in domain_impacts}

    module_priorities = []
    for module in domains.custom_modules:
        owners = [
            impact_by_name[domain_name]
            for domain_name in impact_by_name
            if module.name in impact_by_name[domain_name].modules
        ]
        owners.sort(key=lambda item: (
            -_IMPORTANCE_RANK[item.onboarding_importance],
            -_IMPACT_RANK[item.business_impact],
            item.name.casefold(),
        ))
        domain_names = [item.name for item in owners]
        impact = owners[0].business_impact if owners else "Low"
        confidence = max((item.confidence for item in owners), default=0.35)
        if impact == "High" and owners[0].onboarding_importance == "Very High":
            tier = "Business Critical"
        elif owners:
            tier = "Important"
        else:
            tier = "Supporting"
        rationale = (
            "; ".join(
                f"Matched to {item.name}: {item.rationale}"
                for item in owners[:2]
            )
            if owners else
            "No strong business-domain match was inferred; defer until a workflow leads here."
        )
        module_priorities.append(ModulePriority(
            name=module.name,
            path=module.path,
            tier=tier,
            confidence=confidence,
            business_impact=impact,
            domains=domain_names,
            rationale=rationale,
        ))
    module_priorities.sort(key=lambda item: (
        -_MODULE_TIER_RANK[item.tier],
        -item.confidence,
        item.name.casefold(),
    ))
    capability_rank = {"high": 0, "medium": 1, "low": 2}
    capabilities = sorted(
        [
            BusinessCapability(
                name=capability.name,
                domains=capability.domains,
                modules=capability.modules,
                evidence=capability.evidence,
                priority=(
                    "high" if capability.modules or any(
                        impact_by_name.get(name)
                        and impact_by_name[name].onboarding_importance in {"Very High", "High"}
                        for name in capability.domains
                    )
                    else "medium" if any(
                        impact_by_name.get(name)
                        and impact_by_name[name].business_impact == "Medium"
                        for name in capability.domains
                    )
                    else "low"
                ),
            )
            for capability in domains.capabilities
        ],
        key=lambda item: (capability_rank.get(item.priority, 3), item.name.casefold()),
    )

    critical_integrations = []
    for integration in domains.integrations:
        if integration.name.casefold() not in architecture_integrations:
            continue
        related_domains = [
            domain for domain in integration.domains if domain in impact_by_name
        ]
        integration_priority = (
            "Business Critical"
            if any(impact_by_name[name].business_impact == "High" for name in related_domains)
            else "Important" if related_domains else "Supporting"
        )
        if integration_priority == "Business Critical":
            critical_integrations.append({
                "name": integration.name,
                "priority": integration_priority,
                "domains": related_domains,
                "ownership_boundary": integration.ownership_boundary,
            })

    recommendations = []
    for domain in domain_impacts:
        if domain.onboarding_importance in {"Very High", "High"}:
            modules = ", ".join(domain.modules[:3])
            integrations = ", ".join(domain.integrations[:2])
            focus = "; ".join(
                part for part in (
                    f"review {modules}" if modules else "",
                    f"trace {integrations}" if integrations else "",
                ) if part
            )
            recommendations.append(
                f"Prioritize {domain.name}{': ' + focus if focus else ''}."
            )
    for capability in [item for item in capabilities if item.priority != "low"][:3]:
        recommendations.append(
            f"Trace {capability.name} across "
            f"{', '.join(capability.domains) or 'its inferred application boundaries'}."
        )
    if not recommendations:
        recommendations.append(
            "Start with the README and ask a maintainer which business workflows are most active."
        )
    recommendations.append(
        "Treat impact and confidence as heuristic signals; confirm critical paths and ownership with maintainers."
    )

    return BusinessInsights(
        domain_impacts=domain_impacts,
        capabilities=capabilities,
        ranked_modules=module_priorities,
        critical_integrations=critical_integrations,
        recommendations=recommendations,
    )


def render_executive_summary_markdown(
    architecture: ArchitectureModel, insights: BusinessInsights
) -> str:
    high_value = [
        item for item in insights.domain_impacts
        if item.business_impact == "High"
    ][:4]
    top_modules = insights.ranked_modules[:3]
    description = architecture.description.strip() or (
        f"{architecture.system_name} is a {architecture.system_type} repository."
    )
    lines = [
        f"# Executive Summary — {architecture.system_name}",
        "",
        description,
        "",
        "## Where business value appears concentrated",
        "",
    ]
    if high_value:
        lines += [
            f"- **{item.name}** — {item.rationale} "
            f"(onboarding importance: {item.onboarding_importance}; "
            f"evidence confidence: {item.confidence:.0%}, heuristic)"
            for item in high_value
        ]
    else:
        lines.append(
            "No high-impact domain was confidently inferred; validate business priorities with a maintainer."
        )
    lines += ["", "## Recommended first focus", ""]
    if top_modules:
        lines += [
            f"{index}. **{module.name}** — {', '.join(module.domains) or 'custom application code'}."
            for index, module in enumerate(top_modules, 1)
        ]
    else:
        lines.append("Start with the repository overview and ask which workflows are most important.")
    if insights.critical_integrations:
        lines += [
            "",
            "Critical integration boundaries: "
            + ", ".join(item["name"] for item in insights.critical_integrations[:4]),
        ]
    lines += [
        "",
        "Scores summarize repository evidence, not measured revenue or calibrated probabilities. "
        "Confirm operational importance and ownership with maintainers.",
        "",
    ]
    return "\n".join(lines)


def render_critical_modules_markdown(insights: BusinessInsights) -> str:
    if not insights.ranked_modules:
        return "# Critical Modules\n\nNo custom modules were identified.\n"
    modules = insights.ranked_modules[:_MAX_CRITICAL_MODULES]
    lines = [
        "# Critical Modules",
        "",
        f"Top {len(modules)} modules ranked by inferred business impact and onboarding importance. "
        "The complete module inventory remains in `domain_map.json`.",
        "",
    ]
    for tier in ("Business Critical", "Important", "Supporting"):
        matching = [module for module in modules if module.tier == tier]
        if not matching:
            continue
        lines += [f"## {tier}", ""]
        for module in matching:
            lines += [
                f"### {module.name}",
                "",
                f"- **Domain ownership:** {', '.join(module.domains) or 'Unassigned'}",
                f"- **Business impact:** {module.business_impact}",
                f"- **Evidence confidence:** {module.confidence:.0%} (heuristic)",
                f"- **Rationale:** {module.rationale}",
                "",
            ]
    omitted = len(insights.ranked_modules) - len(modules)
    if omitted:
        lines += [
            f"{omitted} additional modules are omitted from this summary; consult `domain_map.json` when a task requires them.",
            "",
        ]
    return "\n".join(lines)


def render_first_week_onboarding_markdown(insights: BusinessInsights) -> str:
    actionable_domains = [
        item for item in insights.domain_impacts
        if item.onboarding_importance in {"Very High", "High"}
    ]
    selected_domains = actionable_domains[:3]
    top_modules = insights.ranked_modules[:_MAX_CRITICAL_MODULES]
    high_value_modules = [
        item.name for item in top_modules if item.tier == "Business Critical"
    ]
    day_two = selected_domains[0] if selected_domains else None
    day_three = selected_domains[1] if len(selected_domains) > 1 else None
    day_four = selected_domains[2] if len(selected_domains) > 2 else None
    days = [
        {
            "title": "Product context and system boundary",
            "detail": (
                "Read the executive summary and confirm the product’s primary users, "
                "revenue flows, and deployment context with a maintainer."
            ),
        },
        {
            "title": f"Review {day_two.name}" if day_two else "Identify the main business capability",
            "detail": (
                f"Understand why this {day_two.business_impact.lower()}-impact domain matters; "
                f"start with {', '.join(day_two.modules[:3]) or 'the modules listed for this domain'}."
                if day_two else
                "Use the README and ask a maintainer to name the primary customer or operational workflow."
            ),
        },
    ]
    if insights.critical_integrations:
        integration = insights.critical_integrations[0]
        integration_detail = (
            f"Follow {integration['name']} across the "
            f"{', '.join(integration['domains']) or 'application'} boundary. "
            "Confirm runtime activation and ownership before changing behavior."
        )
        if day_three:
            integration_detail += (
                f" Then review {day_three.name}: "
                f"{', '.join(day_three.modules[:3]) or 'see the domain map'}."
            )
        days.append({
            "title": "Trace a critical integration",
            "detail": integration_detail,
        })
    elif day_three:
        days.append({
            "title": f"Understand {day_three.name}",
            "detail": (
                f"Review its business responsibilities and customizations: "
                f"{', '.join(day_three.modules[:3]) or 'see the domain map'}."
            ),
        })
    else:
        days.append({
            "title": "Clarify ownership and change boundaries",
            "detail": (
                "Choose one feature and ask who owns its behavior, which downstream systems it affects, "
                "and how its changes are verified."
            ),
        })
    if day_four:
        days.append({
            "title": f"Understand {day_four.name}",
            "detail": (
                f"Review its responsibilities and customizations: "
                f"{', '.join(day_four.modules[:3]) or 'see the domain map'}."
            ),
        })
    else:
        days.append({
            "title": "Review verification and delivery",
            "detail": "Run the documented tests and inspect how CI or deployment validates the workflows you reviewed.",
        })
    workflow_detail = (
        "Trace an end-to-end capability through its domain modules and integration boundaries."
    )
    actionable_capabilities = [
        item for item in insights.capabilities if item.priority != "low"
    ]
    if actionable_capabilities:
        workflow_detail = (
            "Trace " + ", ".join(item.name for item in actionable_capabilities[:3])
            + " through its domain modules and integration boundaries."
        )
    remaining = [item.name for item in selected_domains[3:]]
    if remaining:
        workflow_detail = f"Also orient on {', '.join(remaining[:3])}. " + workflow_detail
    if high_value_modules:
        workflow_detail += " Begin with " + ", ".join(high_value_modules[:3]) + "."
    workflow_detail += " Run the project’s documented tests before making a change."
    days.append({
        "title": "Follow a business workflow end to end",
        "detail": workflow_detail,
    })
    lines = [
        "# First-Week Onboarding",
        "",
        "A practical five-day plan focused on business value, custom logic, and integration boundaries.",
        "",
    ]
    for index, day in enumerate(days, 1):
        lines += [f"## Day {index}: {day['title']}", "", day["detail"], ""]
    return "\n".join(lines)


def render_business_insights_markdown(insights: BusinessInsights) -> str:
    lines = [
        "# Business Insights",
        "",
        "These insights summarize patterns in names, ownership boundaries, and architecture evidence; "
        "they are hypotheses to validate, not operational measurements.",
        "",
    ]
    high_domains = [
        item for item in insights.domain_impacts
        if item.business_impact == "High"
    ][:5]
    if high_domains:
        lines += ["## Highest-value areas to understand", ""]
        for domain in high_domains:
            module_names = ", ".join(domain.modules[:4]) or "No matching custom module identified"
            integration_names = ", ".join(domain.integrations[:3])
            integration_detail = (
                f" Inferred integration boundary: {integration_names}."
                if integration_names else ""
            )
            lines.append(
                f"- **{domain.name}** is an inferred high-impact area. "
                f"Matched custom modules: {module_names}.{integration_detail} "
                f"Onboarding importance is {domain.onboarding_importance} "
                f"with {domain.confidence:.0%} evidence confidence."
            )
        lines.append("")
    if insights.critical_integrations:
        lines += ["## Business-critical integrations", ""]
        for integration in insights.critical_integrations[:5]:
            domain_list = ", ".join(integration["domains"]) or "unassigned domain"
            lines.append(
                f"- **{integration['name']}** crosses an inferred {integration['ownership_boundary']} "
                f"boundary and is associated with {domain_list}. Confirm its runtime use and owner."
            )
        lines.append("")
    actionable_capabilities = [
        item for item in insights.capabilities if item.priority != "low"
    ]
    if actionable_capabilities:
        lines += ["## Business capabilities to trace", ""]
        for capability in actionable_capabilities[:5]:
            domains = ", ".join(capability.domains) or "domain not confidently assigned"
            modules = ", ".join(capability.modules[:4]) or "follow the relevant workflow"
            lines.append(f"- **{capability.name}** ({domains}): start with {modules}.")
        lines.append("")
    lines += ["## Recommendations", ""]
    lines += [f"- {recommendation}" for recommendation in insights.recommendations[:6]]
    lines += [
        "",
        "## Scoring guide",
        "",
        "Confidence estimates how much repository evidence supports a finding. "
        "Business impact describes the likely consequence of changing the area; "
        "onboarding importance determines learning order. They are separate heuristic ratings.",
        "",
    ]
    return "\n".join(lines)
