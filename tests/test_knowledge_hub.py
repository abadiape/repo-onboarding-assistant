import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzers.business_insights import BusinessInsights
from analyzers.domain_discovery import DomainDiscovery
from analyzers.narrative_generation import BusinessNarrative, NarrativeWorkflow
from artifacts.knowledge_hub import build_knowledge_hub, render_knowledge_hub_html
from models.architecture_model import (
    ArchitectureComponent,
    ArchitectureModel,
    ArchitectureRelationship,
)
from models.models import RepositoryModel


def test_hub_preserves_inferred_edges_and_escapes_untrusted_names():
    model = RepositoryModel(repository_name='<script>alert("x")</script>')
    architecture = ArchitectureModel(
        system_name="example", system_type="application", description="An example",
        components=[
            ArchitectureComponent(id="a", name="<Source>", type="module", description="Source"),
            ArchitectureComponent(id="b", name="Target", type="module", description="Target"),
        ],
        relationships=[
            ArchitectureRelationship(source="a", target="b", type="imports", description=""),
        ],
        execution_flows=[{"paths": [{"component_ids": ["a", "b"], "relationship_types": ["imports"]}]}],
    )
    narrative = BusinessNarrative(
        system_name="example", system_purpose="Example",
        workflows=[NarrativeWorkflow(name="Checkout", purpose="Pay", domains=["Payments"])],
    )
    hub = build_knowledge_hub(model, architecture, DomainDiscovery(), BusinessInsights(), narrative, ["summary.md"])
    assert hub["visualizations"][0]["edges"] == [
        {"source": "<Source>", "target": "Target", "label": "imports"}
    ]
    assert hub["visualizations"][1]["edges"] == hub["visualizations"][0]["edges"]
    assert hub["visualizations"][2]["edges"][0]["label"] == "associated with"
    html = render_knowledge_hub_html(hub)
    assert '<script>alert("x")</script>' not in html
    assert "&lt;Source&gt;" in html
    assert 'href="summary.md"' in html
    assert "https://" not in html
    assert "flowchart TD" not in html
    assert "<svg " in html
    assert 'href="#apis"' not in html


def test_flow_diagram_explains_components_and_relationship_evidence():
    model = RepositoryModel(repository_name="example")
    architecture = ArchitectureModel(
        system_name="example", system_type="application", description="Layout",
        components=[
            ArchitectureComponent("a", "Models", "domain", "Model paths may hold data.", locations=["src/model"]),
            ArchitectureComponent("b", "Providers", "integration", "Provider roles vary.", locations=["src/providers"]),
        ],
        execution_flows=[{"paths": [{
            "component_ids": ["a", "b"], "relationship_types": ["references"],
            "relationship_evidence": [["src/model/example.py:2"]],
        }]}],
    )
    hub = build_knowledge_hub(
        model, architecture, DomainDiscovery(), BusinessInsights(),
        BusinessNarrative(system_name="example", system_purpose="Example"), [],
    )
    html = render_knowledge_hub_html(hub)
    assert 'class="diagram-legend" open' in html
    assert "Model paths may hold data." in html
    assert "Provider roles vary." in html
    assert "src/model/example.py:2" in html


def test_api_routes_group_methods_without_dropping_duplicate_declarations():
    def endpoint(path, method, module):
        return {
            "path": path, "method": method, "module": module, "source": module,
            "service": "", "service_method": "", "resources": [], "forced_parameters": [],
        }

    model = RepositoryModel(repository_name="example", api_inventory={"endpoints": [
        endpoint("/V1/other", "POST", "Other"),
        endpoint("/V1/zebra", "GET", "Last"),
        endpoint("/V1/<item>", "GET", "First"),
        endpoint("/V1/Banana", "POST", "Banana"),
        endpoint("/V1/<item>", "PUT", "Second"),
        endpoint("/V1/<item>", "GET", "Third"),
    ]})
    hub = build_knowledge_hub(
        model, ArchitectureModel(system_name="example", system_type="application", description=""),
        DomainDiscovery(), BusinessInsights(),
        BusinessNarrative(system_name="example", system_purpose="Example"), [],
    )
    html = render_knowledge_hub_html(hub)
    groups = html.split('<details class="card api-group">')[1:]
    assert len(groups) == 4
    assert '<span class="api-path">/V1/&lt;item&gt;</span>' in groups[0]
    assert '(3 declarations: GET, PUT)' in groups[0]
    assert groups[0].count('class="card api-card"') == 3
    assert all(name in groups[0] for name in ("First", "Second", "Third"))
    assert '<span class="api-path">/V1/Banana</span>' in groups[1]
    assert '<span class="api-path">/V1/other</span>' in groups[2]
    assert '<span class="api-path">/V1/zebra</span>' in groups[3]
    assert all(group.count('class="card api-card"') == 1 for group in groups[1:])
    assert "/V1/<item>" not in html
