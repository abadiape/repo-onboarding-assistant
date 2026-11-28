"""Core data models for the repo-onboarding-assistant skill.

Independent from LLM Harness Lite. The harness Artifact API is only
used at the skill boundary (see onboarding_skill.py).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from models.symbols import Evidence, Relationship, Symbol


@dataclass
class Dependency:
    """A dependency declaration found in a repository manifest."""

    name: str
    version: str | None
    source: str
    scope: str = "runtime"
    category: str = "unclassified"


@dataclass
class RepositoryFile:
    """A repository file identified by its relative path and broad role."""

    path: str
    kind: str
    language: str | None = None


@dataclass
class RepositoryModel:
    """Normalized, convention-based representation of a scanned repository."""

    repository_name: str
    root_path: str = ""
    readme_summary: str = ""
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)
    test_frameworks: list[str] = field(default_factory=list)
    important_files: list[str] = field(default_factory=list)
    onboarding_docs: list[str] = field(default_factory=list)
    setup_guides: list[str] = field(default_factory=list)
    documented_setup_commands: list[dict[str, str]] = field(default_factory=list)
    ci_cd_files: list[str] = field(default_factory=list)
    ci_commands: list[dict[str, str]] = field(default_factory=list)
    top_level_directories: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    build_instructions: list[str] = field(default_factory=list)
    test_instructions: list[str] = field(default_factory=list)

    metadata: dict[str, str] = field(default_factory=dict)
    dependencies: list[Dependency] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    files: list[RepositoryFile] = field(default_factory=list)
    detected_patterns: list[str] = field(default_factory=list)
    locked_dependencies: list[Dependency] = field(default_factory=list)
    api_inventory: dict[str, Any] = field(default_factory=dict)
    symbols: list[Symbol] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RepositoryModel:
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        filtered["dependencies"] = [
            item if isinstance(item, Dependency) else Dependency(**item)
            for item in filtered.get("dependencies", [])
        ]
        filtered["locked_dependencies"] = [
            item if isinstance(item, Dependency) else Dependency(**item)
            for item in filtered.get("locked_dependencies", [])
        ]
        filtered["files"] = [
            item if isinstance(item, RepositoryFile) else RepositoryFile(**item)
            for item in filtered.get("files", [])
        ]
        for key, record_type in (("symbols", Symbol), ("relationships", Relationship)):
            records = []
            for item in filtered.get(key, []):
                if isinstance(item, record_type):
                    records.append(item)
                else:
                    values = dict(item)
                    values["evidence"] = [
                        evidence if isinstance(evidence, Evidence) else Evidence(**evidence)
                        for evidence in values.get("evidence", [])
                    ]
                    records.append(record_type(**values))
            filtered[key] = records
        return cls(**filtered)


# Backwards-compatible name for callers of the original inventory model.
RepositoryInventory = RepositoryModel
