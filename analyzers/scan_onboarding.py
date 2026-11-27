"""Scan onboarding."""
from __future__ import annotations

from pathlib import Path

from analyzers.scan_io import _read_text

IMPORTANT_FILENAMES = {
    "README.md", "README.rst", "README.txt", "README",
    "LICENSE", "LICENSE.md", "LICENSE.txt",
    "CHANGELOG.md", "CHANGELOG.rst", "CHANGELOG",
    "CONTRIBUTING.md", "CONTRIBUTING.rst", "CONTRIBUTING",
    "CODE_OF_CONDUCT.md", "SECURITY.md",
    "LOCAL_SETUP.md", "SETUP.md", "INSTALL.md", "DEVELOPMENT.md",
    "DEV_SETUP.md", "GETTING_STARTED.md",
    "pyproject.toml", "requirements.txt", "requirements-dev.txt",
    "setup.py", "setup.cfg", "Pipfile", "poetry.lock",
    "package.json", "tsconfig.json",
    "composer.json", "artisan",
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "go.mod", "Cargo.toml",
    "Gemfile", "Makefile", "Dockerfile", "docker-compose.yml",
    "docker-compose.yaml",
}


CI_CD_PATTERNS = {
    ".github/workflows",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    "azure-pipelines.yml",
    ".circleci/config.yml",
    ".travis.yml",
    ".buildkite/pipeline.yml",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
}


SETUP_GUIDE_FILENAMES = {
    "local_setup.md", "setup.md", "install.md", "development.md",
    "dev_setup.md", "getting_started.md",
}


def _detect_patterns(
    files_by_name: dict[str, list[Path]], ci_cd_files: list[str]
) -> list[str]:
    patterns: list[str] = []
    if any(name.lower().startswith("readme") for name in files_by_name):
        patterns.append("readme")
    manifest_names = {
        "package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
        "composer.json", "pom.xml", "build.gradle", "build.gradle.kts",
        "Cargo.toml", "go.mod",
    }
    patterns.extend(
        f"manifest:{name}" for name in sorted(manifest_names & files_by_name.keys())
    )
    if any(name.lower().startswith("dockerfile") or name.lower().startswith("docker-compose") for name in files_by_name):
        patterns.append("docker")
    if any(path.startswith(".github/workflows/") for path in ci_cd_files):
        patterns.append("github-actions")
    if any(
        not Path(path).name.lower().startswith(("dockerfile", "docker-compose"))
        for path in ci_cd_files
    ):
        patterns.append("ci-cd")
    return patterns


def _extract_readme_summary(root: Path, files_by_name: dict[str, list[Path]]) -> str:
    candidates = [
        path for path in files_by_name.get("README.md", [])
        if path.parent == root
    ]
    if not candidates:
        return ""

    lines: list[str] = []
    for line in _read_text(candidates[0], limit=20_000).splitlines():
        stripped = line.strip()
        if not stripped:
            if lines:
                break
            continue
        if stripped.startswith(("#", "![")):
            continue
        if stripped.startswith(("```", "~~~")):
            break
        lines.append(stripped)
    return " ".join(lines)[:500]


def _collect_ci_cd_files(
    root: Path, files_by_name: dict[str, list[Path]]
) -> list[str]:
    found: list[str] = []
    candidates = [
        ".github/workflows",
        ".gitlab-ci.yml",
        "Jenkinsfile",
        "azure-pipelines.yml",
        ".circleci/config.yml",
        ".travis.yml",
        ".buildkite/pipeline.yml",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    ]
    for candidate in candidates:
        path = root / candidate
        if path.is_dir():
            for child in sorted(path.iterdir()):
                if child.is_file():
                    found.append(str(child.relative_to(root)))
        elif path.is_file():
            found.append(candidate)
    for name, paths in files_by_name.items():
        if name.lower().startswith(("dockerfile", "docker-compose")):
            found.extend(str(path.relative_to(root)) for path in paths)
    return sorted(set(found))


def _collect_ci_commands(root: Path, ci_cd_files: list[str]) -> list[dict[str, str]]:
    commands: list[dict[str, str]] = []
    for relative in ci_cd_files:
        if Path(relative).suffix.lower() not in {".yml", ".yaml"}:
            continue
        for line in _read_text(root / relative).splitlines():
            stripped = line.strip()
            if not stripped.startswith("- run:"):
                continue
            command = stripped.removeprefix("- run:").strip()
            if command:
                commands.append({"source": relative, "command": command})
    return commands


