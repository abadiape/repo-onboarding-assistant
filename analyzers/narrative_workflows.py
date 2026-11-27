"""Narrative workflows."""
from __future__ import annotations

from models.business_insights import BusinessInsights, DomainImpact
from models.business_narrative import DomainInteraction, NarrativeWorkflow

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
            ("Read this story and the architecture overview. Confirm the main users, "
            "business purpose, and inferred value flow with a maintainer."),
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
            (f"{starting_point}{domain.rationale} Trace one relevant capability and "
            "confirm the domain boundary with its maintainer."),
        ))

    if len(days) < 5:
        if workflows:
            workflow = workflows[0]
            days.append((
                f"Day {len(days) + 1}: Trace {workflow.name}",
                (f"Follow the capability through {', '.join(workflow.domains) or 'its inferred application boundary'}. "
                f"Review {', '.join(f'`{name}`' for name in workflow.modules) or 'the relevant implementation'} "
                "and identify how the team verifies the behavior."),
            ))
        else:
            days.append((
                f"Day {len(days) + 1}: Find a representative change",
                "Ask a maintainer to walk through one recent business change and its tests.",
            ))
    while len(days) < 5:
        days.append((
            f"Day {len(days) + 1}: Validate the learning",
            ("Trace a small behavior from its entry point to its outcome, run the "
            "documented tests, and confirm any assumptions with a maintainer."),
        ))
    return days[:5]
