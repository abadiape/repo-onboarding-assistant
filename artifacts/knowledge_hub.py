"""Build and render the portable knowledge hub from structured analysis results."""
from __future__ import annotations

from dataclasses import asdict
from html import escape
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import quote

from analyzers.business_insights import BusinessInsights, first_week_onboarding_plan
from analyzers.domain_discovery import DomainDiscovery
from analyzers.narrative_generation import BusinessNarrative
from models.architecture_model import ArchitectureModel
from models.models import RepositoryModel
from models.repository_archetype import ArchetypeResult, RepositoryArchetype
from analyzers.technical_onboarding import repository_purpose, technical_topics


def build_knowledge_hub(
    model: RepositoryModel,
    architecture: ArchitectureModel,
    domains: DomainDiscovery,
    insights: BusinessInsights,
    narrative: BusinessNarrative,
    artifact_names: list[str],
    archetype: ArchetypeResult | None = None,
) -> dict[str, Any]:
    """Aggregate analyzer results without reading generated Markdown."""
    components = {item.id: item.name for item in architecture.components}
    relationships = [
        {"source": components[item.source], "target": components[item.target], "label": item.type,
         **({"evidence": item.evidence} if item.evidence else {})}
        for item in architecture.relationships
        if item.source in components and item.target in components
    ]
    flow_edges = []
    for flow in architecture.execution_flows:
        for path in flow.get("paths", []):
            ids = path["component_ids"]
            evidence = path.get("relationship_evidence", [])
            for index, (source, target, label) in enumerate(zip(ids, ids[1:], path["relationship_types"])):
                if source in components and target in components:
                    flow_edges.append({
                        "source": components[source], "target": components[target],
                        "label": label + (" (optional)" if path.get("kind") == "optional" else ""),
                        **({"evidence": evidence[index]} if index < len(evidence) and evidence[index] else {}),
                    })
    actionable = [
        item for item in insights.domain_impacts
        if item.onboarding_importance in {"Very High", "High"}
    ]
    starting_domains = actionable or [
        item for item in insights.domain_impacts if item.onboarding_importance == "Medium"
    ]
    purpose = narrative.system_purpose
    if archetype is None and not narrative.primary_domains and architecture.description.strip():
        purpose = architecture.description.strip()
    elif archetype and archetype.archetype == RepositoryArchetype.BUSINESS_APPLICATION and not narrative.primary_domains:
        purpose = repository_purpose(model, purpose)
    workflow_edges = [
        {"source": workflow.name, "target": domain, "label": "associated with"}
        for workflow in narrative.workflows for domain in workflow.domains
    ]
    technical = archetype is not None and archetype.archetype != RepositoryArchetype.BUSINESS_APPLICATION
    topics = technical_topics(model, archetype.archetype) if technical and archetype else []
    observations = []
    for domain in domains.domains:
        paths = [module.path for module in domains.custom_modules if module.name in domain.modules]
        if paths:
            observations.append(f"{domain.name}: matched module paths include {', '.join(paths[:3])}.")
        if len(observations) == 5:
            break
    if architecture.entry_points:
        observations.append("Potential entry points: " + ", ".join(architecture.entry_points[:3]) + ".")
    if architecture.external_dependencies or architecture.data_stores:
        observations.append(
            "Detected external technology signals: "
            + ", ".join((architecture.external_dependencies + architecture.data_stores)[:6])
            + ". Confirm runtime configuration."
        )
    if architecture.optional_integrations:
        observations.append(
            "Optional integrations (not proof of activation or deployment): "
            + "; ".join(architecture.optional_integrations) + "."
        )
    if architecture.relationships and not architecture.execution_flows:
        observations.append(
            "The available relationships do not establish an execution sequence; "
            "inspect their evidence in the visualizations."
        )
    return {
        "schema_version": 1,
        **({"repository_archetype": archetype.to_dict()} if archetype else {}),
        "technical_topics": [asdict(item) for item in topics],
        "api_inventory": model.api_inventory,
        "overview": {
            "repository_name": model.repository_name,
            "purpose": purpose,
            "business_focus": [item.name for item in actionable[:5]],
            "starting_areas": [item.name for item in starting_domains[:4]],
            "defer": domains.deferred_areas,
            "defer_guidance": (
                "Defer framework internals and vendor or generated code initially, where present; "
                "revisit them when a task requires it."
            ),
        },
        "business_domains": [asdict(item) for item in insights.domain_impacts],
        "critical_modules": [asdict(item) for item in insights.ranked_modules[:10]],
        "architecture": {
            "description": architecture.description,
            "system_type": architecture.system_type,
            "frameworks": architecture.frameworks,
            "languages": model.languages,
            "layers": [asdict(item) for item in architecture.layers],
            "components": [asdict(item) for item in architecture.components],
            "execution_flows": architecture.execution_flows,
            "observations": observations,
            "optional_integrations": architecture.optional_integrations,
        },
        "learning_path": first_week_onboarding_plan(insights),
        "workflows": [asdict(item) for item in narrative.workflows],
        "visualizations": [
            {"title": "Architecture relationships", "edges": relationships[:20],
             "omitted": max(0, len(relationships) - 20)},
            {"title": "Conceptual execution flow", "edges": flow_edges, "omitted": 0},
            {"title": "Workflow associations", "edges": workflow_edges[:20],
             "omitted": max(0, len(workflow_edges) - 20)},
        ],
        "artifacts": artifact_names,
    }


