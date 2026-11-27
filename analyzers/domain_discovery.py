"""Domain discovery."""
# Explicit aliases preserve the original import paths.
# ruff: noqa: PLC0414
from __future__ import annotations

import re
from pathlib import Path

from analyzers.domain_rules import (
    _CAPABILITY_DOMAINS,
    _CAPABILITY_RULES,
    _DOMAIN_RULES,
    _HIGH_VALUE_DOMAINS,
)
from analyzers.repository_relevance import (
    RepositoryArea,
    analyze_relevance,
    classify_path,
    relevant_model,
)
from artifacts.domain_reports import (
    render_business_capabilities_markdown as render_business_capabilities_markdown,
)
from artifacts.domain_reports import (
    render_business_domains_markdown as render_business_domains_markdown,
)
from artifacts.domain_reports import (
    render_onboarding_priorities_markdown as render_onboarding_priorities_markdown,
)
from models.architecture_model import ArchitectureModel
from models.domain_discovery import BusinessCapability as BusinessCapability
from models.domain_discovery import BusinessDomain as BusinessDomain
from models.domain_discovery import BusinessIntegration as BusinessIntegration
from models.domain_discovery import CustomModule as CustomModule
from models.domain_discovery import DomainDiscovery as DomainDiscovery
from models.models import RepositoryModel
from models.repository_archetype import ArchetypeResult, RepositoryArchetype

