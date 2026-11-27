"""Prioritize domain-discovery findings for actionable developer onboarding."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import PurePosixPath

from models.architecture_model import ArchitectureModel
from analyzers.domain_discovery import BusinessCapability, DomainDiscovery, _tokens
from models.models import RepositoryModel
from models.repository_archetype import ArchetypeResult, RepositoryArchetype
from analyzers.technical_onboarding import technical_plan, technical_topics


_DOMAIN_IMPACTS = {
    "Payments": "Critical",
    "Orders": "Critical",
    "Inventory": "High",
    "ERP Integrations": "High",
    "Shipping": "High",
    "Customer Experience": "High",
}
_DOMAIN_RATIONALES = {
    "Payments": "Payment and transaction customizations can affect revenue collection.",
    "Orders": "Order capture and lifecycle workflows are central commerce operations.",
    "Inventory": "Stock availability can affect purchasability and fulfillment.",
    "ERP Integrations": "External synchronization can affect order and inventory operations.",
    "Shipping": "Fulfillment and delivery workflows affect order completion.",
    "Customer Experience": "Customer accounts and registration affect access and retention.",
    "Catalog": "Product information influences what customers can find and purchase.",
    "Marketing": "Promotions and campaigns can influence customer acquisition and sales.",
    "Search": "Search helps customers discover relevant products and content.",
    "Loyalty": "Rewards can encourage customer retention and repeat purchases.",
}
_IMPORTANCE_RANK = {"Very High": 4, "High": 3, "Medium": 2, "Low": 1}
_IMPACT_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
_MODULE_TIER_RANK = {"Business Critical": 3, "Important": 2, "Supporting": 1}
_DOMAIN_ORDER = {
    name: index for index, name in enumerate(
        ("Payments", "Orders", "ERP Integrations", "Inventory", "Shipping", "Customer Experience")
    )
}
_SUPPORTING_MODULE_TOKENS = {
    "attribute", "attributes", "clean", "cleanup", "mail", "price", "schedule", "trigger",
}
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
    description: str = ""
    starting_module: str | None = None
    learning_order: list[str] = field(default_factory=list)
    learning_recommendation: str = ""


@dataclass
class ModulePriority:
    name: str
    path: str
    tier: str
    confidence: float
    business_impact: str
    domains: list[str] = field(default_factory=list)
    rationale: str = ""
    recommendation: str = ""


@dataclass
class BusinessInsights:
    domain_impacts: list[DomainImpact] = field(default_factory=list)
    capabilities: list[BusinessCapability] = field(default_factory=list)
    ranked_modules: list[ModulePriority] = field(default_factory=list)
    critical_integrations: list[dict[str, str | list[str]]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    learning_plan: list[dict[str, str]] = field(default_factory=list)
    technical_topics: list[dict[str, object]] = field(default_factory=list)

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
    architecture: ArchitectureModel, domains: DomainDiscovery,
    archetype: ArchetypeResult | None = None, model: RepositoryModel | None = None,
) -> BusinessInsights:
    """Score evidence-backed domain value and rank custom modules for onboarding."""
    if archetype is not None and archetype.archetype != RepositoryArchetype.BUSINESS_APPLICATION:
        if model is None:
            raise ValueError("A repository model is required for technical onboarding insights")
        topics = technical_topics(model, archetype.archetype)
        plan = technical_plan(archetype.archetype, topics, architecture.public_api_entry_points)
        return BusinessInsights(
            frameworks=architecture.frameworks,
            learning_plan=plan,
            technical_topics=[asdict(topic) for topic in topics],
            recommendations=[step["detail"] for step in plan],
        )
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
        impact = _DOMAIN_IMPACTS.get(domain.name, "Medium") if has_direct_evidence else "Low"
        importance = (
            "Very High" if impact in {"Critical", "High"} and domain.modules
            else "High" if impact in {"Critical", "High"} or domain.modules or related_integrations
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
            description=" ".join(domain.responsibilities) or "No responsibility was inferred.",
        ))
    domain_impacts.sort(key=lambda item: (
        -_IMPORTANCE_RANK[item.onboarding_importance],
        -_IMPACT_RANK[item.business_impact],
        _DOMAIN_ORDER.get(item.name, len(_DOMAIN_ORDER)),
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
            _DOMAIN_ORDER.get(item.name, len(_DOMAIN_ORDER)),
            item.name.casefold(),
        ))
        domain_names = [item.name for item in owners]
        impact = owners[0].business_impact if owners else "Low"
        confidence = max((item.confidence for item in owners), default=0.35)
        if impact in {"Critical", "High"} and owners[0].onboarding_importance == "Very High":
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
            recommendation=(
                f"Study this module before changing {owners[0].name} workflows; "
                "confirm its role with a maintainer."
                if owners else
                "Defer this module until a relevant workflow or maintainer points to it."
            ),
        ))
    module_priorities.sort(key=lambda item: (
        -_MODULE_TIER_RANK[item.tier],
        -_IMPACT_RANK[item.business_impact],
        bool(_tokens(item.name) & _SUPPORTING_MODULE_TOKENS),
        item.name.casefold(),
        item.path.casefold(),
    ))
    for domain in domain_impacts:
        domain.learning_order = list(dict.fromkeys(
            item.name for item in module_priorities if domain.name in item.domains
        ))
        domain.starting_module = next(iter(domain.learning_order), None)
        if domain.starting_module:
            domain.learning_recommendation = (
                f"Start with {domain.starting_module}, then trace a workflow in {domain.name} "
                "and confirm the module's role with a maintainer."
            )
        else:
            domain.learning_recommendation = (
                "No starting module was identified; ask a maintainer where to trace this workflow."
            )

    # Give the first representative of each important domain a place before
    # listing additional modules from the same domain.
    representatives = []
    seen_paths = set()
    for domain in domain_impacts:
        if domain.onboarding_importance not in {"Very High", "High"}:
            continue
        representative = next(
            (item for item in module_priorities
             if domain.name in item.domains and item.path not in seen_paths),
            None,
        )
        if representative:
            representatives.append(representative)
            seen_paths.add(representative.path)
    module_priorities = representatives + [
        item for item in module_priorities if item.path not in seen_paths
    ]
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
            if any(impact_by_name[name].business_impact in {"Critical", "High"} for name in related_domains)
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
            modules = ", ".join(domain.learning_order[:3])
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
        frameworks=architecture.frameworks,
    )


def render_executive_summary_markdown(
    architecture: ArchitectureModel, insights: BusinessInsights
) -> str:
    high_value = [
        item for item in insights.domain_impacts
        if item.business_impact in {"Critical", "High"}
    ][:4]
    top_modules = [item for item in insights.ranked_modules if item.tier != "Supporting"][:4]
    customized_domains = [
        item for item in insights.domain_impacts if item.modules
    ][:4]
    platform = ", ".join(architecture.frameworks[:2]) or architecture.system_type
    if customized_domains:
        areas = "; ".join(
            f"{item.name} ({', '.join(item.modules[:2])})"
            for item in customized_domains
        )
        description = (
            f"This {platform} implementation has {len(insights.ranked_modules)} "
            f"discovered project-owned modules. Findings concentrate custom business "
            f"behavior in {areas}."
        )
    elif high_value:
        description = (
            "The repository scan identifies business-priority areas in "
            + ", ".join(item.name for item in high_value[:3])
            + ", but did not match those areas to specific custom modules."
        )
    else:
        description = architecture.description.strip() or (
            f"{architecture.system_name} is a {architecture.system_type} repository."
        )
    lines = [
        f"# Executive Summary — {architecture.system_name}",
        "",
        description,
    ]
    lines += ["", "## Where business value appears concentrated", ""]
    if high_value:
        for item in high_value:
            evidence = []
            if item.modules:
                evidence.append(
                    "matched modules " + ", ".join(f"`{name}`" for name in item.modules[:4])
                )
            if item.integrations:
                evidence.append(
                    "configured integrations "
                    + ", ".join(f"`{name}`" for name in item.integrations[:3])
                )
            related_capabilities = [
                capability.name for capability in insights.capabilities
                if item.name in capability.domains
            ][:2]
            if related_capabilities:
                evidence.append("capabilities " + ", ".join(related_capabilities))
            finding = (
                "Repository evidence links this area to " + "; ".join(evidence) + ". "
                if evidence else
                item.rationale + " "
            )
            lines.append(
                f"- **{item.name}** — {finding}(impact: {item.business_impact}; "
                f"evidence: {item.confidence:.0%}, heuristic)"
            )
    else:
        lines.append(
            "No high-impact domain was confidently inferred; validate business priorities with a maintainer."
        )
    lines += ["", "## Recommended first focus", ""]
    if top_modules:
        for index, module in enumerate(top_modules, 1):
            capabilities = [
                capability.name for capability in insights.capabilities
                if module.name in capability.modules
            ][:2]
            reason = (
                "associated with " + ", ".join(module.domains)
                if module.domains else
                "identified as project-owned custom application code"
            )
            if capabilities:
                reason += "; capability: " + ", ".join(capabilities)
            lines.append(
                f"{index}. **{module.name}** — {reason}. Confirm its role with a maintainer."
            )
    else:
        lines.append("Start with the repository overview and ask which workflows are most important.")
    if insights.critical_integrations:
        lines += [
            "",
            "Critical integration boundaries: "
            + ", ".join(item["name"] for item in insights.critical_integrations[:4]),
        ]
    else:
        erp = next(
            (item for item in insights.domain_impacts
             if item.name == "ERP Integrations" and item.business_impact in {"Critical", "High"}),
            None,
        )
        lines += ["", (
            "ERP integration workflows were inferred, but no specific business-critical external "
            "service was identified; confirm the integration boundary with a maintainer."
            if erp else
            "No business-critical external integration was identified; confirm integration "
            "boundaries with a maintainer."
        )]
    lines += [
        "",
        "Defer framework internals and vendor or generated code initially, where present; "
        "revisit them when a task requires it.",
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
                f"- **Module location:** `{module.path}`",
                f"- **Business impact:** {module.business_impact}",
                f"- **Related domain evidence confidence:** {module.confidence:.0%} (heuristic)",
                f"- **Rationale:** {module.rationale}",
                f"- **Recommendation:** {module.recommendation}",
                "",
            ]
    omitted = len(insights.ranked_modules) - len(modules)
    if omitted:
        lines += [
            f"{omitted} additional modules are omitted from this summary; consult `domain_map.json` when a task requires them.",
            "",
        ]
    return "\n".join(lines)


def first_week_onboarding_plan(insights: BusinessInsights) -> list[dict[str, str]]:
    if insights.learning_plan:
        return insights.learning_plan
    actionable_domains = [
        item for item in insights.domain_impacts
        if item.onboarding_importance in {"Very High", "High"}
    ]
    selected_domains = actionable_domains[:4]
    framework = ", ".join(insights.frameworks) if insights.frameworks else "the application"
    days = [
        {
            "title": "Product context and architecture",
            "detail": (
                f"Understand {framework} architecture and its module or component boundaries. "
                "Review the repository purpose and confirm the primary users and workflows with a maintainer."
            ),
        },
    ]
    for domain in selected_domains:
        detail = f"{domain.rationale} {domain.learning_recommendation}"
        integrations = [
            item["name"] for item in insights.critical_integrations
            if domain.name in item["domains"]
        ]
        if integrations:
            detail += (
                f" Trace a critical integration: {', '.join(integrations[:2])}. "
                "Confirm runtime activation and ownership."
            )
        elif domain.name == "ERP Integrations":
            detail += (
                " Trace the external ERP boundary and confirm the system, runtime activation, "
                "and ownership with a maintainer."
            )
        days.append({"title": f"Understand {domain.name}", "detail": detail})
    fallback_days = [
        ("Identify the main business capability", "Ask a maintainer which customer or operational workflow matters most."),
        ("Clarify ownership and change boundaries", "Choose a feature and confirm its owner and downstream systems."),
        ("Trace a business workflow", "Follow a capability through its application and integration boundaries."),
        ("Review verification and delivery", "Run documented tests and review how changes are validated."),
    ]
    for title, detail in fallback_days:
        if len(days) == 5:
            break
        days.append({"title": title, "detail": detail})
    days[-1]["detail"] += " Run the project's documented tests before making a change."
    return days


def render_first_week_onboarding_markdown(insights: BusinessInsights) -> str:
    days = first_week_onboarding_plan(insights)
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
        if item.business_impact in {"Critical", "High"}
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
                f"- **{domain.name}** — {domain.rationale} "
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
    elif any(
        item.name == "ERP Integrations" and item.business_impact in {"Critical", "High"}
        for item in insights.domain_impacts
    ):
        lines += [
            "## Integration workflows to investigate",
            "",
            "ERP integration workflows were inferred, but no specific external service was identified. "
            "Confirm the boundary, runtime activation, and owner with a maintainer.",
            "",
        ]
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
