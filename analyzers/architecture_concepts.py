"""Architecture concepts."""
from __future__ import annotations

import re
from pathlib import Path

from models.models import RepositoryModel

_CONCEPTS = {
    "api": ("API Layer", "interface", "Presentation", "Exposes application capabilities through an API."),
    "routes": ("Routes", "routing", "Presentation", "Maps incoming requests to application handlers."),
    "controllers": ("Controllers", "application", "Application", "Coordinates requests and application work."),
    "controller": ("Controllers", "application", "Application", "Coordinates requests and application work."),
    "services": ("Services", "application", "Application", "Implements application workflows and use cases."),
    "service": ("Services", "application", "Application", "Implements application workflows and use cases."),
    "domain": ("Domain Layer", "domain", "Domain", "Contains core rules and domain concepts."),
    "models": ("Domain Layer", "domain", "Domain", "Represents application entities and domain data."),
    "model": ("Domain Layer", "domain", "Domain", "Represents application entities and domain data."),
    "entities": ("Domain Layer", "domain", "Domain", "Represents core entities."),
    "repositories": ("Persistence Layer", "persistence", "Data and Infrastructure", "Provides access to persisted application data."),
    "repository": ("Persistence Layer", "persistence", "Data and Infrastructure", "Provides access to persisted application data."),
    "database": ("Persistence Layer", "persistence", "Data and Infrastructure", "Configures or accesses application data stores."),
    "db": ("Persistence Layer", "persistence", "Data and Infrastructure", "Configures or accesses application data stores."),
    "infrastructure": ("Infrastructure Layer", "infrastructure", "Data and Infrastructure", "Connects application behavior to external and platform concerns."),
    "infra": ("Infrastructure Layer", "infrastructure", "Data and Infrastructure", "Connects application behavior to external and platform concerns."),
    "middleware": ("Middleware", "request_pipeline", "Application", "Applies cross-cutting behavior during request processing."),
    "pages": ("Pages", "presentation", "Presentation", "Defines page-level user experiences and navigation."),
    "components": ("Components", "presentation", "Presentation", "Builds reusable pieces of the user interface."),
    "hooks": ("Hooks", "presentation", "Presentation", "Encapsulates reusable UI state and lifecycle behavior."),
    "state": ("State Management", "state", "Application", "Coordinates application or user-interface state."),
    "store": ("State Management", "state", "Application", "Coordinates application or user-interface state."),
    "redux": ("State Management", "state", "Application", "Coordinates application or user-interface state."),
    "client": ("API Client Layer", "integration", "Data and Infrastructure", "Connects application behavior to remote APIs."),
    "api_client": ("API Client Layer", "integration", "Data and Infrastructure", "Connects application behavior to remote APIs."),
    "modules": ("Modules", "application", "Application", "Groups related application capabilities and their providers."),
    "providers": ("Providers", "integration", "Data and Infrastructure", "Supplies shared services or integrations to application modules."),
    "provider": ("Providers", "integration", "Data and Infrastructure", "Supplies shared services or integrations to application modules."),
    "guards": ("Guards", "request_pipeline", "Application", "Applies authorization or access checks to requests."),
    "interceptors": ("Interceptors", "request_pipeline", "Application", "Wraps request handling with cross-cutting behavior."),
    "runtime": ("Runtime", "runtime", "Runtime and Extensions", "Coordinates application startup and capability execution."),
    "registries": ("Registries", "registry", "Runtime and Extensions", "Discovers and manages registered capabilities."),
    "registry": ("Registries", "registry", "Runtime and Extensions", "Discovers and manages registered capabilities."),
    "plugins": ("Plugins", "extension", "Runtime and Extensions", "Provides optional or extensible capabilities."),
    "plugin": ("Plugins", "extension", "Runtime and Extensions", "Provides optional or extensible capabilities."),
    "observer": ("Observers", "extension", "Runtime and Extensions", "Responds to application events."),
    "observers": ("Observers", "extension", "Runtime and Extensions", "Responds to application events."),
    "skills": ("Skills", "extension", "Runtime and Extensions", "Implements task-oriented application capabilities."),
    "skill": ("Skills", "extension", "Runtime and Extensions", "Implements task-oriented application capabilities."),
    "artifacts": ("Artifacts", "output", "Runtime and Extensions", "Represents outputs produced or managed by the system."),
    "artifact": ("Artifacts", "output", "Runtime and Extensions", "Represents outputs produced or managed by the system."),
    "scanner": ("Repository Scanner", "scanner", "Repository Processing", "Discovers repository files and metadata."),
    "scanners": ("Repository Scanner", "scanner", "Repository Processing", "Discovers repository files and metadata."),
    "scan": ("Repository Scanner", "scanner", "Repository Processing", "Discovers repository files and metadata."),
    "analyzer": ("Analyzers", "analysis", "Repository Processing", "Interprets repository facts for a specific capability."),
    "analyzers": ("Analyzers", "analysis", "Repository Processing", "Interprets repository facts for a specific capability."),
    "analysis": ("Analyzers", "analysis", "Repository Processing", "Interprets repository facts for a specific capability."),
    "dashboard": ("Dashboard", "presentation", "Presentation", "Presents repository onboarding information to developers."),
    "visualization": ("Visualizations", "presentation", "Presentation", "Renders repository structure and architecture."),
    "visualizations": ("Visualizations", "presentation", "Presentation", "Renders repository structure and architecture."),
    "skill_result": ("Skill Result", "result", "Runtime and Extensions", "Carries the outcome and generated artifacts of a skill."),
    "model_request": ("Model Requests", "request", "Integrations", "Represents requests sent to an AI or other model provider."),
    "model_response": ("Model Responses", "response", "Integrations", "Represents responses returned by a model provider."),
    "agent": ("Agents", "agent", "Runtime", "Coordinates agent execution and tool use."),
    "llm": ("Model Backends", "integration", "Integrations", "Provides access to language models and their backends."),
    "tools": ("Tools", "extension", "Runtime", "Defines and executes capabilities available to the application."),
    "tool": ("Tools", "extension", "Runtime", "Defines and executes capabilities available to the application."),
    "rag": ("Retrieval", "retrieval", "Data and Infrastructure", "Retrieves contextual data for application workflows."),
    "mcp": ("MCP Integration", "integration", "Integrations", "Connects to external tools through the Model Context Protocol."),
}


