"""Records describing repository relevance and dependency groups."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RepositoryArea:
    name: str
    path: str
    kind: str


@dataclass
class DependencyGroup:
    name: str
    packages: list[str] = field(default_factory=list)
    origin: str = "dependency"


@dataclass
class RepositoryRelevance:
    paths: dict[str, list[str]] = field(default_factory=dict)
    origins: dict[str, list[str]] = field(default_factory=dict)
    areas: list[RepositoryArea] = field(default_factory=list)
    dependency_groups: list[DependencyGroup] = field(default_factory=list)
