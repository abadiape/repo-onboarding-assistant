import json

import pytest

from analyzers.repository_archetype import analyze_repository_archetype
from analyzers.repository_scan import scan_repository
from analyzers.technical_onboarding import repository_purpose
from models.models import RepositoryModel
from models.repository_archetype import RepositoryArchetype
from skills.onboarding_skill import run_onboarding


@pytest.mark.parametrize(("description", "expected"), [
    ("A web framework for building APIs.", "framework"),
    ("A simple HTTP library.", "library"),
    ("A developer tool for repository analysis.", "developer_tool"),
    ("An AI agent platform for tools and skills.", "ai_agent_platform"),
    ("An e-commerce platform.", "business_application"),
    ("A command-line tool.", "cli_tool"),
    ("A software development kit SDK.", "sdk"),
    ("An ETL pipeline.", "data_pipeline"),
    ("Infrastructure as code.", "infrastructure"),
])
def test_classification_from_readme_with_evidence(tmp_path, description, expected):
    (tmp_path / "README.md").write_text(f"# Example\n\n{description}\n", encoding="utf-8")
    result = analyze_repository_archetype(scan_repository(tmp_path))
    assert result.archetype.value == expected
    assert 0 < result.confidence <= 1
    assert result.evidence


def test_unknown_and_alternatives():
    assert analyze_repository_archetype(RepositoryModel("sample")).archetype == RepositoryArchetype.UNKNOWN
    model = RepositoryModel("example", readme_summary="A web framework and HTTP client library")
    result = analyze_repository_archetype(model)
    assert result.archetype == RepositoryArchetype.FRAMEWORK
    assert result.alternatives[0].archetype == RepositoryArchetype.LIBRARY


def test_technical_hub_does_not_infer_commerce_from_incidental_terms(tmp_path):
    repo = tmp_path / "client"
    (repo / "src" / "client").mkdir(parents=True)
    (repo / "README.md").write_text(
        "# Example\n\nAn HTTP client library.\n\n## Examples\n\n"
        "Send an order and search products using the API.\n", encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "client"\ndescription = "HTTP client for integrations"\n',
        encoding="utf-8",
    )
    (repo / "src" / "client" / "api.py").write_text("", encoding="utf-8")
    (repo / "src" / "client" / "adapters.py").write_text("", encoding="utf-8")
    out = tmp_path / "out"
    run_onboarding(repo, out)
    hub = json.loads((out / "knowledge_hub.json").read_text())
    domain_map = json.loads((out / "domain_map.json").read_text())
    assert hub["repository_archetype"]["archetype"] == "library"
    assert hub["repository_archetype"]["evidence"]
    assert not hub["business_domains"] and not domain_map["domains"]
    assert hub["overview"]["purpose"] == "HTTP client for integrations"
    assert hub["learning_path"][0]["title"] == "Public APIs"
    html = (out / "knowledge_hub.html").read_text()
    assert "Public APIs" in html and "Integration Points" in html
    assert 'id="business"' not in html
    assert "Business focus" not in html
    assert "No actionable business workflows" not in html
    assert 'id="modules"' not in html
    for name in ("business_story.md", "business_insights.md", "repository_story.md", "learning_path.md"):
        text = (out / name).read_text().lower()
        assert "business workflow" not in text and "customer journey" not in text


def test_skill_topics_can_be_supported_by_documentation(tmp_path):
    repo = tmp_path / "agent"
    (repo / "docs").mkdir(parents=True)
    (repo / "README.md").write_text("# Agent\n\nAn AI agent platform.\n", encoding="utf-8")
    (repo / "docs" / "guide.md").write_text("Skills generate artifacts.\n", encoding="utf-8")
    out = tmp_path / "out"
    run_onboarding(repo, out)
    hub = json.loads((out / "knowledge_hub.json").read_text())
    topics = {item["title"]: item["evidence"] for item in hub["technical_topics"]}
    assert "docs/guide.md:1" in topics["Skills"]
    assert "docs/guide.md:1" in topics["Artifact System"]


def test_purpose_ignores_pronouns_and_later_readme_sections(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Example\n\nA tool for analyzing repositories. It is a standalone skill.\n\n"
        "## Details\n\nThis project is a library, not a production service.\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "example"\ndescription = "Repository analysis tool"\n',
        encoding="utf-8",
    )
    assert repository_purpose(scan_repository(tmp_path), "") == "Repository analysis tool"


@pytest.mark.parametrize("document_retrieval", [True, False])
def test_agent_hub_uses_public_api_and_only_documented_optional_retrieval(tmp_path, document_retrieval):
    repo = tmp_path / "harness"
    files = {
        "README.md": (
            "# Agent Harness — a tool-enabled AI agent platform\n\n"
            "Agent uses Tools.\n"
            + ("RAG as tool is optional.\n" if document_retrieval else "")
        ),
        "src/harness/__init__.py": (
            "from harness.agent import Agent\n"
            "from harness.tools import ToolRegistry\n"
        ),
        "src/harness/agent.py": "class Agent:\n    pass\n",
        "src/harness/tools.py": "class ToolRegistry:\n    pass\n",
        "src/harness/rag/retriever.py": "class Retriever:\n    pass\n",
    }
    for path, content in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    out = tmp_path / "generated"
    run_onboarding(repo, out)
    hub = json.loads((out / "knowledge_hub.json").read_text())
    architecture = json.loads((out / "architecture_map.json").read_text())
    assert "src/harness/__init__.py" in architecture["public_api_entry_points"]
    assert "src/harness/__init__.py" in hub["learning_path"][0]["detail"]
    assert "src/harness/__init__.py" in (out / "first_day_briefing.md").read_text()
    assert "tool-enabled AI agent platform" in architecture["description"]
    retrieval_edges = [
        edge for edge in hub["visualizations"][1]["edges"]
        if edge["target"] == "Retrieval"
    ]
    assert bool(retrieval_edges) is document_retrieval
    if document_retrieval:
        assert retrieval_edges[0]["source"] == "Tools"
        assert "optional" in retrieval_edges[0]["label"]
        assert any("README.md:4" in item for item in retrieval_edges[0]["evidence"])
        diagram = (out / "execution_flow.mmd").read_text()
        assert "opt Optional integration" in diagram
        assert "Public API: src/harness/__init__.py" in diagram


def test_public_package_api_is_recommended_even_with_cli_entrypoint(tmp_path):
    repo = tmp_path / "tool"
    files = {
        "README.md": "# Tool\n\nA developer tool for repository analysis.\n",
        "cli.py": "print('hello')\n",
        "src/tool/__init__.py": "from tool.api import run\n",
        "src/tool/api.py": "def run():\n    pass\n",
        "src/other/__init__.py": "from external_package import thing\n",
    }
    for path, content in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    out = tmp_path / "generated"
    run_onboarding(repo, out)
    architecture = json.loads((out / "architecture_map.json").read_text())
    hub = json.loads((out / "knowledge_hub.json").read_text())
    assert "cli.py" in architecture["entry_points"]
    assert architecture["public_api_entry_points"] == ["src/tool/__init__.py"]
    assert "src/tool/__init__.py" in hub["learning_path"][0]["detail"]
