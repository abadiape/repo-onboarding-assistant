"""Tests for analyzer selection and model enrichment."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzers import (
    DEFAULT_ANALYZERS,
    GenericAnalyzer,
    NodeJsAnalyzer,
    PhpAnalyzer,
    PythonAnalyzer,
    select_analyzers,
)
from models import Dependency, RepositoryFile, RepositoryModel
from repository_scan import scan_repository


def test_selects_generic_and_matching_language_analyzers():
    model = RepositoryModel(
        repository_name="mixed",
        languages=["JavaScript", "Python"],
        files=[
            RepositoryFile("package.json", "manifest"),
            RepositoryFile("pyproject.toml", "manifest"),
        ],
    )

    selected = select_analyzers(model)

    assert [type(analyzer) for analyzer in selected] == [
        GenericAnalyzer,
        NodeJsAnalyzer,
        PythonAnalyzer,
    ]


def test_generic_analyzer_detects_structure_and_classifies_dependency_scopes():
    model = RepositoryModel(
        repository_name="generic",
        dependencies=[
            Dependency("runtime-lib", "1", "pyproject.toml"),
            Dependency("pytest", "8", "requirements-dev.txt", "development"),
            Dependency("hatchling", "1", "pyproject.toml", "build"),
        ],
        directories=["src", "tests", "docs"],
        files=[
            RepositoryFile("README.md", "readme"),
            RepositoryFile("Makefile", "file"),
            RepositoryFile(".editorconfig", "file"),
        ],
    )

    GenericAnalyzer().analyze(model)

    assert [item.category for item in model.dependencies] == [
        "library", "development", "build-tool"
    ]
    assert {
        "structure:src",
        "structure:tests",
        "structure:docs",
        "convention:readme",
        "convention:makefile",
        "convention:editorconfig",
    } <= set(model.detected_patterns)


def test_node_analyzer_detects_frameworks_and_dependency_categories():
    model = RepositoryModel(
        repository_name="node",
        dependencies=[
            Dependency("react", "^18", "package.json"),
            Dependency("next", "^14", "package.json"),
            Dependency("@nestjs/core", "^10", "package.json"),
            Dependency("express", "^4", "package.json"),
            Dependency("vitest", "^1", "package.json", "development"),
        ],
        directories=["src", "app"],
        files=[RepositoryFile("package.json", "manifest")],
    )

    NodeJsAnalyzer().analyze(model)

    assert {"React", "Next.js", "NestJS", "Express"} <= set(model.frameworks)
    assert all(item.category == "framework" for item in model.dependencies[:4])
    assert model.dependencies[-1].category == "testing"
    assert "next:app-router" in model.detected_patterns


def test_python_analyzer_detects_frameworks_and_conventions():
    model = RepositoryModel(
        repository_name="python",
        languages=["Python"],
        dependencies=[
            Dependency("Django", "5", "requirements.txt"),
            Dependency("Flask", "3", "requirements.txt"),
            Dependency("fastapi", "0.1", "requirements.txt"),
            Dependency("pytest", "8", "requirements-dev.txt", "development"),
        ],
        files=[
            RepositoryFile("manage.py", "file"),
            RepositoryFile("src/app.py", "source", "Python"),
            RepositoryFile("src/project/__init__.py", "source", "Python"),
        ],
    )

    PythonAnalyzer().analyze(model)

    assert {"Django", "Flask", "FastAPI"} <= set(model.frameworks)
    assert model.dependencies[0].category == "framework"
    assert model.dependencies[-1].category == "testing"
    assert {"django:manage-py", "python:src-layout", "python:package-layout"} <= set(
        model.detected_patterns
    )


def test_php_analyzer_detects_frameworks_and_dependency_categories():
    model = RepositoryModel(
        repository_name="php",
        dependencies=[
            Dependency("laravel/framework", "^11", "composer.json"),
            Dependency("symfony/console", "^7", "composer.json"),
            Dependency("phpunit/phpunit", "^10", "composer.json", "development"),
        ],
        directories=["app", "routes", "config", "src", "templates"],
        files=[
            RepositoryFile("composer.json", "manifest"),
            RepositoryFile("artisan", "file"),
            RepositoryFile("bin/console", "file"),
        ],
    )

    PhpAnalyzer().analyze(model)

    assert {"Laravel", "Symfony"} <= set(model.frameworks)
    assert model.dependencies[0].category == "framework"
    assert model.dependencies[1].category == "framework"
    assert model.dependencies[2].category == "testing"
    assert {
        "laravel:directory-layout",
        "symfony:directory-layout",
        "php:composer",
    } <= set(model.detected_patterns)


def test_scan_can_run_an_additional_analyzer(tmp_path):
    repo = tmp_path / "plugin-repo"
    repo.mkdir()
    (repo / "package.json").write_text("{}", encoding="utf-8")

    class MarkerAnalyzer:
        def supports(self, model: RepositoryModel) -> bool:
            return bool(model.repository_name)

        def analyze(self, model: RepositoryModel) -> None:
            model.detected_patterns.append("custom:marker")

    model = scan_repository(repo, analyzers=(*DEFAULT_ANALYZERS, MarkerAnalyzer()))

    assert "custom:marker" in model.detected_patterns
    assert "manifest:package.json" in model.detected_patterns


def test_scan_preserves_framework_detection_from_legacy_manifest_files(tmp_path):
    repo = tmp_path / "legacy-manifests"
    repo.mkdir()
    (repo / "setup.py").write_text(
        'install_requires = ["Flask"]\n', encoding="utf-8"
    )
    (repo / "pom.xml").write_text(
        "<project><build><plugins><plugin><artifactId>"
        "spring-boot-maven-plugin</artifactId></plugin></plugins></build></project>",
        encoding="utf-8",
    )

    model = scan_repository(repo)

    assert {"Flask", "Spring Boot"} <= set(model.frameworks)
