"""Tests for repository_scan.scan_repository."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from repository_scan import scan_repository


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
    (repo / ".github" / "workflows" / "ci.yml").write_text("on: [push]\n", encoding="utf-8")
    (repo / "Dockerfile").write_text("FROM python:3.11\n", encoding="utf-8")
    return repo


def test_scan_python_repo(tmp_path):
    repo = make_python_repo(tmp_path)
    inv = scan_repository(repo)
    assert inv.repository_name == "demo-python"
    assert "Python" in inv.languages
    assert "FastAPI" in inv.frameworks
    assert any("pip" in m or "Poetry" in m for m in inv.package_managers)
    assert "pytest" in inv.test_frameworks or any("pytest" in t for t in inv.test_frameworks)
    assert "README.md" in inv.important_files
    assert ".github/workflows/ci.yml" in inv.ci_cd_files
    assert "Dockerfile" in inv.ci_cd_files
    assert "src" in inv.top_level_directories
    assert any("pytest" in c for c in inv.test_instructions)


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
