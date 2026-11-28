"""Language-independent repository symbol and relationship records."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Evidence:
    path: str
    line: int
    column: int
    extract: str
    detector: str


@dataclass
class Symbol:
    id: str
    qualified_name: str
    kind: str
    language: str
    path: str
    start_line: int
    end_line: int
    parent_symbol_id: str | None
    visibility: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Relationship:
    source_id: str
    target_id: str
    relationship_type: str
    confidence: float
    direct_observation: bool
    evidence: list[Evidence] = field(default_factory=list)
