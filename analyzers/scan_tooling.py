"""Scan tooling."""
from __future__ import annotations

from pathlib import Path

from analyzers.scan_files import EXTENSION_TO_LANGUAGE, _iter_project_files
from analyzers.scan_io import _read_json, _read_text


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
        if name.endswith((".csproj", ".sln"))
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
    if (
        ("phpunit.xml" in files_by_name or "phpunit.xml.dist" in files_by_name)
        and "PHPUnit" not in frameworks
    ):
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
    if any(n.endswith((".sln", ".csproj")) for n in files_by_name):
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
    if any(n in files_by_name for n in ("pytest.ini", "pyproject.toml", "setup.cfg")) or any(n.startswith("test_") for n in files_by_name):
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
