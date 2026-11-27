"""Tests for repository_scan.scan_repository."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzers.repository_scan import scan_repository
from models.models import Dependency, RepositoryModel


def test_openapi_size_limit_reports_skipped_candidate(tmp_path, monkeypatch):
    from analyzers import openapi_inventory

    (tmp_path / "openapi.json").write_text(
        '{"openapi": "3.0.0", "paths": {"/items": {"get": {}}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(openapi_inventory, "_MAX_SPEC_BYTES", 20)
    inventory = scan_repository(tmp_path).api_inventory
    assert inventory["endpoints"] == []
    assert any("size limit" in warning and "openapi.json" in warning for warning in inventory["warnings"])


def test_openapi_reports_ambiguous_references_and_rejects_unsafe_yaml(tmp_path):
    (tmp_path / "openapi.yaml").write_text(
        "openapi: 3.1.0\n"
        "paths:\n"
        "  /cycle:\n"
        "    $ref: '#/components/pathItems/Cycle'\n"
        "  /conflict:\n"
        "    $ref: '#/components/pathItems/Shared'\n"
        "    get: {}\n"
        "  /valid:\n"
        "    $ref: '#/components/pathItems/Shared'\n"
        "components:\n"
        "  pathItems:\n"
        "    Cycle:\n"
        "      $ref: '#/components/pathItems/Cycle'\n"
        "    Shared:\n"
        "      get: {}\n",
        encoding="utf-8",
    )
    (tmp_path / "swagger-unsafe.yaml").write_text(
        "swagger: '2.0'\npaths: !!python/object/apply:os.system ['echo unsafe']\n",
        encoding="utf-8",
    )
    inventory = scan_repository(tmp_path).api_inventory
    assert [(item["method"], item["path"]) for item in inventory["endpoints"]] == [
        ("GET", "/valid")
    ]
    assert any("Unresolved or external path reference" in warning for warning in inventory["warnings"])
    assert any("Conflicting path reference operations" in warning for warning in inventory["warnings"])
    assert any("swagger-unsafe.yaml" in warning for warning in inventory["warnings"])


def test_unrelated_json_containing_nested_spec_marker_is_not_an_api_warning(tmp_path):
    (tmp_path / "data.json").write_text('[{"openapi": "example"}]', encoding="utf-8")
    assert scan_repository(tmp_path).api_inventory == {"endpoints": [], "warnings": []}


def test_openapi_does_not_read_specification_symlink_outside_repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(
        '{"openapi": "3.0.0", "paths": {"/outside": {"get": {}}}}',
        encoding="utf-8",
    )
    (repo / "openapi.json").symlink_to(outside)
    inventory = scan_repository(repo).api_inventory
    assert inventory["endpoints"] == []
    assert any("outside the repository" in warning for warning in inventory["warnings"])


def make_python_repo(base: Path) -> Path:
    repo = base / "demo-python"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "demo"\ndependencies = ["fastapi", "pytest"]\n', encoding="utf-8"
    )
    (repo / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (repo / "tests" / "test_main.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "on: [push]\njobs:\n  test:\n    steps:\n      - run: pytest -q\n",
        encoding="utf-8",
    )
    (repo / "Dockerfile").write_text("FROM python:3.11\n", encoding="utf-8")
    return repo


def test_scan_python_repo(tmp_path):
    repo = make_python_repo(tmp_path)
    inv = scan_repository(repo)
    assert isinstance(inv, RepositoryModel)
    assert inv.repository_name == "demo-python"
    assert "Python" in inv.languages
    assert "FastAPI" in inv.frameworks
    assert any("pip" in m or "Poetry" in m for m in inv.package_managers)
    assert "pytest" in inv.test_frameworks or any("pytest" in t for t in inv.test_frameworks)
    assert "README.md" in inv.important_files
    assert ".github/workflows/ci.yml" in inv.ci_cd_files
    assert {"source": ".github/workflows/ci.yml", "command": "pytest -q"} in inv.ci_commands
    assert "Dockerfile" in inv.ci_cd_files
    assert "src" in inv.top_level_directories
    assert any("pytest" in c for c in inv.test_instructions)
    assert "src" in inv.directories
    assert any(file.path == "README.md" and file.kind == "readme" for file in inv.files)
    assert "readme" in inv.detected_patterns
    assert any(
        dependency.name == "fastapi" and dependency.source == "pyproject.toml"
        for dependency in inv.dependencies
    )


def test_scan_normalizes_supported_manifests_and_ci_files(tmp_path):
    repo = tmp_path / "multi-manifest"
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / "infra").mkdir()
    (repo / "README.md").write_text("# Multi\n", encoding="utf-8")
    (repo / "package.json").write_text(
        '{"dependencies":{"react":"^18"},"devDependencies":{"jest":"^29"}}',
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling>=1"]\n'
        '[project]\ndependencies = ["fastapi>=0.1"]\n'
        '[project.optional-dependencies]\ndev = ["ruff>=0.1"]\n',
        encoding="utf-8",
    )
    (repo / "requirements.txt").write_text("requests==2.31\n", encoding="utf-8")
    (repo / "composer.json").write_text(
        '{"require":{"vendor/library":"^1.0"}}', encoding="utf-8"
    )
    (repo / "pom.xml").write_text(
        "<project><dependencies><dependency><groupId>org.demo</groupId>"
        "<artifactId>demo-lib</artifactId><version>1.2</version>"
        "</dependency></dependencies></project>",
        encoding="utf-8",
    )
    (repo / "build.gradle").write_text(
        "implementation 'org.example:core:2.0'\n", encoding="utf-8"
    )
    (repo / "Cargo.toml").write_text(
        '[dependencies]\nserde = "1.0"\n', encoding="utf-8"
    )
    (repo / "go.mod").write_text(
        "module example.com/demo\nrequire example.com/lib v1.2.3\n",
        encoding="utf-8",
    )
    (repo / "infra" / "Dockerfile.worker").write_text("FROM alpine\n", encoding="utf-8")
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "jobs:\n  test:\n    steps:\n      - run: npm test\n", encoding="utf-8"
    )

    model = scan_repository(repo)
    names = {dependency.name for dependency in model.dependencies}

    assert {
        "react",
        "jest",
        "hatchling",
        "fastapi",
        "ruff",
        "requests",
        "vendor/library",
        "org.demo:demo-lib",
        "org.example:core",
        "serde",
        "example.com/lib",
    } <= names
    assert any(
        isinstance(dependency, Dependency)
        and dependency.name == "jest"
        and dependency.scope == "development"
        for dependency in model.dependencies
    )
    assert any(
        dependency.name == "hatchling" and dependency.scope == "build"
        for dependency in model.dependencies
    )
    assert any(
        dependency.name == "ruff" and dependency.scope == "optional:dev"
        for dependency in model.dependencies
    )
    assert "infra" in model.directories
    assert any(file.path == "infra/Dockerfile.worker" and file.kind == "docker" for file in model.files)
    assert "github-actions" in model.detected_patterns
    assert "docker" in model.detected_patterns
    assert "ci-cd" in model.detected_patterns
    assert "infra/Dockerfile.worker" in model.ci_cd_files
    restored = RepositoryModel.from_dict(model.to_dict())
    assert restored.dependencies == model.dependencies
    assert restored.files == model.files


def test_scan_collects_local_setup_guide_and_documented_commands(tmp_path):
    repo = tmp_path / "demo-setup"
    repo.mkdir()
    (repo / ".ruff_cache").mkdir()
    (repo / "README.md").write_text(
        "# Demo\n\nA small local-first toolkit for developer onboarding.\n",
        encoding="utf-8",
    )
    (repo / "LOCAL_SETUP.md").write_text(
        "# Local setup\n\n## Install\n\n```bash\n"
        "python -m venv .venv\npip install -e \".[dev]\"\n"
        "```\n\n## Run\n\n```sh\npytest\n```\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n',
        encoding="utf-8",
    )

    inv = scan_repository(repo)

    assert "LOCAL_SETUP.md" in inv.important_files
    assert "LOCAL_SETUP.md" in inv.onboarding_docs
    assert "LOCAL_SETUP.md" in inv.setup_guides
    assert inv.readme_summary == "A small local-first toolkit for developer onboarding."
    assert "Python build (Hatch)" in inv.build_tools
    assert [item["command"] for item in inv.documented_setup_commands] == [
        "python -m venv .venv",
        'pip install -e ".[dev]"',
        "pytest",
    ]
    assert ".ruff_cache" not in inv.top_level_directories


def test_scan_node_laravel_and_errors(tmp_path):
    repo = tmp_path / "demo-node"
    repo.mkdir()
    (repo / "package.json").write_text(
        json.dumps({"dependencies": {"react": "^18.0.0", "next": "^14.0.0"}}), encoding="utf-8"
    )
    (repo / "tsconfig.json").write_text("{}", encoding="utf-8")
    inv = scan_repository(repo)
    assert "JavaScript" in inv.languages
    assert "TypeScript" in inv.languages
    assert "React" in inv.frameworks
    assert "Next.js" in inv.frameworks

    laravel = tmp_path / "demo-laravel"
    laravel.mkdir()
    (laravel / "composer.json").write_text(
        json.dumps({"require": {"laravel/framework": "^10.0"}}), encoding="utf-8"
    )
    (laravel / "artisan").write_text("#!/usr/bin/env php\n", encoding="utf-8")
    inv2 = scan_repository(laravel)
    assert "PHP" in inv2.languages
    assert "Laravel" in inv2.frameworks

    import pytest
    with pytest.raises(FileNotFoundError):
        scan_repository(tmp_path / "does-not-exist")
    with pytest.raises(NotADirectoryError):
        some_file = tmp_path / "file.txt"
        some_file.write_text("x", encoding="utf-8")
        scan_repository(some_file)
