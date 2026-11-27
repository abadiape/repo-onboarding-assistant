"""Business reports."""
from __future__ import annotations

from models.architecture_model import ArchitectureModel
from models.business_insights import BusinessInsights

_MAX_CRITICAL_MODULES = 10


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
        ("Defer framework internals and vendor or generated code initially, where present; "
        "revisit them when a task requires it."),
        "",
        ("Scores summarize repository evidence, not measured revenue or calibrated probabilities. "
        "Confirm operational importance and ownership with maintainers."),
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
        (f"Top {len(modules)} modules ranked by inferred business impact and onboarding importance. "
        "The complete module inventory remains in `domain_map.json`."),
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


def render_business_insights_markdown(insights: BusinessInsights) -> str:
    lines = [
        "# Business Insights",
        "",
        ("These insights summarize patterns in names, ownership boundaries, and architecture evidence; "
        "they are hypotheses to validate, not operational measurements."),
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
            ("ERP integration workflows were inferred, but no specific external service was identified. "
            "Confirm the boundary, runtime activation, and owner with a maintainer."),
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
        ("Confidence estimates how much repository evidence supports a finding. "
        "Business impact describes the likely consequence of changing the area; "
        "onboarding importance determines learning order. They are separate heuristic ratings."),
        "",
    ]
    return "\n".join(lines)
