"""Heuristic repository classification and its supporting evidence."""
from dataclasses import asdict, dataclass, field
from enum import Enum


class RepositoryArchetype(str, Enum):
    BUSINESS_APPLICATION = "business_application"
    DEVELOPER_TOOL = "developer_tool"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    CLI_TOOL = "cli_tool"
    INFRASTRUCTURE = "infrastructure"
    SDK = "sdk"
    AI_AGENT_PLATFORM = "ai_agent_platform"
    DATA_PIPELINE = "data_pipeline"
    UNKNOWN = "unknown"


@dataclass
class ArchetypeCandidate:
    archetype: RepositoryArchetype
    confidence: float


@dataclass
class ArchetypeResult:
    archetype: RepositoryArchetype = RepositoryArchetype.UNKNOWN
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    alternatives: list[ArchetypeCandidate] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