def _e(value: object) -> str:
    return escape(str(value), quote=True)


def _list(values: list[str], empty: str, *, ordered: bool = False) -> str:
    if not values:
        return f'<p class="empty">{_e(empty)}</p>'
    tag = "ol" if ordered else "ul"
    return f"<{tag}>" + "".join(f"<li>{_e(value)}</li>" for value in values) + f"</{tag}>"


def _api_parameters(item: dict[str, Any]) -> str:
    if "parameters" not in item:
        return "Not available from the local service contract"
    return ", ".join(
        (param["type"] + " " if param["type"] else "") + "$" + param["name"]
        + (" (optional)" if param["optional"] else "")
        for param in item.get("parameters", [])
    ) or "None declared"


def _diagram(
    visualization: dict[str, Any], index: int,
    component_details: dict[str, dict[str, Any]] | None = None,
) -> str:
    edges = visualization["edges"]
    if not edges:
        return f'<article class="card"><h3>{_e(visualization["title"])}</h3><p class="empty">No relationships were inferred.</p></article>'
    height = len(edges) * 90 + 20
    rows = []
    for row, edge in enumerate(edges):
        y = 10 + row * 90
        # SVG text uses native text wrapping via foreignObject so long names remain readable.
        rows.append(
            f'<rect x="10" y="{y}" width="240" height="62" rx="8"/>'
            f'<rect x="470" y="{y}" width="240" height="62" rx="8"/>'
            f'<foreignObject x="18" y="{y + 6}" width="224" height="50"><div xmlns="http://www.w3.org/1999/xhtml">{_e(edge["source"])}</div></foreignObject>'
            f'<foreignObject x="478" y="{y + 6}" width="224" height="50"><div xmlns="http://www.w3.org/1999/xhtml">{_e(edge["target"])}</div></foreignObject>'
            f'<path d="M250 {y + 31} H465" marker-end="url(#arrow-{index})"/>'
            f'<foreignObject x="260" y="{y + 1}" width="195" height="26"><div xmlns="http://www.w3.org/1999/xhtml">{_e(edge["label"])}</div></foreignObject>'
        )
    omitted = visualization["omitted"]
    note = f'{omitted} additional associations are omitted from this visualization.' if omitted else ""
    names = list(dict.fromkeys(
        name for edge in edges for name in (edge["source"], edge["target"])
    ))
    descriptions = []
    for name in names:
        component = (component_details or {}).get(name)
        if not component:
            continue
        locations = component.get("locations", [])[:2]
        descriptions.append(
            f'<li><strong>{_e(name)}:</strong> {_e(component["description"])}'
            + (f' <span>Example locations: {_e(", ".join(locations))}.</span>' if locations else "")
            + '</li>'
        )
    evidence_rows = [
        f'<li>{_e(edge["source"])} → {_e(edge["target"])} ({_e(edge["label"])}): '
        f'{_e("; ".join(edge["evidence"][:2]))}</li>'
        for edge in edges if edge.get("evidence")
    ]
    legend = (
        f'<details class="diagram-legend"{" open" if index == 10 else ""}><summary>Component meanings and evidence</summary>'
        + ('<ul>' + "".join(descriptions) + '</ul>' if descriptions else "")
        + ('<p>Relationship evidence:</p><ul>' + "".join(evidence_rows) + '</ul>' if evidence_rows else "")
        + '</details>'
    ) if descriptions or evidence_rows else ""
    return (
        f'<article class="card diagram-card"><h3>{_e(visualization["title"])}</h3>'
        f'<p>Inferred relationships, not observed runtime calls. {_e(note)}</p>'
        '<div class="diagram-controls"><button type="button" data-action="in">Zoom in</button>'
        '<button type="button" data-action="out">Zoom out</button>'
        '<button type="button" data-action="reset">Reset</button>'
        '<button type="button" data-action="fullscreen">Fullscreen</button>'
        '<button type="button" data-action="export">Export SVG</button></div>'
        '<p class="diagram-status" role="status" aria-live="polite">Drag to pan.</p>'
        '<div class="diagram-viewport" tabindex="0" aria-label="Diagram; drag to pan">'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 {height}" '
        f'width="720" height="{height}" role="img" aria-label="{_e(visualization["title"])}">'
        f'<defs><marker id="arrow-{index}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">'
        '<path d="M0 0 L8 4 L0 8 Z" fill="#466a8b" stroke="none"/></marker></defs>'
        '<style>rect{fill:#eff6fc;stroke:#9bbbd4} path{fill:none;stroke:#466a8b;stroke-width:2} marker path{fill:#466a8b;stroke:none} '
        'foreignObject div{font:14px/1.2 sans-serif;color:#173b59;text-align:center;overflow-wrap:anywhere}</style>'
        + "".join(rows) + '</svg></div>' + legend + '</article>'
    )


