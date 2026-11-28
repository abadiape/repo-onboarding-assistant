"""Resolve observed imports against the repository's symbol inventory."""
from __future__ import annotations

from collections import defaultdict
import logging
from pathlib import Path

from analyzers.ast.parser import Import
from analyzers.ast.python import module_name
from analyzers.ast.registry import DEFAULT_REGISTRY, ParserRegistry
from models.models import RepositoryFile
from models.symbols import Relationship, Symbol

logger = logging.getLogger(__name__)


def collect_symbols(
    root: Path, files: list[RepositoryFile], registry: ParserRegistry = DEFAULT_REGISTRY,
) -> tuple[list[Symbol], list[Relationship]]:
    symbols: list[Symbol] = []
    relationships: list[Relationship] = []
    imports: list[Import] = []
    for file in sorted(files, key=lambda item: item.path):
        parser = registry.for_path(file.path)
        if parser is None or file.kind != "source":
            continue
        result = parser.parse(root, file.path)
        symbols.extend(result.symbols)
        relationships.extend(result.relationships)
        imports.extend(result.imports)

    modules = [symbol for symbol in symbols if symbol.language == "Python" and symbol.kind == "module"]
    packages: dict[str, Symbol] = {}
    for module in modules:
        parent = Path(module.path).parent
        if Path(module.path).name == "__init__.py" and parent != Path("."):
            package = Symbol(
                id=f"python:package:{parent.as_posix()}",
                qualified_name=module.qualified_name, kind="package", language="Python",
                path=module.path, start_line=module.start_line, end_line=module.end_line,
                parent_symbol_id=None, visibility="private" if parent.name.startswith("_") else "public",
                evidence=module.evidence[:],
            )
            packages[parent.as_posix()] = package
    for package in packages.values():
        parent_path = Path(package.path).parent.parent.as_posix()
        parent = packages.get(parent_path)
        if parent:
            package.parent_symbol_id = parent.id
            relationships.append(Relationship(parent.id, package.id, "CONTAINS", 1.0, True, package.evidence[:]))
    for module in modules:
        package = packages.get(Path(module.path).parent.as_posix())
        if package:
            module.parent_symbol_id = package.id
            relationships.append(Relationship(package.id, module.id, "CONTAINS", 1.0, True, module.evidence[:]))
    symbols.extend(packages.values())

    by_id = {symbol.id: symbol for symbol in symbols}
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    by_suffix: dict[str, list[Symbol]] = defaultdict(list)
    for symbol in symbols:
        parent = by_id.get(symbol.parent_symbol_id or "")
        if symbol.language == "Python" and (
            symbol.kind == "module" or (parent is not None and parent.kind == "module")
        ):
            by_name[symbol.qualified_name].append(symbol)
            parts = symbol.qualified_name.split(".")
            for index in range(1, len(parts)):
                by_suffix[".".join(parts[index:])].append(symbol)

    def find(name: str, *, relative: bool, module_only: bool) -> Symbol | None:
        def eligible(candidates: list[Symbol]) -> list[Symbol]:
            return [symbol for symbol in candidates if not module_only or symbol.kind == "module"]

        candidates = eligible(by_name.get(name, []))
        if not candidates and not relative:
            candidates = eligible(by_suffix.get(name, []))
        return candidates[0] if len(candidates) == 1 else None

    for item in imports:
        source = by_id[item.source_id]
        if source.language != "Python":
            logger.warning("Import resolution is not supported for %s", source.language)
            continue
        base = item.module
        valid_relative = True
        if item.level:
            current = module_name(source.path).split(".")
            if Path(source.path).name != "__init__.py":
                current.pop()
            if item.level > len(current):
                valid_relative = False
            else:
                current = current[:len(current) - item.level + 1]
                base = ".".join([*current, *([item.module] if item.module else [])])
        target_name = ".".join(part for part in (base, item.name if item.name != "*" else None) if part)
        target = (
            find(target_name, relative=bool(item.level), module_only=item.name in (None, "*"))
            if valid_relative and target_name else None
        )
        unresolved = "." * item.level + ".".join(
            part for part in (item.module, item.name) if part
        )
        relationships.append(Relationship(
            source_id=item.source_id,
            target_id=target.id if target else f"unresolved:python:{unresolved}",
            relationship_type="IMPORTS", confidence=0.9 if target else 1.0,
            direct_observation=True, evidence=[item.evidence],
        ))
    return symbols, relationships