_DOC_SUFFIXES = {".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".xml"}


_MAX_EVIDENCE_FILES = 12


_MAX_EVIDENCE_BYTES = 12_000


def _tokens(value: str) -> set[str]:
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", separated)
    return set(re.findall(r"[a-z0-9]+", separated.casefold()))


def _matching_domains(value: str) -> set[str]:
    tokens = _tokens(value)
    return {
        name for name, rule in _DOMAIN_RULES.items()
        if tokens & rule["keywords"]
    }


def _custom_modules(areas: list[RepositoryArea]) -> list[CustomModule]:
    modules = []
    for area in areas:
        if area.kind not in {"custom module", "workspace module", "business area"}:
            continue
        parts = area.path.split("/")
        owner = parts[2] if area.kind == "custom module" and len(parts) > 3 else None
        domains = _matching_domains(area.name + " " + area.path)
        priority = "high" if domains & _HIGH_VALUE_DOMAINS else "medium"
        modules.append(CustomModule(area.name, area.path, area.kind, owner, priority))
    return sorted(modules, key=lambda item: (item.path.casefold(), item.name.casefold()))


def _documentation_evidence(model: RepositoryModel) -> list[tuple[str, str]]:
    if not model.root_path:
        return []
    candidate_paths = list(dict.fromkeys([
        *model.onboarding_docs,
        *model.important_files,
        *(item.path for item in model.files if Path(item.path).suffix.lower() in _DOC_SUFFIXES),
    ]))
    documents: list[tuple[str, str]] = []
    for relative_path in candidate_paths:
        if len(documents) >= _MAX_EVIDENCE_FILES:
            break
        path_parts = {part.casefold() for part in Path(relative_path).parts}
        if "outputs" in path_parts or classify_path(relative_path)[0] in {"low", "ignored"}:
            continue
        if Path(relative_path).suffix.lower() not in _DOC_SUFFIXES and Path(relative_path).name.lower() not in {
            "readme", "license",
        }:
            continue
        try:
            content = (Path(model.root_path) / relative_path).read_text(
                encoding="utf-8", errors="replace"
            )[:_MAX_EVIDENCE_BYTES]
        except OSError:
            continue
        documents.append((relative_path, content))
    return documents


def analyze_domains(
    model: RepositoryModel, architecture: ArchitectureModel | None = None,
    archetype: ArchetypeResult | None = None,
) -> DomainDiscovery:
    """Infer business-focused onboarding facts from model paths, docs, and integrations."""
    if archetype is not None and archetype.archetype != RepositoryArchetype.BUSINESS_APPLICATION:
        relevance = architecture.repository_relevance if architecture else analyze_relevance(model)
        return DomainDiscovery(deferred_areas=sorted(
            set(relevance.paths.get("low", [])) | set(relevance.paths.get("ignored", [])),
            key=str.casefold,
        ))
    model = relevant_model(model)
    relevance = architecture.repository_relevance if architecture else analyze_relevance(model)
    areas = relevance.areas
    modules = _custom_modules(areas)
    documents = _documentation_evidence(model)
    docs = f"{model.readme_summary}\n" + "\n".join(
        content for _, content in documents
    )
    source_paths = [item.path for item in model.files if item.kind == "source"]

    evidence_by_domain: dict[str, set[str]] = {}
    modules_by_domain: dict[str, set[str]] = {}
    documentation_domains = _matching_domains(docs)
    for name in documentation_domains:
        matched_paths = {
            path for path, content in documents if name in _matching_domains(content)
        }
        if name in _matching_domains(model.readme_summary):
            matched_paths.add("Repository description")
        evidence_by_domain.setdefault(name, set()).update(
            matched_paths or ["Repository documentation"]
        )
    for module in modules:
        for name in _matching_domains(module.name + " " + module.path):
            modules_by_domain.setdefault(name, set()).add(module.name)
            evidence_by_domain.setdefault(name, set()).add(module.path)
    for path in source_paths:
        for name in _matching_domains(path):
            evidence_by_domain.setdefault(name, set()).add(path)

    integrations = []
    for integration_name in architecture.external_dependencies if architecture else []:
        domains = _matching_domains(integration_name)
        priority = "high" if domains & _HIGH_VALUE_DOMAINS else "medium"
        evidence = ["Inferred external dependency in Architecture Discovery."]
        integrations.append(BusinessIntegration(
            name=integration_name,
            priority=priority,
            domains=sorted(domains),
            evidence=evidence,
        ))
        for domain in domains:
            evidence_by_domain.setdefault(domain, set()).update(evidence)
    integrations.sort(key=lambda item: (item.priority != "high", item.name.casefold()))

    domains = []
    for name, evidence in evidence_by_domain.items():
        related_modules = sorted(modules_by_domain.get(name, set()), key=str.casefold)
        has_docs = bool(documentation_domains and name in documentation_domains)
        related_integrations = any(name in integration.domains for integration in integrations)
        priority = (
            "high" if related_modules or (
                related_integrations and name in _HIGH_VALUE_DOMAINS
            ) else "medium" if has_docs or related_integrations else "low"
        )
        domains.append(BusinessDomain(
            name=name,
            priority=priority,
            responsibilities=[_DOMAIN_RULES[name]["responsibility"]],
            modules=related_modules,
            evidence=sorted(evidence, key=str.casefold)[:8],
        ))
    domains.sort(key=lambda item: (
        {"high": 0, "medium": 1, "low": 2}[item.priority],
        item.name.casefold(),
    ))

    integration_domains = {
        domain for integration in integrations for domain in integration.domains
    }
    all_names = f"{docs}\n" + "\n".join(
        [module.name + " " + module.path for module in modules]
        + source_paths
        + [item.name for item in integrations]
    )
    all_tokens = _tokens(all_names)
    capabilities = []
    for name, keywords in _CAPABILITY_RULES.items():
        matched = all_tokens & keywords
        if not matched:
            continue
        related_domains = sorted(
            _CAPABILITY_DOMAINS[name] & {item.name for item in domains}
        )
        related_modules = sorted({
            module.name for module in modules
            if _tokens(module.name + " " + module.path) & keywords
        }, key=str.casefold)
        capability_priority = (
            "high" if related_modules or integration_domains.intersection(related_domains)
            else "medium"
        )
        capabilities.append(BusinessCapability(
            name=name,
            priority=capability_priority,
            domains=related_domains,
            modules=related_modules,
            evidence=sorted({
                *[module.path for module in modules if module.name in related_modules],
                *[
                    path for path, content in documents
                    if _tokens(content) & keywords
                ],
                *(["Repository description"] if _tokens(model.readme_summary) & keywords else []),
            }, key=str.casefold)[:8],
        ))
    capabilities.sort(key=lambda item: (
        {"high": 0, "medium": 1, "low": 2}[item.priority],
        item.name.casefold(),
    ))

    priorities = []
    if domains:
        priorities.append({
            "priority": "1",
            "focus": "Learn the highest-value business domains",
            "detail": ", ".join(item.name for item in domains if item.priority == "high")
            or ", ".join(item.name for item in domains[:3]),
        })
    if modules:
        priorities.append({
            "priority": str(len(priorities) + 1),
            "focus": "Review custom application modules",
            "detail": ", ".join(module.name for module in modules[:8]),
        })
    critical_integrations = [item.name for item in integrations if item.priority == "high"]
    if critical_integrations:
        priorities.append({
            "priority": str(len(priorities) + 1),
            "focus": "Understand business-critical integrations",
            "detail": ", ".join(critical_integrations[:6]),
        })
    if capabilities:
        priorities.append({
            "priority": str(len(priorities) + 1),
            "focus": "Trace important business capabilities",
            "detail": ", ".join(item.name for item in capabilities[:6]),
        })
    priorities.append({
        "priority": str(len(priorities) + 1),
        "focus": "Learn framework and deployment architecture",
        "detail": "Use the architecture artifacts after understanding the application’s business behavior.",
    })

    deferred = []
    if architecture:
        deferred = sorted(
            set(architecture.repository_relevance.paths.get("low", []))
            | set(architecture.repository_relevance.paths.get("ignored", [])),
            key=str.casefold,
        )
    return DomainDiscovery(
        domains=domains,
        capabilities=capabilities,
        integrations=integrations,
        custom_modules=modules,
        onboarding_priorities=priorities,
        deferred_areas=deferred,
    )


def domain_learning_steps(
    discovery: DomainDiscovery,
    *,
    top_domain_names: list[str] | None = None,
    top_module_names: list[str] | None = None,
    top_capability_names: list[str] | None = None,
) -> list[dict[str, str]]:
    """Return business-first learning steps to precede the general architecture path."""
    steps = []
    if discovery.domains:
        names = (
            top_domain_names if top_domain_names is not None
            else [item.name for item in discovery.domains[:5]]
        )
        if names:
            steps.append({
                "title": "Understand the business domains",
                "detail": "Start with " + ", ".join(names) + " and their responsibilities.",
            })
    if discovery.custom_modules:
        module_names = (
            top_module_names if top_module_names is not None
            else [item.name for item in discovery.custom_modules[:6]]
        )
        if module_names:
            steps.append({
                "title": "Review custom application modules",
                "detail": "Focus on " + ", ".join(f"`{name}`" for name in module_names[:6])
                + "; these are repository-specific business areas.",
            })
    critical = [item.name for item in discovery.integrations if item.priority == "high"]
    if critical:
        steps.append({
            "title": "Trace business-critical integrations",
            "detail": "Understand where the application crosses ownership boundaries to "
            + ", ".join(critical[:5]) + ".",
        })
    capability_names = (
        top_capability_names if top_capability_names is not None
        else [item.name for item in discovery.capabilities[:5]]
    )
    if capability_names:
        steps.append({
            "title": "Follow important business workflows",
            "detail": "Trace " + ", ".join(capability_names[:5])
            + " before drilling into lower-level architecture.",
        })
    return steps
