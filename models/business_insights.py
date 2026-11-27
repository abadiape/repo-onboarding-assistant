"""Business insights."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from models.domain_discovery import BusinessCapability


@dataclass
class DomainImpact:
    name: str
    confidence: float
    business_impact: str
    onboarding_importance: str
    rationale: str
    modules: list[str] = field(default_factory=list)
    integrations: list[str] = field(default_factory=list)
    description: str = ""
    starting_module: str | None = None
    learning_order: list[str] = field(default_factory=list)
    learning_recommendation: str = ""


@dataclass
class ModulePriority:
    name: str
    path: str
    tier: str
    confidence: float
    business_impact: str
    domains: list[str] = field(default_factory=list)
    rationale: str = ""
    recommendation: str = ""


@dataclass
class BusinessInsights:
    domain_impacts: list[DomainImpact] = field(default_factory=list)
    capabilities: list[BusinessCapability] = field(default_factory=list)
    ranked_modules: list[ModulePriority] = field(default_factory=list)
    critical_integrations: list[dict[str, str | list[str]]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    learning_plan: list[dict[str, str]] = field(default_factory=list)
    technical_topics: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
