"""Repository Scan Capability (local to this skill).

NOT part of the harness. Reusable module inside the skill.

Scans a repository using convention-based inspection only:
filenames, manifest contents (parsed lightly as text/JSON), and
file-extension counts. No AST parsing, no external parsers.
"""
from __future__ import annotations

import json
from pathlib import Path

from models import RepositoryInventory

# Directories never treated as source structure or recursed into
# when counting extensions.
IGNORED_DIRS = {
    ".git", ".hg", ".svn",
    "__pycache__", ".pytest_cache", ".venv", "venv", ".env",
    ".ruff_cache", ".mypy_cache", ".cache", ".tox", ".nox",
    "node_modules", ".next", "dist", "build", "target",
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


def _read_text(path: Path, limit: int = 200_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:limit]
    except (OSError, UnicodeError):
        return ""


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return {}


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
        if stripped.startswith("#") or stripped.startswith("!["):
            continue
        if stripped.startswith("```") or stripped.startswith("~~~"):
            break
        lines.append(stripped)
    return " ".join(lines)[:500]


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
                stack.append(entry)
            elif entry.is_file():
                yield entry


def _detect_languages(root: Path, files_by_name: dict[str, list[Path]]) -> list[str]:
    languages: list[str] = []

    def has(name: str) -> bool:
        return name in files_by_name

    if has("pyproject.toml") or has("requirements.txt") or has("setup.py") or has("Pipfile"):
        languages.append("Python")
    if has("package.json"):
        languages.append("JavaScript")
    if has("tsconfig.json"):
        languages.append("TypeScript")
    if has("composer.json"):
        languages.append("PHP")
    if has("pom.xml") or has("build.gradle") or has("build.gradle.kts"):
        languages.append("Java")
    if has("go.mod"):
        languages.append("Go")
    if has("Cargo.toml"):
        languages.append("Rust")
    if has("Gemfile"):
        languages.append("Ruby")
    dotnet_hit = any(
        paths for name, paths in files_by_name.items()
        if name.endswith(".csproj") or name.endswith(".sln")
    )
    if dotnet_hit:
        languages.append("C#")

    # Fallback: extension counts (top 3, only when manifest detection found nothing
    # for that language family, or to add genuinely present extra languages).
    ext_counts: dict[str, int] = {}
    for file_path in _iter_project_files(root):
        lang = EXTENSION_TO_LANGUAGE.get(file_path.suffix.lower())
        if lang:
            ext_counts[lang] = ext_counts.get(lang, 0) + 1

    for lang, count in sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True):
        if count >= 3 and lang not in languages:
            # Avoid double-counting JS/TS companions of the same codebase:
            # only add via extensions when manifest detection missed everything.
            languages.append(lang)
        if len(languages) >= 6:
            break

    # Keep manifest-detected languages first, in a stable priority order.
    priority = ["Python", "JavaScript", "TypeScript", "PHP", "Java", "C#", "Go", "Rust", "Ruby"]
    languages.sort(key=lambda l: (priority.index(l) if l in priority else 99, l))
    return languages


