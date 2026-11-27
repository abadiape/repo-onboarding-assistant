"""Business narrative."""
from __future__ import annotations

from dataclasses import dataclass, field

from models.business_insights import DomainImpact


@dataclass
class NarrativeWorkflow:
    name: str
    purpose: str
    domains: list[str] = field(default_factory=list)
    modules: list[str] = field(default_factory=list)
    onboarding_significance: str = "Medium"


@dataclass
class DomainInteraction:
    domains: list[str]
    evidence: list[str] = field(default_factory=list)


@dataclass
class NarrativeCustomization:
    name: str
    path: str
    domains: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    owner: str | None = None
    explanation: str = ""


@dataclass
class BusinessNarrative:
    system_name: str
    system_purpose: str
    core_flow_domains: list[str] = field(default_factory=list)
    core_flow_capabilities: list[str] = field(default_factory=list)
    primary_domains: list[DomainImpact] = field(default_factory=list)
    domain_interactions: list[DomainInteraction] = field(default_factory=list)
    differentiators: list[str] = field(default_factory=list)
    customized_domains: list[DomainImpact] = field(default_factory=list)
    narrative_insights: list[str] = field(default_factory=list)
    business_flow: str = ""
    notable_patterns: list[str] = field(default_factory=list)
    customizations: list[NarrativeCustomization] = field(default_factory=list)
    workflows: list[NarrativeWorkflow] = field(default_factory=list)
    critical_integrations: list[dict[str, str | list[str]]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    first_week: list[tuple[str, str]] = field(default_factory=list)
