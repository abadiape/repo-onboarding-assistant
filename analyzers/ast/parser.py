"""Parser contract and intermediate import declarations."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from models.symbols import Evidence, Relationship, Symbol


@dataclass
class Import:
    source_id: str
    module: str
    name: str | None
    level: int
    evidence: Evidence
    alias: str | None = None


@dataclass
class ParseResult:
    symbols: list[Symbol] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    imports: list[Import] = field(default_factory=list)
    syntax_tree: object | None = None
    source_lines: list[str] = field(default_factory=list)


class Parser(Protocol):
    language: str
    extensions: tuple[str, ...]

    def parse(self, root: Path, path: str) -> ParseResult: ...
