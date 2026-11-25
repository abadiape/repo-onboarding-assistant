import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dashboard import render_dashboard_html
from models import RepositoryModel
from onboarding_analyzer import OnboardingInsights


def test_dashboard_is_self_contained_and_escapes_generated_content():
    model = RepositoryModel(repository_name='<script>alert("x")</script>')
    insights = OnboardingInsights(
        summary="<unsafe overview>",
        learning_path=[],
    )

    dashboard = render_dashboard_html(
        model,
        insights,
        "# Summary\n\n<script>unsafe</script>",
        {"architecture_overview.mmd": 'flowchart TD\n  A["<unsafe>"]\n'},
    )

    assert "<script>" not in dashboard
    assert "&lt;script&gt;unsafe&lt;/script&gt;" in dashboard
    assert "&lt;unsafe&gt;" in dashboard
    assert "<script src=" not in dashboard
    assert "<link rel=" not in dashboard
    assert "No learning path steps available." in dashboard
