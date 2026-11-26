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


def build_knowledge_hub(
    model: RepositoryModel,
    architecture: ArchitectureModel,
    domains: DomainDiscovery,
    insights: BusinessInsights,
    narrative: BusinessNarrative,
    artifact_names: list[str],
) -> dict[str, Any]:
    """Aggregate analyzer results without reading generated Markdown."""
    components = {item.id: item.name for item in architecture.components}
    relationships = [
        {"source": components[item.source], "target": components[item.target], "label": item.type}
        for item in architecture.relationships
        if item.source in components and item.target in components
    ]
    flow_edges = []
    for flow in architecture.execution_flows:
        for path in flow.get("paths", []):
            ids = path["component_ids"]
            for source, target, label in zip(ids, ids[1:], path["relationship_types"]):
                if source in components and target in components:
                    flow_edges.append({
                        "source": components[source], "target": components[target], "label": label,
                    })
    actionable = [
        item for item in insights.domain_impacts
        if item.onboarding_importance in {"Very High", "High"}
    ]
    starting_domains = actionable or [
        item for item in insights.domain_impacts if item.onboarding_importance == "Medium"
    ]
    purpose = narrative.system_purpose
    if not narrative.primary_domains and architecture.description.strip():
        purpose = architecture.description.strip()
    workflow_edges = [
        {"source": workflow.name, "target": domain, "label": "associated with"}
        for workflow in narrative.workflows for domain in workflow.domains
    ]
    return {
        "schema_version": 1,
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


def _diagram(visualization: dict[str, Any], index: int) -> str:
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
        + "".join(rows) + '</svg></div></article>'
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
    layers = "".join(
        f'<article class="card"><h3>{_e(item["name"])}</h3><p>{_e(item["description"])}</p></article>'
        for item in architecture["layers"]
    ) or '<p class="empty">No architectural layers were inferred.</p>'
    components = "".join(
        f'<article class="card"><h3>{_e(item["name"])}</h3><p>{_e(item["description"])}</p></article>'
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
    diagrams = [_diagram(item, index) for index, item in enumerate(hub["visualizations"])]
    template = Template((Path(__file__).parent / "knowledge_hub_template.html").read_text(encoding="utf-8"))
    return template.substitute(
        title=_e(overview["repository_name"]), purpose=_e(overview["purpose"]),
        focus=focus, starts=starts, top_modules=top_modules,
        first_day=_e(days[0]["title"]), first_week=_e(days[1]["title"]),
        defer=_e(overview["defer_guidance"]), deferred_paths=_list(overview["defer"][:8], "No specific paths identified."),
        domains=domain_cards, modules=module_cards,
        architecture_description=_e(architecture["description"] or "No architecture overview was inferred."),
        technologies=_e(", ".join(architecture["languages"] + architecture["frameworks"]) or "Not detected"),
        layers=layers, components=components, flow=_diagram(hub["visualizations"][1], 10),
        week=week, workflows=workflows, diagrams="".join(diagrams), artifacts=artifacts,
    )
