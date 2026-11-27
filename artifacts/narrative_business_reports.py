"""Narrative business reports."""
from __future__ import annotations

from models.business_narrative import BusinessNarrative


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
            ("The following links are supported by a shared capability, module, or "
            "business-critical integration; they do not prove runtime call order."),
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
        ("Impact and priority are heuristic onboarding signals, not measured business "
        "risk or revenue. Validate critical paths and ownership with the team."),
        "",
    ]
    return "\n".join(lines)


def render_critical_workflows_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# Critical Workflows — {narrative.system_name}",
        "",
        ("These workflow guides are synthesized from discovered capabilities and their "
        "domain/module associations. The repository findings do not prove runtime call order."),
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
        ("A senior-developer-style learning sequence based on this repository's inferred "
        "business priorities. Confirm assumptions as you go."),
        "",
    ]
    for title, advice in narrative.first_week:
        lines += [f"## {title}", "", advice, ""]
    return "\n".join(lines)
