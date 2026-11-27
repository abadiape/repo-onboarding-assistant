"""Scan files."""
from __future__ import annotations

from pathlib import Path

from analyzers.repository_relevance import classify_path
from models.models import RepositoryFile

IGNORED_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".venv", "venv", ".env",
    ".ruff_cache", ".mypy_cache", ".cache", ".tox", ".nox",
    ".next", "dist", "build", "target",
    ".idea", ".vscode",
}


EXTENSION_TO_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".php": "PHP",
    ".java": "Java",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C/C++",
    ".vue": "Vue",
    ".svelte": "Svelte",
}


def _collect_directories(root: Path) -> list[str]:
    directories: list[str] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda path: path.name)
        except OSError:
            continue
        for child in children:
            if not child.is_dir() or child.is_symlink():
                continue
            relative = child.relative_to(root).as_posix()
            level, _ = classify_path(relative)
            if child.name in IGNORED_DIRS and child.name not in {"build", "dist", "target"}:
                continue
            directories.append(relative)
            if level not in {"low", "ignored"}:
                stack.append(child)
    return sorted(directories)


def _collect_repository_files(
    root: Path,
    files_by_name: dict[str, list[Path]],
    ci_cd_files: list[str],
) -> list[RepositoryFile]:
    ci_paths = set(ci_cd_files)
    manifests = {
        "package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
        "composer.json", "pom.xml", "build.gradle", "build.gradle.kts",
        "Cargo.toml", "go.mod",
    }
    files = [path for paths in files_by_name.values() for path in paths]
    records: list[RepositoryFile] = []
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        basename = path.name
        if basename.lower().startswith("dockerfile") or basename.lower().startswith("docker-compose"):
            kind = "docker"
        elif relative in ci_paths:
            kind = "ci"
        elif basename.lower().startswith("readme"):
            kind = "readme"
        elif basename in manifests:
            kind = "manifest"
        elif path.suffix.lower() in EXTENSION_TO_LANGUAGE:
            kind = "source"
        else:
            kind = "file"
        records.append(RepositoryFile(
            path=relative,
            kind=kind,
            language=EXTENSION_TO_LANGUAGE.get(path.suffix.lower()),
        ))
    return records


def _iter_project_files(root: Path):
    """Yield files under root, pruning ignored directories."""
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.name in IGNORED_DIRS and entry.is_dir():
                continue
            if entry.is_dir() and not entry.is_symlink():
                if classify_path(entry.relative_to(root).as_posix())[0] not in {"low", "ignored"}:
                    stack.append(entry)
            elif entry.is_file():
                yield entry
