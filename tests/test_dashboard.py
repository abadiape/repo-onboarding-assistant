import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from artifacts.dashboard import render_dashboard_html
from models.models import RepositoryModel
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
