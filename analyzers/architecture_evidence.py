"""Architecture evidence."""
from __future__ import annotations

import re
from pathlib import Path

from models.models import RepositoryModel

_IGNORED_AREAS = {
    "test", "tests", "docs", "examples", "example", "build", "dist",
    "vendor", "node_modules", "outputs", "templates", ".github",
}


_DOC_EXTENSIONS = {".md", ".rst", ".txt"}


_CONFIG_FILES = {
    "package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
    "composer.json", "pom.xml", "build.gradle", "build.gradle.kts", "cargo.toml",
    "go.mod", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml",
}


_CONFIG_EXTENSIONS = {
    ".conf", ".ini", ".json", ".properties", ".toml", ".xml", ".yaml", ".yml",
}


_IGNORED_CONTEXT_AREAS = {
    "test", "tests", "example", "examples", "build", "dist", "vendor",
    "node_modules", "outputs", "templates",
}


_IMPORT_PATTERNS = (
    (re.compile(r"^\s*from\s+([.\w/]+)\s+import\b"), "imports"),
    (re.compile(r"^\s*import\s+([.\w/]+)(?:\s+as\b|$)"), "imports"),
    (re.compile(r"\bexport\b[^\n;]*?\bfrom\s*[\"']([^\"']+)[\"']"), "re-exports"),
    (re.compile(r"\bimport\b[^\n;]*?\bfrom\s*[\"']([^\"']+)[\"']"), "imports"),
    (re.compile(r"\b(?:import|require|include)\s*(?:\(\s*)?[\"']([^\"']+)[\"']"), "imports"),
    (re.compile(r"^\s*(?:using|use)\s+([\w\\.*]+)\s*;?"), "imports"),
)


def _parts(path: str) -> list[str]:
    return [part.lower().replace("-", "_") for part in path.replace("\\", "/").split("/") if part]


def _is_config_file(path: Path, kind: str) -> bool:
    return (
        kind == "manifest"
        or path.name.lower() in _CONFIG_FILES
        or (kind == "file" and path.suffix.lower() in _CONFIG_EXTENSIONS)
    )


def _source_code_lines(content: str) -> list[tuple[int, str]]:
    code_lines = []
    quote_delimiter: str | None = None
    in_block_comment = False
    for line_number, original_line in enumerate(content.splitlines(), 1):
        line = original_line
        if in_block_comment:
            if "*/" not in line:
                continue
            line = line.split("*/", 1)[1]
            in_block_comment = False
        if quote_delimiter:
            if quote_delimiter not in line:
                continue
            line = line.split(quote_delimiter, 1)[1]
            quote_delimiter = None
        if "/*" in line:
            before, after = line.split("/*", 1)
            if "*/" in after:
                line = before + after.split("*/", 1)[1]
            else:
                line = before
                in_block_comment = True
        if line.lstrip().startswith(("#", "//", "*")):
            continue
        for delimiter in ('"""', "'''"):
            if delimiter in line:
                before, after = line.split(delimiter, 1)
                if delimiter in after:
                    line = before + after.split(delimiter, 1)[1]
                else:
                    line = before
                    quote_delimiter = delimiter
        line = re.split(r"\s+(?:#|//)", line, maxsplit=1)[0].strip()
        if line:
            code_lines.append((line_number, line))
    return code_lines


def _read_model_sources(model: RepositoryModel) -> str:
    if not model.root_path:
        return ""
    root = Path(model.root_path).resolve()
    selected = []
    for file in model.files:
        relative = Path(file.path)
        name = relative.name.lower()
        parts = _parts(file.path)
        if set(parts) & _IGNORED_CONTEXT_AREAS:
            continue
        is_document = relative.suffix.lower() in _DOC_EXTENSIONS and (
            name.startswith("readme") or "architecture" in name or "design" in name or "docs" in parts
        )
        if (
            (is_document or _is_config_file(relative, file.kind) or file.kind in {"ci", "docker"})
            and not relative.is_absolute()
            and ".." not in relative.parts
        ):
            selected.append(relative.as_posix())
    texts = []
    for relative in sorted(set(selected))[:80]:
        try:
            path = (root / relative).resolve()
            path.relative_to(root)
            with path.open("rb") as source:
                texts.append(source.read(32_000).decode("utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if sum(map(len, texts)) >= 200_000:
            break
    return "\n".join(texts)[:200_000]


def _read_relationship_sources(model: RepositoryModel) -> dict[str, str]:
    if not model.root_path:
        return {}
    root = Path(model.root_path).resolve()
    selected: list[str] = []
    for file in model.files:
        relative = Path(file.path)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        parts = _parts(file.path)
        if set(parts) & _IGNORED_CONTEXT_AREAS:
            continue
        if file.kind == "source" and not set(parts) & _IGNORED_AREAS:
            selected.append(relative.as_posix())
            continue
        name = relative.name.lower()
        is_document = relative.suffix.lower() in _DOC_EXTENSIONS and (
            name.startswith("readme") or "architecture" in name or "design" in name or "docs" in parts
        )
        if is_document or _is_config_file(relative, file.kind) or file.kind in {"ci", "docker"}:
            selected.append(relative.as_posix())

    selected_paths = set(selected)
    kinds = {file.path: file.kind for file in model.files}
    priority = sorted(
        (path for path in selected_paths if
         (Path(path).name.lower().startswith("readme") and len(Path(path).parts) == 1)
         or path in model.entry_points
         or (len(Path(path).parts) == 1 and _is_config_file(Path(path), kinds[path]))),
        key=lambda path: (len(Path(path).parts), path),
    )
    public = sorted(
        (path for path in selected_paths - set(priority)
         if Path(path).name.lower() in {"__init__.py", "index.ts", "index.js", "lib.rs"}),
        key=lambda path: (len(Path(path).parts), path),
    )
    documentation = sorted(
        path for path in selected_paths - set(priority)
        if Path(path).suffix.lower() in _DOC_EXTENSIONS
    )
    priority = list(dict.fromkeys([*priority, *public[:12], *documentation[:10]]))
    remaining = set(selected) - set(priority)
    groups: dict[str, list[str]] = {}
    for path in sorted(remaining):
        groups.setdefault(str(Path(path).parent), []).append(path)
    ordered = priority[:]
    while groups:
        for directory in sorted(groups):
            ordered.append(groups[directory].pop(0))
            if not groups[directory]:
                del groups[directory]

    contents: dict[str, str] = {}
    total_bytes = 0
    candidates = ordered[:120]
    for index, relative in enumerate(candidates):
        if total_bytes >= 400_000:
            break
        remaining = 400_000 - total_bytes
        limit = min(24_000, remaining, max(1024, remaining // (len(candidates) - index)))
        try:
            path = (root / relative).resolve()
            path.relative_to(root)
            with path.open("rb") as source:
                data = source.read(limit)
        except (OSError, ValueError):
            continue
        contents[relative] = data.decode("utf-8", errors="replace")
        total_bytes += len(data)
    return contents


def _public_imports(path: str, content: str) -> list[tuple[int, str]]:
    name = Path(path).name
    if name not in {"__init__.py", "index.js", "index.ts"}:
        return []
    imports = []
    for number, line in _source_code_lines(content):
        if name != "__init__.py" and not re.search(r"\bexport\b", line):
            continue
        for pattern, _ in _IMPORT_PATTERNS:
            match = pattern.search(line)
            if match:
                imports.append((number, match.group(1)))
                break
    return imports