def _detect_frameworks(root: Path, files_by_name: dict[str, list[Path]]) -> list[str]:
    frameworks: list[str] = []

    pkg_json: dict = {}
    if "package.json" in files_by_name:
        pkg_json = _read_json(files_by_name["package.json"][0])
    deps: dict = {}
    for section in ("dependencies", "devDependencies", "peerDependencies"):
        section_deps = pkg_json.get(section, {})
        if isinstance(section_deps, dict):
            deps.update(section_deps)

    def has_dep(name: str) -> bool:
        return name in deps

    # --- JavaScript / TypeScript ---
    if has_dep("next"):
        frameworks.append("Next.js")
    if has_dep("react"):
        frameworks.append("React")
    if has_dep("vue"):
        frameworks.append("Vue")
    if has_dep("@angular/core"):
        frameworks.append("Angular")
    if has_dep("express"):
        frameworks.append("Express")
    if has_dep("nestjs") or has_dep("@nestjs/core"):
        frameworks.append("NestJS")
    if has_dep("svelte"):
        frameworks.append("Svelte")

    # --- Python (lightweight text search in manifests) ---
    py_manifest = ""
    for name in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.py", "Pipfile"):
        for p in files_by_name.get(name, []):
            py_manifest += _read_text(p).lower() + "\n"
    if "django" in py_manifest or "manage.py" in files_by_name:
        frameworks.append("Django")
    if "fastapi" in py_manifest:
        frameworks.append("FastAPI")
    if "flask" in py_manifest and "Django" not in frameworks:
        frameworks.append("Flask")
    elif "flask" in py_manifest:
        frameworks.append("Flask")

    # --- PHP ---
    if "artisan" in files_by_name and "composer.json" in files_by_name:
        frameworks.append("Laravel")
    elif "composer.json" in files_by_name:
        composer_text = _read_text(files_by_name["composer.json"][0]).lower()
        if "laravel/framework" in composer_text:
            frameworks.append("Laravel")
        if "symfony/" in composer_text:
            frameworks.append("Symfony")

    # --- Java ---
    for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
        for p in files_by_name.get(name, []):
            text = _read_text(p).lower()
            if "spring-boot" in text or "springframework" in text:
                frameworks.append("Spring Boot")
                break

    # --- .NET / others via file conventions ---
    if any(n.endswith(".csproj") for n in files_by_name):
        frameworks.append(".NET")

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for fw in frameworks:
        if fw not in seen:
            seen.add(fw)
            unique.append(fw)
    return unique


def _detect_package_managers(files_by_name: dict[str, list[Path]]) -> list[str]:
    managers: list[str] = []
    if "pyproject.toml" in files_by_name:
        text = _read_text(files_by_name["pyproject.toml"][0]).lower()
        if "[tool.poetry]" in text or "poetry" in text:
            managers.append("Poetry")
        else:
            managers.append("pip (pyproject.toml)")
    if "requirements.txt" in files_by_name and not any(m.startswith("pip") for m in managers):
        managers.append("pip")
    if "Pipfile" in files_by_name:
        managers.append("Pipenv")
    if "package.json" in files_by_name:
        managers.append("npm")
    if "yarn.lock" in files_by_name:
        managers.append("yarn")
    if "pnpm-lock.yaml" in files_by_name:
        managers.append("pnpm")
    if "composer.json" in files_by_name:
        managers.append("Composer")
    if "pom.xml" in files_by_name:
        managers.append("Maven")
    if "build.gradle" in files_by_name or "build.gradle.kts" in files_by_name:
        managers.append("Gradle")
    if any(n.endswith(".csproj") for n in files_by_name):
        managers.append("NuGet/dotnet")
    if "go.mod" in files_by_name:
        managers.append("Go modules")
    if "Cargo.toml" in files_by_name:
        managers.append("Cargo")
    if "Gemfile" in files_by_name:
        managers.append("Bundler")
    return managers


def _detect_build_tools(files_by_name: dict[str, list[Path]]) -> list[str]:
    tools: list[str] = []
    if "pyproject.toml" in files_by_name:
        pyproject_text = _read_text(files_by_name["pyproject.toml"][0]).lower()
        backends = (
            ("poetry.core.masonry.api", "Poetry"),
            ("hatchling.build", "Hatch"),
            ("setuptools.build_meta", "setuptools"),
            ("flit_core.buildapi", "Flit"),
            ("pdm.backend", "PDM"),
        )
        tools.append(
            next(
                (f"Python build ({label})" for backend, label in backends if backend in pyproject_text),
                "Python build (pyproject.toml)",
            )
        )
    elif "setup.py" in files_by_name:
        tools.append("Python build (setuptools)")
    if "requirements.txt" in files_by_name:
        tools.append("pip")
    if "package.json" in files_by_name:
        pkg = _read_json(files_by_name["package.json"][0])
        scripts = pkg.get("scripts", {})
        if isinstance(scripts, dict) and "build" in scripts:
            tools.append(f"npm run build (`{scripts['build']}`)")
        else:
            tools.append("npm scripts")
    if "tsconfig.json" in files_by_name:
        tools.append("tsc (TypeScript compiler)")
    if "Makefile" in files_by_name:
        tools.append("Make")
    if "pom.xml" in files_by_name:
        tools.append("Maven")
    if "build.gradle" in files_by_name or "build.gradle.kts" in files_by_name:
        tools.append("Gradle")
    if any(n.endswith(".csproj") for n in files_by_name) or any(n.endswith(".sln") for n in files_by_name):
        tools.append("dotnet build")
    if "go.mod" in files_by_name:
        tools.append("go build")
    if "Cargo.toml" in files_by_name:
        tools.append("cargo build")
    if "artisan" in files_by_name:
        tools.append("artisan (Laravel)")
    return tools


