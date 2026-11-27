import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from artifacts.dashboard import render_dashboard_html
from analyzers.architecture_analyzer import render_execution_flow_mermaid
from models.models import RepositoryModel
from models.architecture_model import ArchitectureComponent, ArchitectureModel, ArchitectureRelationship
from analyzers.onboarding_analyzer import OnboardingInsights


def test_dashboard_renders_mermaid_and_preserves_escaped_source():
    model = RepositoryModel(repository_name='<script>alert("x")</script>')
    insights = OnboardingInsights(
        summary="<unsafe overview>",
        learning_path=[],
    )

    dashboard = render_dashboard_html(
        model,
        insights,
        "# Summary\n\n**Important** `<script>unsafe</script>`",
        {"architecture_overview.mmd": 'flowchart TD\n  A["<unsafe>"]\n'},
    )

    assert '<script>alert("x")</script>' not in dashboard
    assert "<script>unsafe</script>" not in dashboard
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in dashboard
    assert "<strong>Important</strong>" in dashboard
    assert "<code>&lt;script&gt;unsafe&lt;/script&gt;</code>" in dashboard
    assert "&lt;unsafe&gt;" in dashboard
    assert 'class="mermaid"' in dashboard
    assert "mermaid.run" in dashboard
    assert "View Source" in dashboard
    assert "Copy Mermaid" in dashboard
    assert "mermaid@11.17.2" in dashboard
    assert "<link rel=" not in dashboard
    assert "No learning path steps available." in dashboard


def test_dashboard_shows_magento_association_fallback():
    architecture = ArchitectureModel(
        system_name="shop", system_type="application", description="", frameworks=["Magento"],
        components=[ArchitectureComponent("a", "Observers", "extension", ""),
                    ArchitectureComponent("b", "Models", "domain", "")],
        relationships=[ArchitectureRelationship("a", "b", "imports", "")],
    )
    diagram = render_execution_flow_mermaid(architecture)
    dashboard = render_dashboard_html(
        RepositoryModel(repository_name="shop"), OnboardingInsights(summary=""),
        "", {"execution_flow.mmd": diagram}, architecture,
    )
    assert "Associations only - not a verified execution sequence or runtime calls" in dashboard
    assert "a --&gt;|imports| b" in dashboard
