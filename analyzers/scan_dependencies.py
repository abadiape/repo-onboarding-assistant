"""Scan dependencies."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from analyzers.scan_io import _read_json, _read_text
from models.models import Dependency


def _dependency(
    name: str, version: object, source: str, scope: str
) -> Dependency | None:
    normalized_name = name.strip()
    if not normalized_name:
        return None
    normalized_version = str(version).strip() if version is not None else ""
    return Dependency(
        name=normalized_name,
        version=normalized_version or None,
        source=source,
        scope=scope,
    )


def _parse_requirement(line: str, source: str, scope: str) -> Dependency | None:
    line = line.split("#", 1)[0].strip()
    if not line or line.startswith(("-", "http:", "https:")):
        return None
    match = re.match(
        r"([A-Za-z0-9][A-Za-z0-9_.-]*)(?:\[[^]]+\])?\s*(.*)", line
    )
    if not match:
        return None
    version = match.group(2).strip() or None
    return _dependency(match.group(1), version, source, scope)


def _toml_section(text: str, section: str) -> str:
    match = re.search(
        rf"(?ms)^\[{re.escape(section)}\]\s*(.*?)(?=^\[|\Z)", text
    )
    return match.group(1) if match else ""


def _collect_dependencies(
    root: Path, files_by_name: dict[str, list[Path]]
) -> list[Dependency]:
    """Extract declared dependencies from supported manifests without executing code."""
    found: list[Dependency] = []

    def source_for(path: Path) -> str:
        return path.relative_to(root).as_posix()

    def add(dependency: Dependency | None) -> None:
        if dependency is not None:
            found.append(dependency)

    for path in files_by_name.get("package.json", []):
        manifest = _read_json(path)
        for section, scope in (
            ("dependencies", "runtime"),
            ("devDependencies", "development"),
            ("peerDependencies", "peer"),
            ("optionalDependencies", "optional"),
        ):
            declarations = manifest.get(section, {})
            if isinstance(declarations, dict):
                for name, version in declarations.items():
                    add(_dependency(name, version, source_for(path), scope))

    for path in files_by_name.get("pyproject.toml", []):
        text = _read_text(path)
        build_system = _toml_section(text, "build-system")
        for block in re.findall(
            r"(?ms)^\s*requires\s*=\s*\[(.*?)\]", build_system
        ):
            for declaration in re.findall(r"""['"]([^'"]+)['"]""", block):
                add(_parse_requirement(declaration, source_for(path), "build"))

        project = _toml_section(text, "project")
        for block in re.findall(r"(?ms)^\s*dependencies\s*=\s*\[(.*?)\]", project):
            for declaration in re.findall(r"""['"]([^'"]+)['"]""", block):
                add(_parse_requirement(declaration, source_for(path), "runtime"))

        optional = _toml_section(text, "project.optional-dependencies")
        for match in re.finditer(
            r"""(?ms)^\s*([A-Za-z0-9_-]+)\s*=\s*\[(.*?)\]""", optional
        ):
            scope = f"optional:{match.group(1)}"
            for declaration in re.findall(r"""['"]([^'"]+)['"]""", match.group(2)):
                add(_parse_requirement(declaration, source_for(path), scope))

        for section, scope in (
            ("tool.poetry.dependencies", "runtime"),
            ("tool.poetry.dev-dependencies", "development"),
        ):
            section_text = _toml_section(text, section)
            for line in section_text.splitlines():
                match = re.match(r'\s*([A-Za-z0-9_.-]+)\s*=\s*(.+)', line)
                if match and match.group(1).lower() != "python":
                    version_match = re.search(r"""['"]([^'"]+)['"]""", match.group(2))
                    add(_dependency(
                        match.group(1),
                        version_match.group(1) if version_match else match.group(2),
                        source_for(path),
                        scope,
                    ))

    for filename in ("requirements.txt", "requirements-dev.txt"):
        for path in files_by_name.get(filename, []):
            scope = "development" if filename == "requirements-dev.txt" else "runtime"
            for line in _read_text(path).splitlines():
                add(_parse_requirement(line, source_for(path), scope))

    for path in files_by_name.get("composer.json", []):
        manifest = _read_json(path)
        for section, scope in (("require", "runtime"), ("require-dev", "development")):
            declarations = manifest.get(section, {})
            if isinstance(declarations, dict):
                for name, version in declarations.items():
                    add(_dependency(name, version, source_for(path), scope))

    for path in files_by_name.get("pom.xml", []):
        try:
            document = ET.fromstring(_read_text(path))
        except ET.ParseError:
            continue
        for item in document.iter():
            if item.tag.rsplit("}", 1)[-1] != "dependency":
                continue
            values = {
                child.tag.rsplit("}", 1)[-1]: child.text
                for child in item
                if child.text
            }
            if values.get("artifactId"):
                name = ":".join(
                    part for part in (values.get("groupId"), values["artifactId"]) if part
                )
                scope = "development" if values.get("scope") == "test" else "runtime"
                add(_dependency(name, values.get("version"), source_for(path), scope))

    for filename in ("build.gradle", "build.gradle.kts"):
        for path in files_by_name.get(filename, []):
            for match in re.finditer(
                r"""(?m)^\s*(implementation|api|compileOnly|runtimeOnly|"""
                r"""testImplementation|testRuntimeOnly)\s*\(?\s*['"]"""
                r"""([^:'"]+):([^:'"]+):([^'"]+)['"]""",
                _read_text(path),
            ):
                scope = "development" if match.group(1).startswith("test") else "runtime"
                add(_dependency(
                    f"{match.group(2)}:{match.group(3)}",
                    match.group(4),
                    source_for(path),
                    scope,
                ))

    for path in files_by_name.get("Cargo.toml", []):
        current_scope = "runtime"
        for line in _read_text(path).splitlines():
            section = re.match(r"\s*\[([^]]+)\]", line)
            if section:
                current_scope = (
                    "development" if "dev-dependencies" in section.group(1)
                    else "build" if "build-dependencies" in section.group(1)
                    else "runtime" if section.group(1) == "dependencies"
                    else ""
                )
                continue
            if not current_scope:
                continue
            declaration = re.match(r'\s*([A-Za-z0-9_-]+)\s*=\s*(.+)', line)
            if declaration:
                version = re.search(r"""version\s*=\s*['"]([^'"]+)['"]""", declaration.group(2))
                if not version:
                    version = re.match(r"""['"]([^'"]+)['"]""", declaration.group(2))
                add(_dependency(
                    declaration.group(1),
                    version.group(1) if version else None,
                    source_for(path),
                    current_scope,
                ))

    for path in files_by_name.get("go.mod", []):
        in_require_block = False
        for line in _read_text(path).splitlines():
            stripped = line.strip()
            if stripped.startswith("require ("):
                in_require_block = True
                continue
            if in_require_block and stripped == ")":
                in_require_block = False
                continue
            if stripped.startswith("require "):
                stripped = stripped.removeprefix("require ").strip()
            elif not in_require_block:
                continue
            match = re.match(r"(\S+)\s+(\S+)", stripped)
            if match:
                add(_dependency(
                    match.group(1), match.group(2), source_for(path), "runtime"
                ))

    unique: dict[tuple[str, str, str, str], Dependency] = {}
    for item in found:
        unique[(item.name, item.version or "", item.source, item.scope)] = item
    return list(unique.values())


def _collect_locked_dependencies(root: Path, files_by_name: dict[str, list[Path]]) -> list[Dependency]:
    locked: dict[tuple[str, str], Dependency] = {}
    for path in files_by_name.get("composer.lock", []):
        source = path.relative_to(root).as_posix()
        lock = _read_json(path)
        for section in ("packages", "packages-dev"):
            packages = lock.get(section, [])
            if not isinstance(packages, list):
                continue
            for package in packages:
                if isinstance(package, dict) and isinstance(package.get("name"), str):
                    name = package["name"]
                    dependency = _dependency(name, package.get("version"), source, "locked")
                    if dependency:
                        locked[(source, name)] = dependency
    for path in files_by_name.get("package-lock.json", []):
        source = path.relative_to(root).as_posix()
        lock = _read_json(path)
        packages = lock.get("packages", {})
        if isinstance(packages, dict) and packages:
            for location, package in packages.items():
                if "node_modules/" not in location or not isinstance(package, dict):
                    continue
                name = location.rsplit("node_modules/", 1)[-1]
                if name:
                    dependency = _dependency(name, package.get("version"), source, "locked")
                    if dependency:
                        locked[(source, name)] = dependency
        elif isinstance(lock.get("dependencies"), dict):
            for name, package in lock["dependencies"].items():
                if isinstance(package, dict):
                    dependency = _dependency(name, package.get("version"), source, "locked")
                    if dependency:
                        locked[(source, name)] = dependency
    return list(locked.values())