def _detect_test_frameworks(
    root: Path, files_by_name: dict[str, list[Path]], package_json: dict
) -> list[str]:
    frameworks: list[str] = []

    py_text = ""
    for name in ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "setup.cfg"):
        for p in files_by_name.get(name, []):
            py_text += _read_text(p).lower() + "\n"
    if "pytest" in py_text:
        frameworks.append("pytest")
    # tests/ or test_*.py files imply pytest/unittest even without manifest mention
    has_py_tests = any(
        n.startswith("test_") and n.endswith(".py") or n.endswith("_test.py")
        for n in files_by_name
    ) or "tests" in {p.name for p in root.iterdir() if p.is_dir()}
    if has_py_tests and "pytest" not in frameworks:
        frameworks.append("pytest/unittest (test files found)")

    deps: dict = {}
    for section in ("dependencies", "devDependencies"):
        section_deps = package_json.get(section, {})
        if isinstance(section_deps, dict):
            deps.update(section_deps)
    for dep, label in (
        ("jest", "Jest"), ("vitest", "Vitest"), ("mocha", "Mocha"),
        ("playwright", "Playwright"), ("cypress", "Cypress"),
    ):
        if dep in deps:
            frameworks.append(label)

    if "composer.json" in files_by_name:
        composer_text = _read_text(files_by_name["composer.json"][0]).lower()
        if "phpunit" in composer_text:
            frameworks.append("PHPUnit")
    if "phpunit.xml" in files_by_name or "phpunit.xml.dist" in files_by_name:
        if "PHPUnit" not in frameworks:
            frameworks.append("PHPUnit")

    for name in ("pom.xml", "build.gradle", "build.gradle.kts"):
        for p in files_by_name.get(name, []):
            if "junit" in _read_text(p).lower():
                frameworks.append("JUnit")
                break

    if "go.mod" in files_by_name:
        frameworks.append("go test")
    if "Cargo.toml" in files_by_name:
        frameworks.append("cargo test")
    if "Gemfile" in files_by_name:
        gem_text = _read_text(files_by_name["Gemfile"][0]).lower()
        if "rspec" in gem_text:
            frameworks.append("RSpec")

    return frameworks


def _collect_ci_cd_files(root: Path) -> list[str]:
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
    return found


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
            if stripped.startswith("```") or stripped.startswith("~~~"):
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