def _framework(model: RepositoryModel, name: str) -> bool:
    return any(name in framework.lower() for framework in model.frameworks)


def _system_type(model: RepositoryModel, text: str, entry_points: list[str]) -> str:
    if _framework(model, "react") or _framework(model, "next") or _framework(model, "vue"):
        return "Web application"
    if "microservice" in text:
        return "Microservice"
    if re.search(r"\b(?:is|as)\s+a\s+(?:library|framework|package)\b", text):
        return "Library or framework"
    if any(_framework(model, key) for key in ("laravel", "nestjs", "fastapi", "django", "express", "spring", "magento")):
        return "Backend application"
    if re.search(r"\b(?:python3?|node)\s+[\w./-]+\.(?:py|js|mjs)\b", text) or any(
        Path(path).name.lower() in {"cli.py", "manage.py", "artisan"} for path in entry_points
    ):
        return "CLI application"
    if any(Path(file.path).name.lower() in {"dockerfile", "docker-compose.yml", "compose.yaml"} for file in model.files):
        return "Backend service"
    if not entry_points and any(Path(file.path).name.lower() in {"pyproject.toml", "package.json", "cargo.toml", "go.mod"} for file in model.files):
        return "Library or framework"
    return "Application"


def _framework_key(model: RepositoryModel) -> str | None:
    for key in ("magento", "laravel", "nestjs"):
        if _framework(model, key):
            return key
    if _framework(model, "react") or _framework(model, "next"):
        return "react"
    return None


