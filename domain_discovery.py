"""Heuristic discovery of business domains and capabilities from repository facts."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from architecture_model import ArchitectureModel
from models import RepositoryModel
from repository_relevance import (
    RepositoryArea,
    analyze_relevance,
    classify_path,
    relevant_model,
)


_DOMAIN_RULES = {
    "Payments": {
        "keywords": {"payment", "payments", "visa", "mastercard", "stripe", "paypal", "billing", "refund", "authorize"},
        "responsibility": "Handles payment methods, authorization, capture, and refunds.",
    },
    "Catalog": {
        "keywords": {"catalog", "product", "products", "attribute", "attributes", "category", "categories"},
        "responsibility": "Manages product information, attributes, and category organization.",
    },
    "Orders": {
        "keywords": {"order", "orders", "checkout", "cart", "basket"},
        "responsibility": "Supports cart, checkout, and order lifecycle workflows.",
    },
    "Inventory": {
        "keywords": {"inventory", "stock", "warehouse", "availability"},
        "responsibility": "Tracks stock, warehouse, and product availability information.",
    },
    "Customer Experience": {
        "keywords": {"customer", "customers", "account", "accounts", "registration", "profile", "identity"},
        "responsibility": "Supports customer accounts, registration, and profile experiences.",
    },
    "Shipping": {
        "keywords": {"shipping", "shipment", "delivery", "fulfillment", "carrier"},
        "responsibility": "Coordinates shipment, delivery, and fulfillment workflows.",
    },
    "Marketing": {
        "keywords": {"marketing", "campaign", "campaigns", "advertising", "advertisement", "ad", "ads", "promotion", "coupon"},
        "responsibility": "Supports campaigns, promotions, and customer-facing merchandising.",
    },
    "Search": {
        "keywords": {"search", "index", "indexing", "elasticsearch", "opensearch"},
        "responsibility": "Indexes and retrieves information for product and content discovery.",
    },
    "Loyalty": {
        "keywords": {"loyalty", "rewards", "points"},
        "responsibility": "Manages customer rewards, points, and loyalty programs.",
    },
    "ERP Integrations": {
        "keywords": {"erp", "sap", "netsuite", "dynamics", "oracle"},
        "responsibility": "Connects application workflows with enterprise resource planning systems.",
    },
}
_HIGH_VALUE_DOMAINS = {"Payments", "Orders", "Inventory", "ERP Integrations"}
_CAPABILITY_RULES = {
    "Customer Registration": {"customer", "account", "registration", "register", "create"},
    "Order Processing": {"order", "checkout", "cart", "process"},
    "Payment Authorization": {"payment", "visa", "mastercard", "stripe", "paypal", "authorize"},
    "Inventory Management": {"inventory", "stock", "warehouse", "availability"},
    "Product Search": {"product", "catalog", "search", "index", "indexing"},
    "ERP Synchronization": {"erp", "sap", "netsuite", "dynamics", "oracle", "sync", "synchronization"},
    "Shipping and Fulfillment": {"shipping", "shipment", "delivery", "fulfillment", "carrier"},
    "Promotions and Campaigns": {"marketing", "campaign", "advertising", "ad", "ads", "promotion", "coupon"},
    "Customer Loyalty": {"loyalty", "rewards", "points"},
}
_CAPABILITY_DOMAINS = {
    "Customer Registration": {"Customer Experience"},
    "Order Processing": {"Orders"},
    "Payment Authorization": {"Payments"},
    "Inventory Management": {"Inventory"},
    "Product Search": {"Catalog", "Search"},
    "ERP Synchronization": {"ERP Integrations"},
    "Shipping and Fulfillment": {"Shipping"},
    "Promotions and Campaigns": {"Marketing"},
    "Customer Loyalty": {"Loyalty"},
}
_DOC_SUFFIXES = {".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".xml"}
_MAX_EVIDENCE_FILES = 12
_MAX_EVIDENCE_BYTES = 12_000


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
    model: RepositoryModel, architecture: ArchitectureModel | None = None
) -> DomainDiscovery:
    """Infer business-focused onboarding facts from model paths, docs, and integrations."""
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


def render_business_domains_markdown(discovery: DomainDiscovery) -> str:
    lines = ["# Business Domains", ""]
    if not discovery.domains:
        lines += ["No business domains were confidently inferred from the available repository evidence.", ""]
    for domain in discovery.domains:
        lines += [
            f"## {domain.name} — {domain.priority.title()} priority",
            "",
            domain.responsibilities[0],
            "",
            "**Related modules:** "
            + (", ".join(f"`{name}`" for name in domain.modules[:5]) or "None detected")
            + (f" (+{len(domain.modules) - 5} more in `domain_map.json`)" if len(domain.modules) > 5 else ""),
            "",
            "**Evidence:** " + (", ".join(f"`{item}`" for item in domain.evidence) or "None recorded"),
            "",
        ]
    if discovery.custom_modules:
        lines += [
            "## Custom module sample",
            "",
            "Prioritized choices are in `critical_modules.md`.",
            "",
        ]
        for module in discovery.custom_modules[:10]:
            owner = f"; inferred owner `{module.owner}`" if module.owner else ""
            lines.append(f"- `{module.name}` (`{module.path}`; {module.kind}{owner})")
        omitted = len(discovery.custom_modules) - min(len(discovery.custom_modules), 10)
        if omitted:
            lines.append(
                f"- {omitted} additional modules are listed in `domain_map.json`."
            )
        lines.append("")
    return "\n".join(lines)


def render_business_capabilities_markdown(discovery: DomainDiscovery) -> str:
    lines = ["# Business Capabilities", ""]
    if not discovery.capabilities:
        lines += ["No business capabilities were inferred from the available repository evidence.", ""]
    for capability in discovery.capabilities:
        lines.append(f"- **{capability.name}** ({capability.priority} priority)")
        if capability.domains:
            lines.append(f"  - Domains: {', '.join(capability.domains)}")
        if capability.modules:
            modules = capability.modules[:5]
            remaining = len(capability.modules) - len(modules)
            suffix = f" (+{remaining} more in `domain_map.json`)" if remaining else ""
            lines.append(f"  - Modules: {', '.join(f'`{name}`' for name in modules)}{suffix}")
        if capability.evidence:
            lines.append(f"  - Evidence: {', '.join(f'`{path}`' for path in capability.evidence)}")
    if discovery.integrations:
        lines += ["", "## External integrations and ownership boundaries", ""]
        for integration in discovery.integrations[:5]:
            domains = f"; related domains: {', '.join(integration.domains)}" if integration.domains else ""
            lines.append(
                f"- **{integration.name}** ({integration.priority} priority; "
                f"boundary: {integration.ownership_boundary}{domains})"
            )
        if len(discovery.integrations) > 5:
            lines.append(
                f"- {len(discovery.integrations) - 5} additional integrations are listed in `domain_map.json`."
            )
    lines.append("")
    return "\n".join(lines)


def render_onboarding_priorities_markdown(
    discovery: DomainDiscovery,
    *,
    top_domain_names: list[str] | None = None,
    top_module_names: list[str] | None = None,
    top_capability_names: list[str] | None = None,
) -> str:
    lines = [
        "# Onboarding Priorities",
        "",
        "A suggested one-week focus. Priorities are heuristic and should be confirmed with a maintainer.",
        "",
    ]
    for day, priority in enumerate(discovery.onboarding_priorities, 1):
        detail = priority["detail"]
        if (
            priority["focus"] == "Learn the highest-value business domains"
            and top_domain_names is not None
        ):
            detail = ", ".join(top_domain_names[:4]) or (
                "No high-confidence domain was inferred; validate business priorities with a maintainer."
            )
        elif (
            priority["focus"] == "Review custom application modules"
            and top_module_names is not None
        ):
            detail = ", ".join(top_module_names[:8]) or (
                "No module was strongly matched to a business-critical domain; consult the domain map as workflows lead there."
            )
        elif (
            priority["focus"] == "Trace important business capabilities"
            and top_capability_names is not None
        ):
            detail = ", ".join(top_capability_names[:5]) or (
                "No capability was strongly matched to custom modules or integrations; validate workflows with a maintainer."
            )
        lines += [
            f"## Focus {day}: {priority['focus']}",
            "",
            detail,
            "",
        ]
    if discovery.deferred_areas:
        deferred_roots = []
        boundary_names = {
            "vendor", "node_modules", "generated", "cache", "caches", "tmp",
            "temp", "dist", "build",
        }
        for path in sorted(
            discovery.deferred_areas,
            key=lambda item: (len(item.split("/")), item.casefold()),
        ):
            parts = path.split("/")
            boundary = next(
                (index for index, part in enumerate(parts) if part.casefold() in boundary_names),
                len(parts) - 1,
            )
            root = "/".join(parts[:boundary + 1])
            if not any(root == parent or root.startswith(parent + "/") for parent in deferred_roots):
                deferred_roots.append(root)
        displayed_roots = deferred_roots[:8]
        lines += [
            "## Defer initially",
            "",
            "These vendor or generated areas are supporting material; avoid starting there unless a task requires it:",
            "",
        ]
        lines += [f"- `{path}/`" for path in displayed_roots]
        omitted = len(deferred_roots) - len(displayed_roots)
        if omitted:
            lines.append(f"- {omitted} additional low-relevance boundaries are available in `domain_map.json`.")
        lines.append("")
    else:
        lines += [
            "## Defer initially",
            "",
            "Start with the business domains and custom modules above; explore supporting infrastructure when a workflow leads there.",
            "",
        ]
    lines += [
        "This is a suggested learning order, not a guarantee that omitted areas are safe to change or ignore.",
        "",
    ]
    return "\n".join(lines)