def scan_repository(repo_path: str | Path) -> RepositoryInventory:
    """Scan a repository directory and return its inventory.

    Raises:
        FileNotFoundError: if repo_path does not exist.
        NotADirectoryError: if repo_path is not a directory.
    """
    root = Path(repo_path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path does not exist: {repo_path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")

    files_by_name: dict[str, list[Path]] = {}
    for file_path in _iter_project_files(root):
        files_by_name.setdefault(file_path.name, []).append(file_path)

    package_json: dict = {}
    if "package.json" in files_by_name:
        package_json = _read_json(files_by_name["package.json"][0])

    languages = _detect_languages(root, files_by_name)
    frameworks = _detect_frameworks(root, files_by_name)
    onboarding_docs, setup_guides = _collect_onboarding_docs(root, files_by_name)
    documented_setup_commands = _extract_documented_setup_commands(
        root, onboarding_docs
    )

    top_level_directories = sorted(
        p.name for p in root.iterdir() if p.is_dir() and p.name not in IGNORED_DIRS
    )

    ci_cd_files = _collect_ci_cd_files(root)
    build_instructions = _build_instructions(root, files_by_name, package_json)
    test_instructions = _test_instructions(package_json, files_by_name)

    return RepositoryInventory(
        repository_name=root.name,
        root_path=str(root),
        readme_summary=_extract_readme_summary(root, files_by_name),
        languages=languages,
        frameworks=frameworks,
        package_managers=_detect_package_managers(files_by_name),
        build_tools=_detect_build_tools(files_by_name),
        test_frameworks=_detect_test_frameworks(root, files_by_name, package_json),
        important_files=_collect_important_files(root, files_by_name),
        onboarding_docs=onboarding_docs,
        setup_guides=setup_guides,
        documented_setup_commands=documented_setup_commands,
        ci_cd_files=ci_cd_files,
        ci_commands=_collect_ci_commands(root, ci_cd_files),
        top_level_directories=top_level_directories,
        entry_points=_collect_entry_points(root, files_by_name),
        build_instructions=build_instructions,
        test_instructions=test_instructions,
    )


def _build_instructions(
    root: Path, files_by_name: dict[str, list[Path]], package_json: dict
) -> list[str]:
    instructions: list[str] = []
    if "requirements.txt" in files_by_name:
        instructions.append("pip install -r requirements.txt")
    if "pyproject.toml" in files_by_name:
        pyproject_text = _read_text(files_by_name["pyproject.toml"][0]).lower()
        if "[tool.poetry]" in pyproject_text:
            instructions.append("poetry install")
        else:
            instructions.append("python -m pip install -e .")
    if "package.json" in files_by_name:
        instructions.append("npm install  (or yarn/pnpm if a lockfile is present)")
        scripts = package_json.get("scripts", {})
        if isinstance(scripts, dict) and "build" in scripts:
            instructions.append("npm run build")
    if "composer.json" in files_by_name:
        instructions.append("composer install")
    if "pom.xml" in files_by_name:
        instructions.append("mvn package")
    if "build.gradle" in files_by_name or "build.gradle.kts" in files_by_name:
        instructions.append("./gradlew build")
    if any(n.endswith(".sln") or n.endswith(".csproj") for n in files_by_name):
        instructions.append("dotnet build")
    if "go.mod" in files_by_name:
        instructions.append("go build ./...")
    if "Cargo.toml" in files_by_name:
        instructions.append("cargo build")
    if "Gemfile" in files_by_name:
        instructions.append("bundle install")
    if (root / "Makefile").is_file():
        instructions.append("make  (see Makefile targets)")
    if (root / "Dockerfile").is_file():
        instructions.append("docker build -t <name> .")
    return instructions


def _test_instructions(package_json: dict, files_by_name: dict[str, list[Path]]) -> list[str]:
    instructions: list[str] = []
    scripts = package_json.get("scripts", {})
    if isinstance(scripts, dict) and "test" in scripts:
        instructions.append(f"npm test  (`{scripts['test']}`)")
    if any(n in files_by_name for n in ("pytest.ini", "pyproject.toml", "setup.cfg")):
        instructions.append("pytest")
    elif any(n.startswith("test_") for n in files_by_name):
        instructions.append("pytest")
    if "phpunit.xml" in files_by_name or "phpunit.xml.dist" in files_by_name:
        instructions.append("vendor/bin/phpunit")
    if "pom.xml" in files_by_name:
        instructions.append("mvn test")
    if "build.gradle" in files_by_name or "build.gradle.kts" in files_by_name:
        instructions.append("./gradlew test")
    if any(n.endswith(".csproj") for n in files_by_name):
        instructions.append("dotnet test")
    if "go.mod" in files_by_name:
        instructions.append("go test ./...")
    if "Cargo.toml" in files_by_name:
        instructions.append("cargo test")
    return instructions
