"""Business insights."""
# Explicit aliases preserve the original import paths.
# ruff: noqa: PLC0414
from __future__ import annotations

from dataclasses import asdict
from pathlib import PurePosixPath

from analyzers.domain_discovery import _tokens
from analyzers.technical_onboarding import technical_plan, technical_topics
from artifacts.business_plan import (
    first_week_onboarding_plan as first_week_onboarding_plan,
)
from artifacts.business_plan import (
    render_first_week_onboarding_markdown as render_first_week_onboarding_markdown,
)
from artifacts.business_reports import (
    render_business_insights_markdown as render_business_insights_markdown,
)
from artifacts.business_reports import (
    render_critical_modules_markdown as render_critical_modules_markdown,
)
from artifacts.business_reports import (
    render_executive_summary_markdown as render_executive_summary_markdown,
)
from models.architecture_model import ArchitectureModel
from models.business_insights import BusinessInsights as BusinessInsights
from models.business_insights import DomainImpact as DomainImpact
from models.business_insights import ModulePriority as ModulePriority
from models.domain_discovery import BusinessCapability, DomainDiscovery
from models.models import RepositoryModel
from models.repository_archetype import ArchetypeResult, RepositoryArchetype

_DOMAIN_IMPACTS = {
    "Payments": "Critical",
    "Orders": "Critical",
    "Inventory": "High",
    "ERP Integrations": "High",
    "Shipping": "High",
    "Customer Experience": "High",
}


_DOMAIN_RATIONALES = {
    "Payments": "Payment and transaction customizations can affect revenue collection.",
    "Orders": "Order capture and lifecycle workflows are central commerce operations.",
    "Inventory": "Stock availability can affect purchasability and fulfillment.",
    "ERP Integrations": "External synchronization can affect order and inventory operations.",
    "Shipping": "Fulfillment and delivery workflows affect order completion.",
    "Customer Experience": "Customer accounts and registration affect access and retention.",
    "Catalog": "Product information influences what customers can find and purchase.",
    "Marketing": "Promotions and campaigns can influence customer acquisition and sales.",
    "Search": "Search helps customers discover relevant products and content.",
    "Loyalty": "Rewards can encourage customer retention and repeat purchases.",
}


_IMPORTANCE_RANK = {"Very High": 4, "High": 3, "Medium": 2, "Low": 1}


_IMPACT_RANK = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


_MODULE_TIER_RANK = {"Business Critical": 3, "Important": 2, "Supporting": 1}


_DOMAIN_ORDER = {
    name: index for index, name in enumerate(
        ("Payments", "Orders", "ERP Integrations", "Inventory", "Shipping", "Customer Experience")
    )
}


_SUPPORTING_MODULE_TOKENS = {
    "attribute", "attributes", "clean", "cleanup", "mail", "price", "schedule", "trigger",
}


_SOURCE_SUFFIXES = {".cs", ".go", ".java", ".js", ".php", ".py", ".rb", ".rs", ".ts"}


def _domain_confidence(
    has_documentation: bool,
    source_evidence_count: int,
    module_count: int,
    integration_count: int,
) -> float:
    score = 0.25 + (0.05 if has_documentation else 0)
    score += (0.20 + min(module_count - 1, 3) * 0.05) if module_count else 0
    score += min(source_evidence_count, 3) * 0.10
    score += 0.25 if integration_count else 0
    return round(min(score, 0.95), 2)


