"""Intermediate representation for inferred repository architecture."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any
from analyzers.repository_relevance import RepositoryRelevance


@dataclass
class ArchitectureComponent:
    id: str
    name: str
    type: str
    description: str
    responsibilities: list[str] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    relevance: float = 0.0
    locations: list[str] = field(default_factory=list)
    significance: float = 0.0


@dataclass
class ArchitectureSubsystem:
    id: str
    name: str
    description: str
    components: list[str] = field(default_factory=list)


@dataclass
class ArchitectureRelationship:
    source: str
    target: str
    type: str
    description: str
    confidence: float = 0.5
    evidence: list[str] = field(default_factory=list)


@dataclass
class ArchitectureModel:
    system_name: str
    system_type: str
    description: str
    components: list[ArchitectureComponent] = field(default_factory=list)
    subsystems: list[ArchitectureSubsystem] = field(default_factory=list)
    layers: list[ArchitectureSubsystem] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    relationships: list[ArchitectureRelationship] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    external_dependencies: list[str] = field(default_factory=list)
    data_stores: list[str] = field(default_factory=list)
    execution_flows: list[dict[str, Any]] = field(default_factory=list)
    detected_patterns: list[str] = field(default_factory=list)
    recommended_learning_path: list[str] = field(default_factory=list)
    framework_architecture: list[str] = field(default_factory=list)
    deployment_architecture: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    repository_relevance: RepositoryRelevance = field(default_factory=RepositoryRelevance)
    public_api_entry_points: list[str] = field(default_factory=list)
    optional_integrations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
