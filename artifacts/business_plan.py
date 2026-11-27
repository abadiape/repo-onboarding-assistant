"""Business plan."""
from __future__ import annotations

from models.business_insights import BusinessInsights


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