def analyze_business_insights(
    architecture: ArchitectureModel, domains: DomainDiscovery,
    archetype: ArchetypeResult | None = None, model: RepositoryModel | None = None,
) -> BusinessInsights:
    """Score evidence-backed domain value and rank custom modules for onboarding."""
    if archetype is not None and archetype.archetype != RepositoryArchetype.BUSINESS_APPLICATION:
        if model is None:
            raise ValueError("A repository model is required for technical onboarding insights")
        topics = technical_topics(model, archetype.archetype)
        plan = technical_plan(archetype.archetype, topics, architecture.public_api_entry_points)
        return BusinessInsights(
            frameworks=architecture.frameworks,
            learning_plan=plan,
            technical_topics=[asdict(topic) for topic in topics],
            recommendations=[step["detail"] for step in plan],
        )
    architecture_integrations = {
        item.casefold() for item in architecture.external_dependencies
    }
    domain_impacts = []
    for domain in domains.domains:
        related_integrations = [
            item.name for item in domains.integrations
            if domain.name in item.domains
            and item.name.casefold() in architecture_integrations
        ]
        source_evidence_count = sum(
            PurePosixPath(evidence).suffix.casefold() in _SOURCE_SUFFIXES
            for evidence in domain.evidence
        )
        has_direct_evidence = bool(
            domain.modules or related_integrations or source_evidence_count
        )
        impact = _DOMAIN_IMPACTS.get(domain.name, "Medium") if has_direct_evidence else "Low"
        importance = (
            "Very High" if impact in {"Critical", "High"} and domain.modules
            else "High" if impact in {"Critical", "High"} or domain.modules or related_integrations
            else "Medium" if impact == "Medium" else "Low"
        )
        rationale = _DOMAIN_RATIONALES.get(
            domain.name,
            "This business area may shape customer-facing or operational behavior.",
        )
        if not has_direct_evidence:
            rationale = (
                "This term appears in documentation, but no matching custom module, "
                "source path, or configured integration was found."
            )
        domain_impacts.append(DomainImpact(
            name=domain.name,
            confidence=_domain_confidence(
                bool(domain.evidence),
                source_evidence_count,
                len(domain.modules),
                len(related_integrations),
            ),
            business_impact=impact,
            onboarding_importance=importance,
            rationale=rationale,
            modules=sorted(domain.modules, key=str.casefold),
            integrations=sorted(related_integrations, key=str.casefold),
            description=" ".join(domain.responsibilities) or "No responsibility was inferred.",
        ))
    domain_impacts.sort(key=lambda item: (
        -_IMPORTANCE_RANK[item.onboarding_importance],
        -_IMPACT_RANK[item.business_impact],
        _DOMAIN_ORDER.get(item.name, len(_DOMAIN_ORDER)),
        item.name.casefold(),
    ))
    impact_by_name = {item.name: item for item in domain_impacts}

    module_priorities = []
    for module in domains.custom_modules:
        owners = [
            impact_by_name[domain_name]
            for domain_name in impact_by_name
            if module.name in impact_by_name[domain_name].modules
        ]
        owners.sort(key=lambda item: (
            -_IMPORTANCE_RANK[item.onboarding_importance],
            -_IMPACT_RANK[item.business_impact],
            _DOMAIN_ORDER.get(item.name, len(_DOMAIN_ORDER)),
            item.name.casefold(),
        ))
        domain_names = [item.name for item in owners]
        impact = owners[0].business_impact if owners else "Low"
        confidence = max((item.confidence for item in owners), default=0.35)
        if impact in {"Critical", "High"} and owners[0].onboarding_importance == "Very High":
            tier = "Business Critical"
        elif owners:
            tier = "Important"
        else:
            tier = "Supporting"
        rationale = (
            "; ".join(
                f"Matched to {item.name}: {item.rationale}"
                for item in owners[:2]
            )
            if owners else
            "No strong business-domain match was inferred; defer until a workflow leads here."
        )
        module_priorities.append(ModulePriority(
            name=module.name,
            path=module.path,
            tier=tier,
            confidence=confidence,
            business_impact=impact,
            domains=domain_names,
            rationale=rationale,
            recommendation=(
                f"Study this module before changing {owners[0].name} workflows; "
                "confirm its role with a maintainer."
                if owners else
                "Defer this module until a relevant workflow or maintainer points to it."
            ),
        ))
    module_priorities.sort(key=lambda item: (
        -_MODULE_TIER_RANK[item.tier],
        -_IMPACT_RANK[item.business_impact],
        bool(_tokens(item.name) & _SUPPORTING_MODULE_TOKENS),
        item.name.casefold(),
        item.path.casefold(),
    ))
    for domain in domain_impacts:
        domain.learning_order = list(dict.fromkeys(
            item.name for item in module_priorities if domain.name in item.domains
        ))
        domain.starting_module = next(iter(domain.learning_order), None)
        if domain.starting_module:
            domain.learning_recommendation = (
                f"Start with {domain.starting_module}, then trace a workflow in {domain.name} "
                "and confirm the module's role with a maintainer."
            )
        else:
            domain.learning_recommendation = (
                "No starting module was identified; ask a maintainer where to trace this workflow."
            )

    # Give the first representative of each important domain a place before
    # listing additional modules from the same domain.
    representatives = []
    seen_paths = set()
    for domain in domain_impacts:
        if domain.onboarding_importance not in {"Very High", "High"}:
            continue
        representative = next(
            (item for item in module_priorities
             if domain.name in item.domains and item.path not in seen_paths),
            None,
        )
        if representative:
            representatives.append(representative)
            seen_paths.add(representative.path)
    module_priorities = representatives + [
        item for item in module_priorities if item.path not in seen_paths
    ]
    capability_rank = {"high": 0, "medium": 1, "low": 2}
    capabilities = sorted(
        [
            BusinessCapability(
                name=capability.name,
                domains=capability.domains,
                modules=capability.modules,
                evidence=capability.evidence,
                priority=(
                    "high" if capability.modules or any(
                        impact_by_name.get(name)
                        and impact_by_name[name].onboarding_importance in {"Very High", "High"}
                        for name in capability.domains
                    )
                    else "medium" if any(
                        impact_by_name.get(name)
                        and impact_by_name[name].business_impact == "Medium"
                        for name in capability.domains
                    )
                    else "low"
                ),
            )
            for capability in domains.capabilities
        ],
        key=lambda item: (capability_rank.get(item.priority, 3), item.name.casefold()),
    )

    critical_integrations = []
    for integration in domains.integrations:
        if integration.name.casefold() not in architecture_integrations:
            continue
        related_domains = [
            domain for domain in integration.domains if domain in impact_by_name
        ]
        integration_priority = (
            "Business Critical"
            if any(impact_by_name[name].business_impact in {"Critical", "High"} for name in related_domains)
            else "Important" if related_domains else "Supporting"
        )
        if integration_priority == "Business Critical":
            critical_integrations.append({
                "name": integration.name,
                "priority": integration_priority,
                "domains": related_domains,
                "ownership_boundary": integration.ownership_boundary,
            })

    recommendations = []
    for domain in domain_impacts:
        if domain.onboarding_importance in {"Very High", "High"}:
            modules = ", ".join(domain.learning_order[:3])
            integrations = ", ".join(domain.integrations[:2])
            focus = "; ".join(
                part for part in (
                    f"review {modules}" if modules else "",
                    f"trace {integrations}" if integrations else "",
                ) if part
            )
            recommendations.append(
                f"Prioritize {domain.name}{': ' + focus if focus else ''}."
            )
    for capability in [item for item in capabilities if item.priority != "low"][:3]:
        recommendations.append(
            f"Trace {capability.name} across "
            f"{', '.join(capability.domains) or 'its inferred application boundaries'}."
        )
    if not recommendations:
        recommendations.append(
            "Start with the README and ask a maintainer which business workflows are most active."
        )
    recommendations.append(
        "Treat impact and confidence as heuristic signals; confirm critical paths and ownership with maintainers."
    )

    return BusinessInsights(
        domain_impacts=domain_impacts,
        capabilities=capabilities,
        ranked_modules=module_priorities,
        critical_integrations=critical_integrations,
        recommendations=recommendations,
        frameworks=architecture.frameworks,
    )
