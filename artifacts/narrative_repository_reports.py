"""Narrative repository reports."""
from __future__ import annotations

from models.business_insights import DomainImpact
from models.business_narrative import BusinessNarrative


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
            ("A conceptual reading path, ordered from the current domain and capability "
            "findings (not an observed runtime sequence):"),
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
        ("These associations are repository-derived onboarding hypotheses. Confirm "
        "module responsibilities, runtime activation, and workflow order with maintainers."),
        "",
    ]
    return "\n".join(lines)


def render_business_risk_story_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# Business Risk Story — {narrative.system_name}",
        "",
        ("This is onboarding prioritization, not an operational risk assessment. "
        "The observations below describe inferred business sensitivity, not guarantees "
        "about production impact."),
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
        ("Treat the ratings and module associations as hypotheses. They are based on "
        "repository evidence and do not establish outage likelihood, revenue exposure, "
        "or runtime coupling."),
        "",
    ]
    return "\n".join(lines)


def render_first_day_briefing_markdown(narrative: BusinessNarrative) -> str:
    lines = [
        f"# First-Day Briefing — {narrative.system_name}",
        "",
        ("A short first read. Use the linked maps and a maintainer conversation to verify "
        "these repository-derived hypotheses."),
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
        ("Validate inferred roles and priorities with a maintainer before changing "
        "business-critical behavior."),
        "",
    ]
    return "\n".join(lines)
