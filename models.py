"""Core data models for the repo-onboarding-assistant skill.

Independent from LLM Harness Lite. The harness Artifact API is only
used at the skill boundary (see onboarding_skill.py).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class RepositoryInventory:
    """Convention-based inventory of a source code repository.

    This object is the foundation for all onboarding analysis.
    Produced by repository_scan.scan_repository(), consumed by
    onboarding_analyzer.
    """

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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RepositoryInventory":
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)