def _concept_for(
    folder: str, framework: str | None, runtime_layout: bool
) -> tuple[str, str, str, str] | None:
    if framework == "magento":
        if folder in {"domain", "model", "models", "entities"}:
            return (
                "Models and Domain Code", "domain", "Domain",
                ("Groups paths named Model or Domain. These may contain business data or behavior; "
                "the names alone do not establish a shared domain layer."),
            )
        if folder in {"resourcemodel", "resourcemodels"}:
            return (
                "Resource Models", "persistence", "Data and Infrastructure",
                ("Magento ResourceModel paths commonly contain persistence-related code; "
                "check the individual implementation."),
            )
        if folder in {"provider", "providers"}:
            return (
                "Provider Classes", "integration", "Data and Infrastructure",
                ("Groups classes or paths named Provider, including possible configuration or UI data "
                "providers. Their individual responsibilities must be checked."),
            )
        if folder in {
            "api", "controller", "controllers", "service", "services",
            "repository", "repositories", "observer", "observers",
            "plugin", "plugins", "components", "pages",
        }:
            return _CONCEPTS.get(folder)
        return None
    if framework == "react":
        return {
            "app": ("Pages", "presentation", "Presentation", "Defines page-level user experiences and navigation."),
            "pages": ("Pages", "presentation", "Presentation", "Defines page-level user experiences and navigation."),
            "components": _CONCEPTS["components"],
            "hooks": _CONCEPTS["hooks"],
            "store": _CONCEPTS["state"],
            "redux": _CONCEPTS["state"],
            "zustand": _CONCEPTS["state"],
            "state": _CONCEPTS["state"],
            "api": _CONCEPTS["client"],
            "client": _CONCEPTS["client"],
            "services": _CONCEPTS["client"],
        }.get(folder)
    if framework == "laravel":
        name = {
            "routes": "Routes", "controllers": "Controllers", "services": "Services",
            "models": "Models", "middleware": "Middleware",
        }.get(folder)
        laravel_concepts = {
            "Routes": ("Routes", "routing", "Presentation", "Maps incoming requests to application handlers."),
            "Controllers": ("Controllers", "application", "Application", "Coordinates requests and application work."),
            "Services": ("Services", "application", "Application", "Implements application workflows and use cases."),
            "Models": ("Models", "domain", "Domain", "Represents application entities and domain data."),
            "Middleware": ("Middleware", "request_pipeline", "Application", "Applies cross-cutting behavior during request processing."),
        }
        return laravel_concepts.get(name)
    if framework == "nestjs":
        if folder in {"controllers", "providers", "modules", "guards", "interceptors"}:
            return _CONCEPTS.get(folder)
        return None
    if runtime_layout and folder in {"providers", "provider"}:
        return _CONCEPTS["providers"]
    return _CONCEPTS.get(folder)


def _concept_for_class(class_name: str, framework: str | None = None) -> tuple[str, str, str, str] | None:
    normalized = re.sub(r"[^a-z]", "", class_name.lower())
    special_names = {
        "skillresult": "skill_result",
        "modelrequest": "model_request",
        "modelrequests": "model_request",
        "modelresponse": "model_response",
        "modelresponses": "model_response",
    }
    if normalized in special_names:
        return _CONCEPTS[special_names[normalized]]
    for suffix, concept in (
        ("agent", "agent"),
        ("llmbackend", "llm"),
        ("retriever", "rag"),
        ("toolregistry", "tools"),
        ("artifactregistry", "registries"),
        ("registry", "registries"),
        ("provider", "providers"),
        ("skill", "skills"),
        ("artifact", "artifacts"),
        ("runtime", "runtime"),
        ("controller", "controllers"),
        ("service", "services"),
        ("repository", "repositories"),
        ("model", "models"),
        ("module", "modules"),
        ("plugin", "plugins"),
        ("scanner", "scanner"),
        ("analyzer", "analyzer"),
        ("dashboard", "dashboard"),
        ("visualization", "visualization"),
    ):
        if normalized.endswith(suffix):
            matched = _concept_for(concept, framework, False)
            return matched if framework == "magento" else matched or _CONCEPTS[concept]
    return None


def _concept_for_module(module_stem: str, framework: str | None = None) -> tuple[str, str, str, str] | None:
    normalized = re.sub(r"[^a-z]", "", module_stem.lower())
    special_names = {
        "skillresult": "skill_result",
        "modelrequest": "model_request",
        "modelrequests": "model_request",
        "modelresponse": "model_response",
        "modelresponses": "model_response",
    }
    if normalized in special_names:
        return _CONCEPTS[special_names[normalized]]
    tokens = set(re.findall(r"[a-z0-9]+", module_stem.lower()))
    for token in (
        "runtime", "scanner", "scanners", "scan", "analyzer", "analyzers",
        "analysis", "skill", "skills", "provider", "providers", "registry",
        "registries", "artifact", "artifacts", "dashboard", "visualization",
        "visualizations", "api", "routes", "controllers", "services",
        "repositories", "models", "plugins", "pages", "components",
        "agent", "llm", "tools", "rag", "mcp",
    ):
        if token in tokens:
            matched = _concept_for(token, framework, False)
            return matched if framework == "magento" else matched or _CONCEPTS.get(token)
    return None
