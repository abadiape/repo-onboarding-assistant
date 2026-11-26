import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.models import Dependency, RepositoryFile, RepositoryModel
from artifacts.visualizations import (
    render_architecture_overview_mermaid,
    render_dependency_graph_mermaid,
    render_module_graph_mermaid,
)


def test_dependency_graph_uses_declared_dependencies_and_escapes_labels():
    model = RepositoryModel(
        repository_name='demo "repo"',
        dependencies=[
            Dependency("example|lib", "^1", "manifest.toml", scope="runtime"),
        ],
    )

    graph = render_dependency_graph_mermaid(model)

    assert graph.startswith("flowchart LR\n")
    assert 'Repository: demo #quot;repo#quot;' in graph
    assert "example#124;lib ^1" in graph
    assert 'runtime · manifest.toml' in graph


def test_module_graph_shows_hierarchy_and_file_metadata():
    model = RepositoryModel(
        repository_name="demo",
        directories=["src/core"],
        files=[RepositoryFile("src/core/main.py", "source", "Python")],
    )

    graph = render_module_graph_mermaid(model)

    assert "src/" in graph
    assert "src/core/" in graph
    assert "src/core/main.py · source · Python" in graph
    assert "directory_0 --> directory_1" in graph
    assert "directory_1 --> file_0" in graph


def test_architecture_overview_uses_available_model_facts():
    model = RepositoryModel(
        repository_name="demo",
        languages=["ExampleLang"],
        top_level_directories=["src"],
        entry_points=["src/main.any"],
    )

    graph = render_architecture_overview_mermaid(model)

    assert "Language: ExampleLang" in graph
    assert "src/main.any" in graph
    assert "src" in graph
    assert "Python" not in graph


def test_empty_graphs_have_valid_fallback_nodes():
    model = RepositoryModel(repository_name="empty")

    assert "No declared dependencies" in render_dependency_graph_mermaid(model)
    assert "No directories or files recorded" in render_module_graph_mermaid(model)
    assert "No architecture facts detected" in render_architecture_overview_mermaid(model)
