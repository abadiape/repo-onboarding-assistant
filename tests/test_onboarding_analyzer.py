"""Tests for onboarding_analyzer."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models import RepositoryInventory
from onboarding_analyzer import (
    analyze_inventory,
    render_learning_path_markdown,
    render_summary_markdown,
)


def sample_inventory() -> RepositoryInventory:
    return RepositoryInventory(
        repository_name="demo",
        languages=["Python"],
        frameworks=["FastAPI"],
        package_managers=["pip"],
        build_tools=["Python build (setuptools/poetry)"],
        test_frameworks=["pytest"],
        important_files=["README.md", "pyproject.toml"],
        ci_cd_files=[".github/workflows/ci.yml"],
        top_level_directories=["src", "tests"],
        entry_points=["src/main.py"],
        build_instructions=["pip install -e ."],
        test_instructions=["pytest"],
    )


def test_analyze_inventory_learning_path():
    inv = sample_inventory()
    insights = analyze_inventory(inv)
    assert "demo" in insights.summary
    assert "Python" in insights.main_technologies
    assert insights.files_to_read_first[0] == "README.md"
    titles = [s["title"] for s in insights.learning_path]
    assert any("README" in t for t in titles)
    assert any("Build" in t for t in titles)
    md = render_summary_markdown(inv, insights)
    assert "# Repository Overview — demo" in md
    lp = render_learning_path_markdown(inv, insights)
    assert "# Learning Path — demo" in lp


def test_setup_guide_is_in_learning_path_and_summary():
    inv = sample_inventory()
    inv.readme_summary = "A small local-first toolkit."
    inv.setup_guides = ["LOCAL_SETUP.md"]
    inv.onboarding_docs = ["README.md", "LOCAL_SETUP.md"]
    inv.documented_setup_commands = [
        {"source": "LOCAL_SETUP.md", "section": "Install", "command": "pip install -e ."}
    ]

    insights = analyze_inventory(inv)
    setup_step = next(step for step in insights.learning_path if "setup guide" in step["title"].lower())
    assert "LOCAL_SETUP.md" in setup_step["detail"]
    assert "A small local-first toolkit." in insights.summary

    summary = render_summary_markdown(inv, insights)
    assert "Onboarding documentation" in summary
    assert "Setup commands documented by the project" in summary
    assert "`pip install -e .`" in summary


def test_analyze_empty_repo():
    inv = RepositoryInventory(repository_name="empty")
    insights = analyze_inventory(inv)
    assert "no recognized language" in insights.summary.lower()
    assert insights.open_questions  # should flag missing tests/CI/docs