def render_knowledge_hub_html(hub: dict[str, Any]) -> str:
    """Render a self-contained HTML document from a knowledge hub model."""
    overview = hub["overview"]
    days = hub["learning_path"]
    focus = _list(overview["business_focus"], "No business focus inferred; confirm priorities with a maintainer.")
    starts = _list(overview["starting_areas"], "Ask a maintainer for the most important workflow.", ordered=True)
    modules = hub["critical_modules"]
    top_modules = _list([item["name"] for item in modules[:4]], "No custom modules identified.")
    domain_cards = "".join(
        '<article class="card">'
        f'<h3>{_e(item["name"])}</h3><p>{_e(item["description"])}</p>'
        f'<p><strong>Why it matters:</strong> {_e(item["rationale"])}</p>'
        f'<p><strong>Estimated impact:</strong> {_e(item["business_impact"])}</p>'
        f'<p><strong>Start with:</strong> {_e(item["starting_module"] or "Ask a maintainer")}</p>'
        f'<p><strong>Learning order:</strong> {_e(", ".join(item["learning_order"][:5]) or "Not inferred")}</p>'
        '</article>' for item in hub["business_domains"]
    ) or '<p class="empty">No business domains were inferred.</p>'
    module_cards = "".join(
        '<details class="card"><summary>'
        f'#{index} {_e(item["name"])} <span>{_e(item["tier"])}</span></summary>'
        f'<p><strong>Location:</strong> {_e(item["path"])}</p>'
        f'<p><strong>Why it matters:</strong> {_e(item["rationale"])}</p>'
        f'<p><strong>Domains:</strong> {_e(", ".join(item["domains"]) or "Unassigned")}</p>'
        f'<p><strong>Estimated impact:</strong> {_e(item["business_impact"])}</p>'
        f'<p><strong>Onboarding:</strong> {_e(item["recommendation"])}</p></details>'
        for index, item in enumerate(modules, 1)
    ) or '<p class="empty">No custom modules were identified.</p>'
    architecture = hub["architecture"]
    component_details = {item["name"]: item for item in architecture["components"]}
    layers = "".join(
        f'<article class="card"><h3>{_e(item["name"])}</h3><p>{_e(item["description"])}</p></article>'
        for item in architecture["layers"]
    ) or '<p class="empty">No architectural layers were inferred.</p>'
    components = "".join(
        f'<article class="card"><h3>{_e(item["name"])}</h3><p>{_e(item["description"])}</p>'
        + (f'<p><strong>Example locations:</strong> {_e(", ".join(item.get("locations", [])[:2]))}</p>' if item.get("locations") else "")
        + '</article>'
        for item in architecture["components"][:12]
    ) or '<p class="empty">No major components were inferred.</p>'
    if len(architecture["components"]) > 12:
        components += '<p class="empty">Additional components are available in the architecture map.</p>'
    week = "".join(
        f'<article class="card day"><span>Day {index}</span><h3>{_e(day["title"])}</h3><p>{_e(day["detail"])}</p></article>'
        for index, day in enumerate(days, 1)
    )
    workflows = "".join(
        f'<article class="card"><h3>{_e(item["name"])}</h3><p>{_e(item["purpose"])}</p>'
        f'<p><strong>Associated domains:</strong> {_e(", ".join(item["domains"]) or "Not inferred")}</p>'
        f'<p><strong>Modules:</strong> {_e(", ".join(item["modules"][:5]) or "Not inferred")}</p></article>'
        for item in hub["workflows"]
    ) or '<p class="empty">No actionable business workflows were inferred.</p>'
    artifacts = "".join(
        f'<li><a href="{quote(name, safe="")}">{_e(name)}</a></li>'
        for name in hub["artifacts"]
    )
    technical = "repository_archetype" in hub and hub["repository_archetype"]["archetype"] != RepositoryArchetype.BUSINESS_APPLICATION.value
    classification = hub.get("repository_archetype")
    classification_card = ""
    if classification:
        name = classification["archetype"].replace("_", " ").title()
        classification_card = (
            f'<article class="card"><h3>Inferred archetype: {_e(name)}</h3>'
            f'<p>Heuristic confidence: {_e(classification["confidence"])}</p>'
            + (_list(classification["evidence"], "") if classification["evidence"] else "")
            + '</article>'
        )
    if technical:
        topics = hub.get("technical_topics", [])
        focus_cards = "".join(
            f'<article class="card"><h3>{_e(item["title"])}</h3>'
            f'{_list(item["evidence"], "")}</article>'
            for item in topics
        )
        overview_cards = (
            f'<article class="card"><h3>Learning path</h3><p><strong>Start:</strong> {_e(days[0]["title"])}</p>'
            '<a href="#week">See the learning plan</a></article>'
        )
        business_nav = ""
        business_section = ""
        overview_heading = "Repository Overview"
        notice = "Classification and relationships are heuristic; confirm them with maintainers."
        overview_extra = f'<div class="grid block">{classification_card}{focus_cards}</div>' if classification_card or focus_cards else ""
    else:
        overview_heading = "Executive Overview"
        notice = "Inferred from repository evidence, not a runtime or business assessment. Confirm priorities and ownership with maintainers."
        overview_cards = (
            (f'<article class="card"><h3>Business focus</h3>{focus}</article>' if overview["business_focus"] else "")
            + (f'<article class="card"><h3>Critical modules</h3>{top_modules}</article>' if modules else "")
            + (f'<article class="card"><h3>Start here</h3>{starts}</article>' if overview["starting_areas"] else "")
            + f'<article class="card"><h3>Learning path</h3><p><strong>First day:</strong> {_e(days[0]["title"])}</p>'
            f'<p><strong>First week:</strong> {_e(days[1]["title"])} and the remaining plan.</p><a href="#week">See the five-day plan</a></article>'
        )
        overview_extra = (
            f'<div class="grid block">{classification_card}{domain_cards if hub["business_domains"] else ""}</div>'
        ) if classification_card or hub["business_domains"] else ""
        if hub["workflows"]:
            overview_extra += f'<div class="block"><h2>Workflows</h2><div class="grid">{workflows}</div></div>'
        business_nav = '<a href="#business">Business</a>'
        business_section = (
            '<section id="business"><h2>Business View</h2><p class="notice">Domain matches and impacts are heuristic; confirm them with maintainers.</p>'
            + (f'<div class="grid">{domain_cards}</div>' if hub["business_domains"] else "")
            + (f'<div class="block"><h2>Workflows</h2><div class="grid">{workflows}</div></div>' if hub["workflows"] else "")
            + '</section>'
        ) if hub["business_domains"] or hub["workflows"] else ""
        if not business_section:
            business_nav = ""
    modules_nav = '<a href="#modules">Critical Modules</a>' if modules else ""
    inventory = hub.get("api_inventory", {})
    endpoints = inventory.get("endpoints", [])
    warnings = inventory.get("warnings", [])
    api_nav = '<a href="#apis">API Inventory</a>' if endpoints or warnings else ""

    def api_card(item: dict[str, Any]) -> str:
        return (
            '<details class="card api-card"><summary>'
            f'{_e(item["method"])} <span>{_e(item["module"])}</span></summary>'
            f'<p><strong>Declared service:</strong> {_e(item["service"] or "Not specified")}'
            f'::{_e(item["service_method"] or "Not specified")}</p>'
            f'<p><strong>Access resources:</strong> {_e(", ".join(item["resources"]) or "Not specified")}</p>'
            f'<p><strong>Service parameters:</strong> {_e(_api_parameters(item))}</p>'
            f'<p><strong>Return type:</strong> {_e(item.get("return_type") or "Not documented")}</p>'
            + (f'<p><strong>Configured parameter names:</strong> {_e(", ".join(item["forced_parameters"]))}</p>'
               if item["forced_parameters"] else "")
            + f'<p><strong>Evidence:</strong> {_e(item["source"])}'
            + (f'; {_e(item["contract_source"])}' if item.get("contract_source") else "")
            + '</p></details>'
        )

    api_groups: dict[str, list[dict[str, Any]]] = {}
    for item in endpoints:
        api_groups.setdefault(item["path"], []).append(item)
    api_cards = "".join(
        '<details class="card api-group"><summary>'
        f'<span class="api-path">{_e(path)}</span> '
        f'<span>({len(items)} declaration{"s" if len(items) != 1 else ""}: '
        f'{_e(", ".join(dict.fromkeys(item["method"] for item in items)))})</span>'
        '</summary><div class="stack api-methods">'
        + "".join(api_card(item) for item in items)
        + '</div></details>'
        for path, items in sorted(api_groups.items(), key=lambda entry: (entry[0].casefold(), entry[0]))
    )
    api_section = (
        '<section id="apis"><h2>API Inventory</h2>'
        '<p class="notice">This inventory lists project-owned Magento service routes declared in webapi.xml. '
        'Storefront code or external clients may call them; their implementations may use local data or call '
        'external services. Platform and vendor routes and outbound service calls are not inventoried.</p>'
        '<p class="notice">The inventory can be generated from a local clone without access to a running environment. '
        'Paths are source declarations, not complete URLs: base URLs and REST or store prefixes can vary by '
        'environment, as can deployed code, enabled modules and route overrides. Confirm effective URLs, access, '
        'request and response behavior, and business criticality with maintainers when possible. '
        'Service parameters are not necessarily HTTP parameters.</p>'
        f'<p>{len(endpoints)} route declaration{"s" if len(endpoints) != 1 else ""} '
        f'across {len(api_groups)} path{"s" if len(api_groups) != 1 else ""}</p>'
        + (_list(warnings, "") if warnings else "")
        + ('<label for="api-search">Filter routes</label> <input id="api-search" type="search" placeholder="Method, path, module or service">'
           '<p id="api-count" role="status"></p><div class="stack">' + api_cards + '</div>' if endpoints else "")
        + '</section>'
    ) if api_nav else ""
    modules_section = (
        '<section id="modules"><h2>Critical Modules</h2><p class="notice">Select a module for its inferred role and onboarding recommendation. Up to ten are shown.</p>'
        f'<div class="stack">{module_cards}</div></section>'
    ) if modules else ""
    flow_section = (
        f'<div class="block"><h2>Execution Flow</h2><p class="notice">A conceptual path based on inferred relationships, not a runtime trace. Open the legend to inspect role definitions and evidence.</p>{_diagram(hub["visualizations"][1], 10, component_details)}</div>'
    ) if hub["visualizations"][1]["edges"] else ""
    layers_section = f'<div class="block"><h2>Architectural Layers</h2><div class="grid">{layers}</div></div>' if architecture["layers"] else ""
    components_section = f'<div class="block"><h2>Major Components</h2><div class="grid">{components}</div></div>' if architecture["components"] else ""
    diagrams = [_diagram(item, index, component_details) for index, item in enumerate(hub["visualizations"]) if item["edges"]]
    visual_nav = '<a href="#visualizations">Visualizations</a>' if diagrams else ""
    visual_section = '<section id="visualizations"><h2>Visualizations</h2><p class="notice">Offline SVG maps generated from structured findings. Associations are inferred.</p><div class="stack">' + "".join(diagrams) + '</div></section>' if diagrams else ""
    template = Template((Path(__file__).parent / "knowledge_hub_template.html").read_text(encoding="utf-8"))
    return template.substitute(
        title=_e(overview["repository_name"]), purpose=_e(overview["purpose"]),
        overview_heading=overview_heading, notice=notice, overview_cards=overview_cards,
        overview_extra=overview_extra, business_nav=business_nav, business_section=business_section,
        modules_nav=modules_nav, modules_section=modules_section, visual_nav=visual_nav, visual_section=visual_section,
        api_nav=api_nav, api_section=api_section,
        defer_section=(
            '<div class="card defer"><h3>Defer initially</h3>'
            f'<p>{_e(overview["defer_guidance"])}</p><details><summary>Detected lower-priority paths</summary>'
            f'{_list(overview["defer"][:8], "")}</details></div>'
        ) if overview["defer"] else "",
        architecture_description=_e(architecture["description"] or "No architecture overview was inferred."),
        architecture_observations=(
            '<div class="block"><h2>Repository-specific evidence</h2>'
            '<p class="notice">Path and name matches suggest investigation points, not verified responsibilities.</p>'
            + _list(architecture.get("observations", []), "") + '</div>'
        ) if architecture.get("observations") else "",
        technologies=_e(", ".join(architecture["languages"] + architecture["frameworks"]) or "Not detected"),
        layers_section=layers_section, components_section=components_section, flow_section=flow_section,
        week=week, artifacts=artifacts,
    )
