"""Domain discovery."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class BusinessDomain:
    name: str
    priority: str
    responsibilities: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class BusinessCapability:
    name: str
    priority: str
    domains: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)


@dataclass
class BusinessIntegration:
    name: str
    priority: str
    domains: list[str] = field(default_factory=list)
    ownership_boundary: str = "External system"
    evidence: list[str] = field(default_factory=list)


@dataclass
class CustomModule:
    name: str
    path: str
    kind: str
    owner: str | None = None
    priority: str = "medium"


@dataclass
class DomainDiscovery:
    domains: list[BusinessDomain] = field(default_factory=list)
    capabilities: list[BusinessCapability] = field(default_factory=list)
    integrations: list[BusinessIntegration] = field(default_factory=list)
    custom_modules: list[CustomModule] = field(default_factory=list)
    onboarding_priorities: list[dict[str, str]] = field(default_factory=list)
    deferred_areas: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
