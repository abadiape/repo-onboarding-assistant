"""Domain reports."""
from __future__ import annotations

from models.business_insights import BusinessInsights
from models.domain_discovery import DomainDiscovery


def render_business_domains_markdown(
    discovery: DomainDiscovery, *, insights: BusinessInsights | None = None
) -> str:
    lines = ["# Business Domains", ""]
    if not discovery.domains:
        lines += ["No business domains were confidently inferred from the available repository evidence.", ""]
    impacts = {item.name: item for item in insights.domain_impacts} if insights else {}
    domains_by_name = {item.name: item for item in discovery.domains}
    ordered_domains = (
        [domains_by_name[item.name] for item in insights.domain_impacts]
        if insights else discovery.domains
    )
    for domain in ordered_domains:
        impact = impacts.get(domain.name)
        lines += [
            f"## {domain.name} — {domain.priority.title()} priority",
            "",
            "**Description:** " + (" ".join(domain.responsibilities) or "No responsibility was inferred."),
            "",
        ]
        if impact:
            order = impact.learning_order[:5]
            lines += [
                f"**Why it matters:** {impact.rationale}",
                "",
                (f"**Business impact:** {impact.business_impact}; "
                f"**evidence confidence:** {impact.confidence:.0%} (heuristic)."),
                "",
                "**Suggested starting module:** "
                + (f"`{impact.starting_module}`" if impact.starting_module else "None identified"),
                "",
                f"**Learning recommendation:** {impact.learning_recommendation}",
                "",
                "**Suggested learning order:** "
                + (", ".join(f"`{name}`" for name in order) or "Confirm a starting point with a maintainer")
                + (f" (+{len(impact.learning_order) - 5} more in `domain_map.json`)"
                   if len(impact.learning_order) > 5 else ""),
                "",
            ]
        else:
            lines += [
                "**Related modules:** "
                + (", ".join(f"`{name}`" for name in domain.modules[:5]) or "None detected"),
                "",
            ]
        lines += [
            "<details>",
            "<summary>Supporting evidence</summary>",
            "",
            *[f"- `{item}`" for item in domain.evidence],
            *([] if domain.evidence else ["No evidence recorded."]),
            "",
            "</details>",
            "",
        ]
    if discovery.custom_modules:
        lines += [
            "## Custom module sample",
            "",
            "Prioritized choices are in `critical_modules.md`.",
            "",
        ]
        for module in discovery.custom_modules[:10]:
            owner = f"; inferred owner `{module.owner}`" if module.owner else ""
            lines.append(f"- `{module.name}` (`{module.path}`; {module.kind}{owner})")
        omitted = len(discovery.custom_modules) - min(len(discovery.custom_modules), 10)
        if omitted:
            lines.append(
                f"- {omitted} additional modules are listed in `domain_map.json`."
            )
        lines.append("")
    return "\n".join(lines)


def render_business_capabilities_markdown(discovery: DomainDiscovery) -> str:
    lines = ["# Business Capabilities", ""]
    if not discovery.capabilities:
        lines += ["No business capabilities were inferred from the available repository evidence.", ""]
    for capability in discovery.capabilities:
        lines.append(f"- **{capability.name}** ({capability.priority} priority)")
        if capability.domains:
            lines.append(f"  - Domains: {', '.join(capability.domains)}")
        if capability.modules:
            modules = capability.modules[:5]
            remaining = len(capability.modules) - len(modules)
            suffix = f" (+{remaining} more in `domain_map.json`)" if remaining else ""
            lines.append(f"  - Modules: {', '.join(f'`{name}`' for name in modules)}{suffix}")
        if capability.evidence:
            lines += [
                "",
                "  <details>",
                "  <summary>Supporting evidence</summary>",
                "",
                *[f"  - `{path}`" for path in capability.evidence],
                "",
                "  </details>",
            ]
    if discovery.integrations:
        lines += ["", "## External integrations and ownership boundaries", ""]
        for integration in discovery.integrations[:5]:
            domains = f"; related domains: {', '.join(integration.domains)}" if integration.domains else ""
            lines.append(
                f"- **{integration.name}** ({integration.priority} priority; "
                f"boundary: {integration.ownership_boundary}{domains})"
            )
        if len(discovery.integrations) > 5:
            lines.append(
                f"- {len(discovery.integrations) - 5} additional integrations are listed in `domain_map.json`."
            )
    lines.append("")
    return "\n".join(lines)


def render_onboarding_priorities_markdown(
    discovery: DomainDiscovery,
    *,
    top_domain_names: list[str] | None = None,
    top_module_names: list[str] | None = None,
    top_capability_names: list[str] | None = None,
) -> str:
    lines = [
        "# Onboarding Priorities",
        "",
        "A suggested one-week focus. Priorities are heuristic and should be confirmed with a maintainer.",
        "",
    ]
    for day, priority in enumerate(discovery.onboarding_priorities, 1):
        detail = priority["detail"]
        if (
            priority["focus"] == "Learn the highest-value business domains"
            and top_domain_names is not None
        ):
            detail = ", ".join(top_domain_names[:4]) or (
                "No high-confidence domain was inferred; validate business priorities with a maintainer."
            )
        elif (
            priority["focus"] == "Review custom application modules"
            and top_module_names is not None
        ):
            detail = ", ".join(top_module_names[:8]) or (
                "No module was strongly matched to a business-critical domain; consult the domain map as workflows lead there."
            )
        elif (
            priority["focus"] == "Trace important business capabilities"
            and top_capability_names is not None
        ):
            detail = ", ".join(top_capability_names[:5]) or (
                "No capability was strongly matched to custom modules or integrations; validate workflows with a maintainer."
            )
        lines += [
            f"## Focus {day}: {priority['focus']}",
            "",
            detail,
            "",
        ]
    if discovery.deferred_areas:
        deferred_roots = []
        boundary_names = {
            "vendor", "node_modules", "generated", "cache", "caches", "tmp",
            "temp", "dist", "build",
        }
        for path in sorted(
            discovery.deferred_areas,
            key=lambda item: (len(item.split("/")), item.casefold()),
        ):
            parts = path.split("/")
            boundary = next(
                (index for index, part in enumerate(parts) if part.casefold() in boundary_names),
                len(parts) - 1,
            )
            root = "/".join(parts[:boundary + 1])
            if not any(root == parent or root.startswith(parent + "/") for parent in deferred_roots):
                deferred_roots.append(root)
        displayed_roots = deferred_roots[:8]
        lines += [
            "## Defer initially",
            "",
            "These vendor or generated areas are supporting material; avoid starting there unless a task requires it:",
            "",
        ]
        lines += [f"- `{path}/`" for path in displayed_roots]
        omitted = len(deferred_roots) - len(displayed_roots)
        if omitted:
            lines.append(f"- {omitted} additional low-relevance boundaries are available in `domain_map.json`.")
        lines.append("")
    else:
        lines += [
            "## Defer initially",
            "",
            "Start with the business domains and custom modules above; explore supporting infrastructure when a workflow leads there.",
            "",
        ]
    lines += [
        "This is a suggested learning order, not a guarantee that omitted areas are safe to change or ignore.",
        "",
    ]
    return "\n".join(lines)