def _collect_important_files(root: Path, files_by_name: dict[str, list[Path]]) -> list[str]:
    important: list[str] = []
    for name, paths in files_by_name.items():
        if name in IMPORTANT_FILENAMES:
            for p in paths:
                try:
                    rel = str(p.relative_to(root))
                except ValueError:
                    continue
                # Only top-level or well-known config locations
                if len(Path(rel).parts) <= 2:
                    important.append(rel)
    # Prefer README / entry docs first
    def sort_key(p: str) -> tuple:
        base = Path(p).name.lower()
        order = {"readme.md": 0, "readme.rst": 1, "readme": 2}
        return (order.get(base, 10), p)

    important = sorted(set(important), key=sort_key)
    return important[:30]


def _collect_onboarding_docs(
    root: Path, files_by_name: dict[str, list[Path]]
) -> tuple[list[str], list[str]]:
    docs: set[str] = set()
    setup_guides: set[str] = set()
    for paths in files_by_name.values():
        for path in paths:
            try:
                relative_path = path.relative_to(root)
            except ValueError:
                continue
            if len(relative_path.parts) > 2 or path.suffix.lower() not in {".md", ".rst"}:
                continue

            relative = relative_path.as_posix()
            name = path.name.lower()
            if name.startswith("readme") or name in {
                "contributing.md", "contributing.rst", "local_setup.md", "setup.md",
                "install.md", "development.md", "dev_setup.md", "getting_started.md",
            } or relative_path.parts[0].lower() == "docs":
                docs.add(relative)
            if name in SETUP_GUIDE_FILENAMES:
                setup_guides.add(relative)

    doc_order = {
        "readme.md": 0,
        "local_setup.md": 1,
        "setup.md": 2,
        "getting_started.md": 3,
        "development.md": 4,
        "dev_setup.md": 5,
        "install.md": 6,
        "contributing.md": 7,
    }

    def sort_key(path: str) -> tuple[int, str]:
        name = Path(path).name.lower()
        return (doc_order.get(name, 10), path)

    return sorted(docs, key=sort_key), sorted(setup_guides, key=sort_key)


def _clean_heading(heading: str) -> str:
    heading = heading.strip()
    if heading and heading[0].isdigit():
        separator = next((i for i, char in enumerate(heading) if char.isspace()), -1)
        if separator > 0 and heading[:separator].rstrip(".)").isdigit():
            return heading[separator:].strip()
    return heading


def _extract_documented_setup_commands(
    root: Path, docs: list[str]
) -> list[dict[str, str]]:
    """Collect shell commands from relevant Markdown code blocks; never execute them."""
    commands: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    relevant_headings = (
        "setup", "install", "build", "test", "run", "develop", "quick start",
        "getting started", "container", "environment",
    )
    shell_languages = {"bash", "sh", "shell", "zsh", "console"}

    for relative in docs:
        path = root / relative
        is_setup_guide = path.name.lower() in SETUP_GUIDE_FILENAMES
        text = _read_text(path)
        heading = ""
        fence_language = ""
        in_fence = False

        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                if not in_fence:
                    fence_language = stripped[3:].strip().split(maxsplit=1)[0].lower() if stripped[3:].strip() else ""
                    in_fence = True
                    continue
                in_fence = False
                fence_language = ""
                continue

            if not in_fence:
                if stripped.startswith("#"):
                    heading = _clean_heading(stripped.lstrip("#"))
                continue

            heading_is_relevant = any(term in heading.lower() for term in relevant_headings)
            if fence_language not in shell_languages or not (is_setup_guide or heading_is_relevant):
                continue
            if not stripped or stripped.startswith("#"):
                continue

            command = stripped.removeprefix("$ ").removeprefix("> ").strip()
            key = (relative, heading, command)
            if key not in seen:
                commands.append({
                    "source": relative,
                    "section": heading,
                    "command": command,
                })
                seen.add(key)
            if len(commands) >= 40:
                return commands

    return commands


def _collect_entry_points(root: Path, files_by_name: dict[str, list[Path]]) -> list[str]:
    candidates = [
        "manage.py", "app.py", "main.py", "run.py", "wsgi.py", "asgi.py",
        "artisan", "index.js", "index.ts",
        "src/index.js", "src/index.ts", "src/main.ts", "src/main.py",
        "src/app.py", "cmd/main.go", "src/main.rs", "Program.cs",
    ]
    found: list[str] = []
    for candidate in candidates:
        if (root / candidate).is_file():
            found.append(candidate)
    # src/<repo>.main style fallbacks
    for name in ("__main__.py", "cli.py"):
        for p in files_by_name.get(name, [])[:3]:
            try:
                found.append(str(p.relative_to(root)))
            except ValueError:
                continue
    return found[:15]
