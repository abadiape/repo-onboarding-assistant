"""Extract and render repository-centric architecture without AST parsing."""
from __future__ import annotations

import json
import posixpath
import re
from pathlib import Path

from models.architecture_model import (
    ArchitectureComponent,
    ArchitectureModel,
    ArchitectureRelationship,
    ArchitectureSubsystem,
)
from models.models import RepositoryModel
from analyzers.repository_relevance import RepositoryRelevance, analyze_relevance, relevant_model


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
_IGNORED_AREAS = {
    "test", "tests", "docs", "examples", "example", "build", "dist",
    "vendor", "node_modules", "outputs", "templates", ".github",
}
_SERVICE_TERMS = {
    "postgres": ("PostgreSQL", "relational database"),
    "postgresql": ("PostgreSQL", "relational database"),
    "psycopg": ("PostgreSQL", "relational database"),
    "psycopg2": ("PostgreSQL", "relational database"),
    "asyncpg": ("PostgreSQL", "relational database"),
    "mysql": ("MySQL", "relational database"),
    "pymysql": ("MySQL", "relational database"),
    "mariadb": ("MariaDB", "relational database"),
    "sqlite": ("SQLite", "relational database"),
    "mongodb": ("MongoDB", "document database"),
    "pymongo": ("MongoDB", "document database"),
    "dynamodb": ("DynamoDB", "managed database"),
    "redis": ("Redis", "cache"),
    "memcached": ("Memcached", "cache"),
    "elasticsearch": ("Elasticsearch", "search service"),
    "opensearch": ("OpenSearch", "search service"),
    "kafka": ("Kafka", "message broker"),
    "rabbitmq": ("RabbitMQ", "message broker"),
    "sqs": ("Amazon SQS", "message queue"),
    "stripe": ("Stripe", "payment service"),
    "sentry": ("Sentry", "error monitoring"),
    "auth0": ("Auth0", "identity provider"),
    "aws": ("AWS", "cloud platform"),
    "azure": ("Azure", "cloud platform"),
    "gcp": ("Google Cloud", "cloud platform"),
}
_DOC_EXTENSIONS = {".md", ".rst", ".txt"}
_CONFIG_FILES = {
    "package.json", "pyproject.toml", "requirements.txt", "requirements-dev.txt",
    "composer.json", "pom.xml", "build.gradle", "build.gradle.kts", "cargo.toml",
    "go.mod", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml",
}
_CONFIG_EXTENSIONS = {
    ".conf", ".ini", ".json", ".properties", ".toml", ".xml", ".yaml", ".yml",
}
_IGNORED_CONTEXT_AREAS = {
    "test", "tests", "example", "examples", "build", "dist", "vendor",
    "node_modules", "outputs", "templates",
}
_FRAMEWORK_GUIDANCE = {
    "react": "React composes the user interface from pages, reusable components, hooks, and state.",
    "next": "Next.js organizes a React web application around routes and page-level UI composition.",
    "laravel": "Laravel routes requests through middleware and controllers to application services and models.",
    "nestjs": "NestJS modules compose controllers and providers, with guards and interceptors around request handling.",
    "django": "Django commonly organizes web behavior around URL routing, views, models, and middleware.",
    "fastapi": "FastAPI commonly exposes Python functions as HTTP endpoints and composes request dependencies.",
    "express": "Express commonly composes a Node.js HTTP application from middleware and routes.",
    "spring": "Spring commonly composes backend behavior from configured application components and web endpoints.",
    "magento": "Magento organizes commerce behavior through modules, configuration, and extension mechanisms.",
}
_RELATION_RULES = {
    "react": [
        ("Pages", "Components", "renders"),
        ("Pages", "Hooks", "uses"),
        ("Hooks", "State Management", "reads and updates"),
        ("Pages", "API Client Layer", "requests data through"),
    ],
    "laravel": [
        ("Routes", "Middleware", "passes through"),
        ("Middleware", "Controllers", "dispatches to"),
        ("Routes", "Controllers", "dispatches to"),
        ("Controllers", "Services", "delegates to"),
        ("Services", "Models", "uses"),
    ],
    "nestjs": [
        ("Modules", "Controllers", "registers"),
        ("Modules", "Providers", "registers"),
        ("Controllers", "Providers", "delegates to"),
        ("Guards", "Controllers", "authorizes"),
        ("Interceptors", "Controllers", "wraps"),
    ],
    "backend": [
        ("API Layer", "Controllers", "dispatches to"),
        ("Controllers", "Services", "delegates to"),
        ("Services", "Domain Layer", "applies"),
        ("Domain Layer", "Persistence Layer", "reads and writes through"),
        ("Persistence Layer", "Infrastructure Layer", "uses"),
    ],
    "runtime": [
        ("Runtime", "Registries", "discovers through"),
        ("Runtime", "Providers", "uses"),
        ("Runtime", "Skills", "executes"),
        ("Registries", "Skills", "makes available"),
        ("Registries", "Plugins", "makes available"),
        ("Skills", "Providers", "invokes"),
        ("Skills", "Artifacts", "produces"),
        ("Registries", "Artifacts", "tracks"),
        ("Artifacts", "Registries", "registers with"),
        ("Skills", "Skill Result", "returns"),
        ("Skill Result", "Artifacts", "contains"),
        ("Providers", "Model Requests", "handles"),
        ("Providers", "Model Responses", "returns"),
        ("Model Responses", "Skill Result", "populates"),
    ],
}

_CLASS_DECLARATION = re.compile(
    r"^\s*(?:(?:export|default|public|private|internal|abstract|final|sealed|static|data|open|pub|partial)\s+)*(?:class|interface|struct|record|trait|enum|type)\s+([A-Z][A-Za-z0-9_]*)",
    re.MULTILINE,
)
_IMPORT_PATTERNS = (
    (re.compile(r"^\s*from\s+([.\w/]+)\s+import\b"), "imports"),
    (re.compile(r"^\s*import\s+([.\w/]+)(?:\s+as\b|$)"), "imports"),
    (re.compile(r"\bexport\b[^\n;]*?\bfrom\s*[\"']([^\"']+)[\"']"), "re-exports"),
    (re.compile(r"\bimport\b[^\n;]*?\bfrom\s*[\"']([^\"']+)[\"']"), "imports"),
    (re.compile(r"\b(?:import|require|include)\s*(?:\(\s*)?[\"']([^\"']+)[\"']"), "imports"),
    (re.compile(r"^\s*(?:using|use)\s+([\w\\.*]+)\s*;?"), "imports"),
)
_RELATION_WORDS = {
    "produces": "produces",
    "produce": "produces",
    "contains": "contains",
    "executes": "executes",
    "handles": "handles",
    "tracks": "tracks",
    "track": "tracks",
    "registers": "registers",
    "uses": "uses",
    "creates": "creates",
    "provides": "provides",
    "returns": "returns",
    "populates": "populates",
    "invokes": "invokes",
    "delegates": "delegates to",
    "routes": "routes to",
    "dispatches": "dispatches to",
}
def _parts(path: str) -> list[str]:
    return [part.lower().replace("-", "_") for part in path.replace("\\", "/").split("/") if part]


def _is_config_file(path: Path, kind: str) -> bool:
    return (
        kind == "manifest"
        or path.name.lower() in _CONFIG_FILES
        or (kind == "file" and path.suffix.lower() in _CONFIG_EXTENSIONS)
    )


def _source_code_lines(content: str) -> list[tuple[int, str]]:
    code_lines = []
    quote_delimiter: str | None = None
    in_block_comment = False
    for line_number, original_line in enumerate(content.splitlines(), 1):
        line = original_line
        if in_block_comment:
            if "*/" not in line:
                continue
            line = line.split("*/", 1)[1]
            in_block_comment = False
        if quote_delimiter:
            if quote_delimiter not in line:
                continue
            line = line.split(quote_delimiter, 1)[1]
            quote_delimiter = None
        if "/*" in line:
            before, after = line.split("/*", 1)
            if "*/" in after:
                line = before + after.split("*/", 1)[1]
            else:
                line = before
                in_block_comment = True
        if line.lstrip().startswith(("#", "//", "*")):
            continue
        for delimiter in ('"""', "'''"):
            if delimiter in line:
                before, after = line.split(delimiter, 1)
                if delimiter in after:
                    line = before + after.split(delimiter, 1)[1]
                else:
                    line = before
                    quote_delimiter = delimiter
        line = re.split(r"\s+(?:#|//)", line, maxsplit=1)[0].strip()
        if line:
            code_lines.append((line_number, line))
    return code_lines


def _read_model_sources(model: RepositoryModel) -> str:
    if not model.root_path:
        return ""
    root = Path(model.root_path).resolve()
    selected = []
    for file in model.files:
        relative = Path(file.path)
        name = relative.name.lower()
        parts = _parts(file.path)
        if set(parts) & _IGNORED_CONTEXT_AREAS:
            continue
        is_document = relative.suffix.lower() in _DOC_EXTENSIONS and (
            name.startswith("readme") or "architecture" in name or "design" in name or "docs" in parts
        )
        if is_document or _is_config_file(relative, file.kind) or file.kind in {"ci", "docker"}:
            if not relative.is_absolute() and ".." not in relative.parts:
                selected.append(relative.as_posix())
    texts = []
    for relative in sorted(set(selected))[:80]:
        try:
            path = (root / relative).resolve()
            path.relative_to(root)
            with path.open("rb") as source:
                texts.append(source.read(32_000).decode("utf-8", errors="replace"))
        except (OSError, ValueError):
            continue
        if sum(map(len, texts)) >= 200_000:
            break
    return "\n".join(texts)[:200_000]


def _read_relationship_sources(model: RepositoryModel) -> dict[str, str]:
    if not model.root_path:
        return {}
    root = Path(model.root_path).resolve()
    selected: list[str] = []
    for file in model.files:
        relative = Path(file.path)
        if relative.is_absolute() or ".." in relative.parts:
            continue
        parts = _parts(file.path)
        if set(parts) & _IGNORED_CONTEXT_AREAS:
            continue
        if file.kind == "source" and not set(parts) & _IGNORED_AREAS:
            selected.append(relative.as_posix())
            continue
        name = relative.name.lower()
        is_document = relative.suffix.lower() in _DOC_EXTENSIONS and (
            name.startswith("readme") or "architecture" in name or "design" in name or "docs" in parts
        )
        if is_document or _is_config_file(relative, file.kind) or file.kind in {"ci", "docker"}:
            selected.append(relative.as_posix())

    selected_paths = set(selected)
    kinds = {file.path: file.kind for file in model.files}
    priority = sorted(
        (path for path in selected_paths if
         (Path(path).name.lower().startswith("readme") and len(Path(path).parts) == 1)
         or path in model.entry_points
         or (len(Path(path).parts) == 1 and _is_config_file(Path(path), kinds[path]))),
        key=lambda path: (len(Path(path).parts), path),
    )
    public = sorted(
        (path for path in selected_paths - set(priority)
         if Path(path).name.lower() in {"__init__.py", "index.ts", "index.js", "lib.rs"}),
        key=lambda path: (len(Path(path).parts), path),
    )
    documentation = sorted(
        path for path in selected_paths - set(priority)
        if Path(path).suffix.lower() in _DOC_EXTENSIONS
    )
    priority = list(dict.fromkeys([*priority, *public[:12], *documentation[:10]]))
    remaining = set(selected) - set(priority)
    groups: dict[str, list[str]] = {}
    for path in sorted(remaining):
        groups.setdefault(str(Path(path).parent), []).append(path)
    ordered = priority[:]
    while groups:
        for directory in sorted(groups):
            ordered.append(groups[directory].pop(0))
            if not groups[directory]:
                del groups[directory]

    contents: dict[str, str] = {}
    total_bytes = 0
    candidates = ordered[:120]
    for index, relative in enumerate(candidates):
        if total_bytes >= 400_000:
            break
        remaining = 400_000 - total_bytes
        limit = min(24_000, remaining, max(1024, remaining // (len(candidates) - index)))
        try:
            path = (root / relative).resolve()
            path.relative_to(root)
            with path.open("rb") as source:
                data = source.read(limit)
        except (OSError, ValueError):
            continue
        contents[relative] = data.decode("utf-8", errors="replace")
        total_bytes += len(data)
    return contents


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
                "Groups paths named Model or Domain. These may contain business data or behavior; "
                "the names alone do not establish a shared domain layer.",
            )
        if folder in {"resourcemodel", "resourcemodels"}:
            return (
                "Resource Models", "persistence", "Data and Infrastructure",
                "Magento ResourceModel paths commonly contain persistence-related code; "
                "check the individual implementation.",
            )
        if folder in {"provider", "providers"}:
            return (
                "Provider Classes", "integration", "Data and Infrastructure",
                "Groups classes or paths named Provider, including possible configuration or UI data "
                "providers. Their individual responsibilities must be checked.",
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


def _public_imports(path: str, content: str) -> list[tuple[int, str]]:
    name = Path(path).name
    if name not in {"__init__.py", "index.js", "index.ts"}:
        return []
    imports = []
    for number, line in _source_code_lines(content):
        if name != "__init__.py" and not re.search(r"\bexport\b", line):
            continue
        for pattern, _ in _IMPORT_PATTERNS:
            match = pattern.search(line)
            if match:
                imports.append((number, match.group(1)))
                break
    return imports


def _discover_components(
    model: RepositoryModel, source_files: dict[str, str] | None = None, *, include_features: bool = True
) -> list[ArchitectureComponent]:
    framework = _framework_key(model)
    evidence: dict[str, set[str]] = {}
    definitions: dict[str, tuple[str, str, str, str]] = {}
    path_parts = {part for path in model.directories for part in _parts(path)}
    runtime_layout = bool(path_parts & {"runtime", "registries", "registry", "plugins", "skills", "artifacts"})

    for directory in model.directories:
        parts = _parts(directory)
        if not parts or set(parts) & _IGNORED_AREAS:
            continue
        for index, part in enumerate(parts):
            concept = _concept_for(part, framework, runtime_layout)
            if concept:
                name, component_type, subsystem, description = concept
                definitions[name] = (component_type, subsystem, description, part)
                evidence.setdefault(name, set()).add("/".join(directory.split("/")[:index + 1]))

    directories = set(model.directories)
    children_by_parent: dict[str, set[str]] = {}
    for directory in directories:
        parent, _, child = directory.rpartition("/")
        if parent:
            children_by_parent.setdefault(parent, set()).add(child.lower())
    for directory in sorted(directories) if include_features else []:
        parts = _parts(directory)
        if not parts or set(parts) & _IGNORED_AREAS:
            continue
        if _concept_for(parts[-1], framework, runtime_layout):
            continue
        children = children_by_parent.get(directory, set())
        layers = {"controller", "controllers", "service", "services", "repository", "repositories", "domain"}
        if len(children & layers) < 2:
            continue
        name = parts[-1].replace("_", " ").title()
        definitions[name] = (
            "feature", "Features", f"Groups the {name.lower()} application functionality.", parts[-1]
        )
        evidence.setdefault(name, set()).add(directory)

    for path, content in (source_files or {}).items():
        if not any(file.path == path and file.kind == "source" for file in model.files):
            continue
        module_concept = _concept_for_module(Path(path).stem, framework)
        if module_concept:
            name, component_type, subsystem, description = module_concept
            definitions[name] = (component_type, subsystem, description, Path(path).stem)
            evidence.setdefault(name, set()).add(path)
        source_lines = _source_code_lines(content)
        code = "\n".join(line for _, line in source_lines)
        for class_name in _CLASS_DECLARATION.findall(code):
            concept = _concept_for_class(class_name, framework)
            if concept:
                name, component_type, subsystem, description = concept
                definitions[name] = (component_type, subsystem, description, class_name)
                evidence.setdefault(name, set()).add(path)

    source_paths = {file.path for file in model.files if file.kind == "source"}
    for path, content in (source_files or {}).items():
        if path not in source_paths:
            continue
        for _, import_path in _public_imports(path, content):
            targets = _import_candidates(import_path, path, source_paths)
            if len(targets) != 1:
                continue
            target = targets[0]
            if any(
                target == location or target.startswith(location.rstrip("/") + "/")
                for locations in evidence.values() for location in locations
            ):
                continue
            stem = Path(target).stem
            if stem in {"__init__", "index", "lib"}:
                stem = Path(target).parent.name
            name = stem.replace("_", " ").replace("-", " ").title()
            if name:
                definitions[name] = ("module", "Application", f"Provides the public {name} functionality.", stem)
                evidence.setdefault(name, set()).add(target)

    if not evidence and model.entry_points:
        evidence["Application Entry Point"] = set(model.entry_points[:3])
        definitions["Application Entry Point"] = (
            "entry_point", "Application", "Starts or exposes the application.", "entry"
        )

    ids_by_name = {
        name: "component_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        for name in evidence
    }
    return [
        ArchitectureComponent(
            id=ids_by_name[name],
            name=name,
            type=definitions[name][0],
            description=definitions[name][2],
            responsibilities=[definitions[name][2]],
            evidence=sorted(evidence[name]),
            locations=sorted(evidence[name]),
        )
        for name in sorted(evidence)
    ]


def _component_owner(
    path: str, components: list[ArchitectureComponent]
) -> ArchitectureComponent | None:
    normalized_path = path.replace("\\", "/").strip("/")
    matches = [
        (0 if Path(evidence).suffix else 1, len(evidence), component)
        for component in components
        for evidence in component.locations
        if normalized_path == evidence.replace("\\", "/").strip("/")
        or normalized_path.startswith(evidence.replace("\\", "/").strip("/") + "/")
    ]
    if not matches:
        return None
    best_rank = max((directory_rank, length) for directory_rank, length, _ in matches)
    best = [
        component for directory_rank, length, component in matches
        if (directory_rank, length) == best_rank
    ]
    return best[0] if len(best) == 1 else None


def _source_owner(
    path: str, components: list[ArchitectureComponent]
) -> ArchitectureComponent | None:
    normalized_path = path.replace("\\", "/").strip("/")
    directory_matches = [
        (len(evidence), component)
        for component in components
        for evidence in component.locations
        if not Path(evidence).suffix
        and normalized_path.startswith(evidence.replace("\\", "/").strip("/") + "/")
    ]
    if directory_matches:
        best_length = max(length for length, _ in directory_matches)
        best = [component for length, component in directory_matches if length == best_length]
        if len(best) == 1:
            return best[0]
    module_concept = _concept_for_module(Path(path).stem)
    if module_concept:
        component = next(
            (item for item in components if item.name == module_concept[0]),
            None,
        )
        if component:
            return component
    return _component_owner(path, components)


def _component_aliases(component: ArchitectureComponent) -> list[str]:
    candidates = [component.name]
    for location in component.locations:
        path = Path(location)
        if not path.suffix:
            concept = _concept_for(path.name.lower(), None, False)
            if concept and concept[0] == component.name:
                candidates.append(location)
        else:
            concept = _concept_for_module(path.stem)
            if concept and concept[0] == component.name:
                candidates.append(location)
    aliases: set[str] = set()
    for candidate in candidates:
        value = Path(candidate).stem.replace("_", " ").replace("-", " ").lower()
        words = re.findall(r"[a-z0-9]+", value)
        if not words:
            continue
        aliases.add(" ".join(words))
        aliases.add("".join(words))
        if len(words) == 1:
            word = words[0]
            aliases.add(word)
            if word.endswith("ies"):
                aliases.add(word[:-3] + "y")
            elif word.endswith("s") and len(word) > 3:
                aliases.add(word[:-1])
    return sorted(aliases, key=lambda value: (-len(value), value))


def _alias_pattern(alias: str) -> str:
    return r"(?<!\w)" + re.escape(alias).replace(r"\ ", r"[\s_-]+") + r"(?!\w)"


def _import_candidates(import_path: str, source_path: str, source_paths: set[str]) -> list[str]:
    if import_path.startswith("./") or import_path.startswith("../"):
        module_path = posixpath.normpath(posixpath.join(posixpath.dirname(source_path), import_path))
        if Path(module_path).suffix in {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}:
            module_path = str(Path(module_path).with_suffix(""))
        relative = True
    elif import_path.startswith("."):
        prefix_length = len(import_path) - len(import_path.lstrip("."))
        base = posixpath.dirname(source_path)
        for _ in range(max(prefix_length - 1, 0)):
            base = posixpath.dirname(base)
        module_path = posixpath.normpath(posixpath.join(base, import_path[prefix_length:].replace(".", "/")))
        relative = True
    else:
        module_path = import_path.replace(".", "/").replace("\\", "/")
        relative = False
    module_path = module_path.strip("/")
    candidates: list[tuple[int, str]] = []
    for path in source_paths:
        path_without_suffix = str(Path(path).with_suffix("")).replace("\\", "/")
        if path_without_suffix.endswith(("/__init__", "/index")):
            path_without_suffix = path_without_suffix.rsplit("/", 1)[0]
        if path_without_suffix == module_path:
            candidates.append((len(module_path), path))
        elif not relative and (
            path_without_suffix.endswith("/" + module_path)
            or ("/" in path_without_suffix and module_path.endswith("/" + path_without_suffix))
        ):
            candidates.append((min(len(path_without_suffix), len(module_path)), path))
    if not candidates:
        return []
    best_score = max(score for score, _ in candidates)
    return sorted(path for score, path in candidates if score == best_score)


def _target_component(
    import_path: str, source_path: str, components: list[ArchitectureComponent],
    source_paths: set[str],
) -> ArchitectureComponent | None:
    owners = {
        component.id: component
        for path in _import_candidates(import_path, source_path, source_paths)
        for component in [_source_owner(path, components)]
        if component is not None
    }
    return next(iter(owners.values())) if len(owners) == 1 else None


def _add_relationship(
    found: dict[tuple[str, str, str], ArchitectureRelationship],
    source: ArchitectureComponent,
    target: ArchitectureComponent,
    relation_type: str,
    confidence: float,
    evidence: str,
    description: str,
) -> None:
    if source.id == target.id:
        return
    key = (source.id, target.id, relation_type)
    relationship = found.get(key)
    if relationship is None:
        found[key] = ArchitectureRelationship(
            source=source.id,
            target=target.id,
            type=relation_type,
            description=description,
            confidence=confidence,
            evidence=[evidence],
        )
        return
    if confidence > relationship.confidence:
        relationship.confidence = confidence
        relationship.description = description
    if evidence not in relationship.evidence:
        relationship.evidence.append(evidence)


def _discover_relationships(
    model: RepositoryModel,
    components: list[ArchitectureComponent],
    framework: str | None,
    files: dict[str, str],
) -> list[ArchitectureRelationship]:
    found: dict[tuple[str, str, str], ArchitectureRelationship] = {}
    names = {component.name: component for component in components}
    runtime_names = {
        "Registries", "Plugins", "Skills", "Artifacts", "Providers",
        "Skill Result", "Model Requests", "Model Responses",
    }
    rule_set = framework or ("runtime" if runtime_names & names.keys() else "backend")
    for source_name, target_name, relation_type in _RELATION_RULES.get(rule_set, []):
        source, target = names.get(source_name), names.get(target_name)
        if source and target:
            _add_relationship(
                found,
                source,
                target,
                relation_type,
                0.55,
                f"layout convention: {source.name} -> {target.name}",
                f"Inferred from {rule_set} framework/layout conventions.",
            )

    class_owners: dict[str, dict[str, ArchitectureComponent]] = {}
    components_by_name = {component.name: component for component in components}
    source_paths = {
        file.path for file in model.files
        if file.kind == "source"
    }
    for path, content in files.items():
        if path not in source_paths:
            continue
        owner = _source_owner(path, components)
        if owner is None:
            continue
        source_lines = _source_code_lines(content)
        code = "\n".join(line for _, line in source_lines)
        for class_name in _CLASS_DECLARATION.findall(code):
            class_concept = _concept_for_class(class_name, framework)
            symbol_owner = (
                components_by_name.get(class_concept[0])
                if class_concept else None
            ) or owner
            class_owners.setdefault(class_name, {})[symbol_owner.id] = symbol_owner

        for line_number, line in source_lines:
            for pattern, relation_type in _IMPORT_PATTERNS:
                match = pattern.search(line)
                if not match:
                    continue
                imported_path = match.group(1)
                target = _target_component(imported_path, path, components, source_paths)
                if target:
                    _add_relationship(
                        found,
                        owner,
                        target,
                        relation_type,
                        0.9,
                        f"{path}:{line_number} (import {imported_path})",
                        "Lexically detected an import or re-export of a local component module.",
                    )
                break

    for path, content in files.items():
        if path not in source_paths:
            continue
        owner = _source_owner(path, components)
        if owner is None:
            continue
        for line_number, line in _source_code_lines(content):
            if re.match(r"\s*(?:from\s+\S+\s+import|import\s+)", line):
                continue
            for class_name, targets in class_owners.items():
                if len(targets) != 1:
                    continue
                if not re.search(rf"\b{re.escape(class_name)}\b", line):
                    continue
                for target in targets.values():
                    if target.id == owner.id:
                        continue
                    if re.search(r"\b(?:register|bind|provide|providers|inject)\b", line, re.I):
                        relation_type, confidence = "registers", 0.88
                    elif re.search(r"\bextends\b", line, re.I):
                        relation_type, confidence = "extends", 0.86
                    elif re.search(r"\bimplements\b", line, re.I):
                        relation_type, confidence = "implements", 0.86
                    elif re.search(rf"\bnew\s+{re.escape(class_name)}\b|\b{re.escape(class_name)}\s*\(", line):
                        relation_type, confidence = "constructs", 0.84
                    elif (
                        re.search(rf"->\s*{re.escape(class_name)}\b", line)
                        and (concept := _concept_for_class(class_name, framework))
                        and concept[0] == target.name
                    ):
                        relation_type, confidence = "returns", 0.82
                    elif re.search(rf"[:<]\s*{re.escape(class_name)}\b", line):
                        relation_type, confidence = "depends on", 0.78
                    else:
                        relation_type, confidence = "references", 0.65
                    _add_relationship(
                        found,
                        owner,
                        target,
                        relation_type,
                        confidence,
                        f"{path}:{line_number} (reference to {class_name})",
                        "Lexically detected a cross-component type or class reference.",
                    )

    for path, content in files.items():
        if path in source_paths or Path(path).suffix.lower() not in {".yaml", ".yml"}:
            continue
        owner = _component_owner(path, components)
        if owner is None:
            continue
        registration_indent: int | None = None
        for line_number, line in enumerate(content.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip())
            if registration_indent is not None and indent <= registration_indent:
                registration_indent = None
            if re.match(r"^(?:providers|bindings|registrations)\s*:", stripped, re.I):
                registration_indent = indent
            elif registration_indent is None:
                continue
            for class_name, targets in class_owners.items():
                if len(targets) == 1 and re.search(rf"\b{re.escape(class_name)}\b", stripped):
                    target = next(iter(targets.values()))
                    _add_relationship(
                        found, owner, target, "registers", 0.75,
                        f"{path}:{line_number} (registration of {class_name})",
                        "A configuration registration names a component class.",
                    )

    alias_patterns = {
        component.id: [re.compile(_alias_pattern(alias), re.I) for alias in _component_aliases(component)]
        for component in components
    }
    for path, content in files.items():
        if not any(
            file.path == path and (file.kind != "source" or Path(path).suffix.lower() in _DOC_EXTENSIONS)
            for file in model.files
        ):
            continue
        for line_number, line in enumerate(content.splitlines(), 1):
            if (
                Path(path).suffix.lower() in _DOC_EXTENSIONS
                and "Tools" in names and "Retrieval" in names
                and re.search(r"\b(?:rag|retrieval)(?:\s+operation)?\s+as\s+(?:an?\s+)?(?:regular\s+)?tool\b", line, re.I)
                and not re.search(r"\b(?:no|not|never|without)\b", line, re.I)
            ):
                _add_relationship(
                    found, names["Tools"], names["Retrieval"], "can expose as a tool",
                    0.82, f"{path}:{line_number} (documented optional retrieval tool)",
                    "Documentation describes retrieval as a tool; its use is optional.",
                )
            for sentence in re.split(r"(?<=[.!?;])\s+", line):
                if not any(re.search(rf"\b{verb}\b", sentence, re.I) for verb in _RELATION_WORDS):
                    continue
                mentions = []
                for component in components:
                    for pattern in alias_patterns[component.id]:
                        match = pattern.search(sentence)
                        if match:
                            mentions.append((component, match))
                            break
                for source, source_match in mentions:
                    for target, target_match in mentions:
                        if source.id == target.id:
                            continue
                        if target_match.start() <= source_match.end():
                            continue
                        relation_text = sentence[source_match.end():target_match.start()].lower()
                        relation_type = next(
                            (relation for verb, relation in _RELATION_WORDS.items() if re.search(rf"\b{verb}\b", relation_text)),
                            None,
                        )
                        if relation_type:
                            _add_relationship(
                                found,
                                source,
                                target,
                                relation_type,
                                0.82,
                                f"{path}:{line_number} (documented relationship)",
                                "Explicit relationship described in repository documentation/configuration.",
                            )

    for component in components:
        component.relationships.clear()
    relationships = sorted(
        found.values(),
        key=lambda item: (-item.confidence, item.source, item.target, item.type),
    )
    for relation in relationships:
        source = next(component for component in components if component.id == relation.source)
        source.relationships.append({
            "target": relation.target,
            "type": relation.type,
            "confidence": relation.confidence,
            "evidence": relation.evidence,
        })
    return relationships


def _subsystems(components: list[ArchitectureComponent]) -> list[ArchitectureSubsystem]:
    groups: dict[str, list[str]] = {}
    subsystem_by_component = {
        "API Layer": "Presentation",
        "Routes": "Presentation",
        "Pages": "Presentation",
        "Dashboard": "Presentation",
        "Visualizations": "Presentation",
        "Components": "Presentation",
        "Hooks": "Presentation",
        "Controllers": "Application",
        "Services": "Application",
        "Middleware": "Application",
        "State Management": "Application",
        "Modules": "Application",
        "Guards": "Application",
        "Interceptors": "Application",
        "Domain Layer": "Domain",
        "Models and Domain Code": "Domain",
        "Models": "Domain",
        "Persistence Layer": "Data and Infrastructure",
        "Resource Models": "Data and Infrastructure",
        "Infrastructure Layer": "Data and Infrastructure",
        "API Client Layer": "Data and Infrastructure",
        "Providers": "Data and Infrastructure",
        "Provider Classes": "Data and Infrastructure",
        "Runtime": "Runtime and Extensions",
        "Registries": "Runtime and Extensions",
        "Plugins": "Runtime and Extensions",
        "Observers": "Runtime and Extensions",
        "Skills": "Runtime and Extensions",
        "Artifacts": "Runtime and Extensions",
        "Skill Result": "Runtime and Extensions",
        "Model Requests": "Integrations",
        "Model Responses": "Integrations",
        "Repository Scanner": "Repository Processing",
        "Analyzers": "Repository Processing",
        "Agents": "Runtime",
        "Model Backends": "Integrations",
        "Tools": "Runtime",
        "Retrieval": "Data and Infrastructure",
        "MCP Integration": "Integrations",
    }
    descriptions = {
        "Presentation": "User-facing interface and request entry layers.",
        "Application": "Application workflows and request processing.",
        "Domain": "Core business rules and domain concepts.",
        "Data and Infrastructure": "Persistence and external platform integrations.",
        "Runtime and Extensions": "Runtime registration and extensible capabilities.",
        "Integrations": "Requests and responses exchanged with external model providers.",
        "Repository Processing": "Repository inventory and analysis capabilities.",
        "Runtime": "Application execution and extensible tools.",
        "Features": "Business capabilities grouped by their implementation boundaries.",
    }
    for component in components:
        subsystem = subsystem_by_component.get(
            component.name, "Features" if component.type == "feature" else "Application"
        )
        groups.setdefault(subsystem, []).append(component.id)
    return [
        ArchitectureSubsystem(
            id="subsystem_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            name=name,
            description=descriptions.get(name, "Related application components."),
            components=member_ids,
        )
        for name, member_ids in groups.items()
    ]


def _layers(components: list[ArchitectureComponent]) -> list[ArchitectureSubsystem]:
    layer_types = {
        "interface": "Presentation Layer", "routing": "Presentation Layer",
        "presentation": "Presentation Layer",
        "application": "Application Layer", "request_pipeline": "Application Layer",
        "state": "Application Layer", "feature": "Application Layer", "module": "Application Layer",
        "domain": "Domain Layer",
        "runtime": "Runtime Layer", "agent": "Agent Layer", "extension": "Runtime Layer",
        "registry": "Runtime Layer", "scanner": "Application Layer", "analysis": "Application Layer",
        "persistence": "Persistence Layer", "retrieval": "Retrieval Layer",
        "infrastructure": "Infrastructure Layer", "integration": "Integration Layer",
        "request": "Integration Layer", "response": "Integration Layer",
        "output": "Supporting Layer", "result": "Supporting Layer",
        "entry_point": "Application Layer",
    }
    groups: dict[str, list[str]] = {}
    by_id = {component.id: component for component in components}
    for component in components:
        layer = (
            "Models and Domain Code" if component.name == "Models and Domain Code"
            else layer_types.get(component.type)
        )
        if layer:
            groups.setdefault(layer, []).append(component.id)
    return [
        ArchitectureSubsystem(
            id="layer_" + re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"),
            name=name,
            description=" ".join(
                f"{by_id[item].name}: {by_id[item].description}"
                + (f" Example: {by_id[item].locations[0]}." if by_id[item].locations else "")
                for item in ids
            ),
            components=ids,
        )
        for name, ids in groups.items()
    ]


def _system_description(
    model: RepositoryModel, files: dict[str, str],
    components: list[ArchitectureComponent], relevance: RepositoryRelevance,
) -> str:
    if _framework(model, "magento"):
        areas = relevance.areas
        modules = [area for area in areas if area.kind == "custom module"]
        themes = [area for area in areas if area.kind == "theme"]
        facts = ["Magento was detected from repository metadata."]
        readme = model.readme_summary.strip()
        if readme and not re.search(
            r"\b(?:repository|project)\s+contains\s+(?:a|an)\s+(?:sample|example)\s+magento\b",
            readme, re.IGNORECASE,
        ):
            facts.append(f"README description: {readme}")
        if modules:
            facts.append(
                f"The scan found {len(modules)} module {'directory' if len(modules) == 1 else 'directories'} under app/code; "
                "examples include " + ", ".join(area.path for area in modules[:3]) + "."
            )
        if themes:
            facts.append(
                f"The scan found {len(themes)} theme {'directory' if len(themes) == 1 else 'directories'} under app/design, including "
                + ", ".join(area.path for area in themes[:2]) + "."
            )
        relevant_components = [
            component for component in components
            if component.name in {"Controllers", "Models and Domain Code", "Resource Models", "Plugins", "Observers", "Provider Classes"}
        ]
        if relevant_components:
            facts.append(
                "Detected path and class conventions include "
                + ", ".join(component.name for component in relevant_components) + ". "
                "These are cross-module groups, not verified runtime layers."
            )
        facts.append("The repository layout does not establish deployment status or production behavior.")
        return " ".join(facts)
    readmes = [
        (path, text) for path, text in files.items()
        if Path(path).name.lower().startswith("readme")
        and len(Path(path).parts) == 1
    ]
    title = ""
    if readmes:
        for line in readmes[0][1].splitlines():
            match = re.match(r"^#\s+(.+)$", line.strip())
            if match:
                heading = match.group(1).strip()
                parts = re.split(r"\s+(?:—|–|-)\s+|:\s+", heading, maxsplit=1)
                if len(parts) == 2 and len(parts[1].strip()) >= 8:
                    title = parts[1].strip().rstrip(".")
                    title = title[0].upper() + title[1:] + "."
                break
    description = model.readme_summary.strip()
    if title and title.casefold().rstrip(".") not in description.casefold():
        return " ".join(part for part in (title, description) if part)
    return description or title or f"{model.repository_name} repository architecture."


def _rank_components(
    model: RepositoryModel,
    components: list[ArchitectureComponent],
    relationships: list[ArchitectureRelationship],
    files: dict[str, str],
    entry_points: list[str],
) -> None:
    kinds = {file.path: file.kind for file in model.files}
    sources: dict[str, dict[str, list[str]]] = {
        component.id: {} for component in components
    }

    def add(component: ArchitectureComponent, category: str, evidence: str) -> None:
        group = sources[component.id].setdefault(category, [])
        if evidence not in group and len(group) < 3:
            group.append(evidence)

    framework = _framework_key(model)
    aliases = {
        component.id: [re.compile(_alias_pattern(alias), re.I) for alias in _component_aliases(component)]
        for component in components
    }
    for component in components:
        for path in component.locations:
            category = "source" if kinds.get(path) == "source" else "structure"
            add(component, category, f"{path} ({category})")
            if path in entry_points:
                add(component, "entry_point", f"{path} (entry point)")
        concepts = (
            _concept_for(part, framework, False)
            for path in component.locations for part in _parts(path)
        )
        if framework and any(concept and concept[0] == component.name for concept in concepts):
            add(component, "framework", f"{framework} framework convention")

    source_paths = {file.path for file in model.files if file.kind == "source"}
    for path, content in files.items():
        name = Path(path).name.lower()
        if kinds.get(path) == "source":
            for number, import_path in _public_imports(path, content):
                target = _target_component(import_path, path, components, source_paths)
                if target:
                    add(target, "public_api", f"{path}:{number} (public API export)")
            continue
        is_readme = name.startswith("readme")
        is_doc = Path(path).suffix.lower() in _DOC_EXTENSIONS
        is_config = _is_config_file(Path(path), kinds.get(path, ""))
        if not (is_doc or is_config):
            continue
        lead = is_readme and len(Path(path).parts) == 1
        for number, line in enumerate(content.splitlines(), 1):
            if lead and (re.match(r"^##\s+", line) or number > 40):
                lead = False
            category = "readme_lead" if lead else "readme" if is_readme else "documentation" if is_doc else "configuration"
            for component in components:
                if any(pattern.search(line) for pattern in aliases[component.id]):
                    add(component, category, f"{path}:{number} ({category.replace('_', ' ')})")

    by_id = {component.id: component for component in components}
    for relationship in relationships:
        for location in relationship.evidence:
            if location.startswith("layout convention:"):
                continue
            category = "reference"
            for component_id in (relationship.source, relationship.target):
                add(by_id[component_id], category, location)
            path = location.split(":", 1)[0]
            if path in entry_points:
                add(by_id[relationship.target], "entry_point", f"{location} (entry point reference)")

    confidence_weights = {
        "structure": 0.30, "source": 0.28, "framework": 0.10,
        "readme_lead": 0.18, "readme": 0.08, "documentation": 0.12,
        "public_api": 0.18, "configuration": 0.10, "reference": 0.15,
        "entry_point": 0.15,
    }
    relevance_weights = {
        "structure": 0.05, "source": 0.08, "framework": 0.05,
        "readme_lead": 0.35, "readme": 0.12, "documentation": 0.12,
        "public_api": 0.20, "configuration": 0.08, "reference": 0.15,
        "entry_point": 0.25,
    }
    for component in components:
        evidence = sources[component.id]
        component.confidence = round(min(0.98, sum(confidence_weights[key] for key in evidence)), 2)
        component.relevance = round(min(1.0, sum(relevance_weights[key] for key in evidence)), 2)
        component.evidence = [
            item for category in confidence_weights for item in evidence.get(category, [])
        ]
    components.sort(key=lambda component: (-component.relevance, -component.confidence, component.name))


def _score_significance(
    components: list[ArchitectureComponent],
    relationships: list[ArchitectureRelationship],
    flows: list[dict],
) -> None:
    by_id = {component.id: component for component in components}
    neighbors: dict[str, set[str]] = {component.id: set() for component in components}
    incoming_major: dict[str, set[str]] = {component.id: set() for component in components}
    for relationship in relationships:
        if all(item.startswith("layout convention:") for item in relationship.evidence):
            continue
        neighbors[relationship.source].add(relationship.target)
        neighbors[relationship.target].add(relationship.source)
        if by_id[relationship.source].relevance >= 0.4:
            incoming_major[relationship.target].add(relationship.source)
    flow_ids = {
        component_id
        for flow in flows for path in flow["paths"] for component_id in path["component_ids"]
    }
    for component in components:
        component.significance = round(min(
            1.0,
            0.72 * component.relevance
            + min(0.12, 0.03 * len(neighbors[component.id]))
            + min(0.09, 0.03 * len(incoming_major[component.id]))
            + (0.07 if component.id in flow_ids else 0.0),
        ), 2)
    components.sort(key=lambda component: (-component.significance, -component.confidence, component.name))


def _significance_label(component: ArchitectureComponent) -> str:
    if component.significance >= 0.55:
        return "High"
    if component.significance >= 0.20:
        return "Medium"
    return "Low"


def _entry_points(
    model: RepositoryModel, source_text: str, files: dict[str, str] | None = None
) -> list[str]:
    def usable(path: str) -> bool:
        return not set(_parts(path)) & _IGNORED_AREAS

    entries = [path for path in model.entry_points if usable(path)]
    known = {Path(file.path).as_posix() for file in model.files if usable(file.path)}
    if _framework(model, "magento"):
        entries.extend(path for path in ("pub/index.php", "bin/magento", "index.php") if path in known and path not in entries)
    for path in sorted(known):
        if Path(path).name.lower() in {
            "main.py", "app.py", "server.py", "cli.py", "manage.py",
            "artisan", "index.js", "index.ts", "main.go", "main.rs", "__main__.py",
        } and path not in entries:
            entries.append(path)
    for path in re.findall(r"\bpython(?:3)?\s+([\w./-]+\.py)\b", source_text, re.IGNORECASE):
        if path in known and path not in entries:
            entries.append(path)
    if not entries:
        public_modules = [
            path for path, content in (files or {}).items()
            if _public_imports(path, content)
        ]
        if public_modules:
            depth = min(len(Path(path).parts) for path in public_modules)
            entries.extend(sorted(path for path in public_modules if len(Path(path).parts) == depth))
    return entries[:15]


def _external_facts(model: RepositoryModel, files: dict[str, str]) -> tuple[list[str], list[str]]:
    signals = [
        dependency.name for dependency in model.dependencies
        if dependency.scope == "runtime"
        and not set(_parts(dependency.source)) & _IGNORED_AREAS
        and not re.search(r"(?:^|[._-])(?:example|sample|test|dev|development|local|optional)(?:[._-]|$)", Path(dependency.source).name, re.I)
    ]
    kinds = {file.path: file.kind for file in model.files}
    for path, content in files.items():
        name = Path(path).name.lower()
        if set(_parts(path)) & _IGNORED_AREAS or re.search(
            r"(?:^|[._-])(?:example|sample|test|dev|development|local|optional)(?:[._-]|$)", name
        ):
            continue
        if kinds.get(path) == "source":
            original_lines = content.splitlines()
            signals.extend(
                line for number, line in _source_code_lines(content)
                if re.search(r"^\s*(?:from|import|using|use)\b|\b(?:import|require)\s*\(", line)
                and not original_lines[number - 1][:1].isspace()
            )
            continue
        if name in {"compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}:
            preamble = "\n".join(line for line in content.splitlines()[:5] if line.lstrip().startswith("#"))
            if re.search(r"\b(?:development|dev|example|sample|optional)\b", preamble, re.I):
                continue
            service_blocks: list[list[str]] = []
            in_services = False
            services_indent = -1
            service_indent: int | None = None
            for line in content.splitlines():
                if not line.strip() or line.lstrip().startswith("#"):
                    continue
                indent = len(line) - len(line.lstrip())
                if in_services and indent <= services_indent:
                    in_services = False
                if re.match(r"^\s*services\s*:\s*(?:#.*)?$", line):
                    in_services, services_indent, service_indent = True, indent, None
                    continue
                if not in_services:
                    continue
                if service_indent is None:
                    service_indent = indent
                if indent == service_indent and re.match(r"^\s*[\w.-]+\s*:", line):
                    service_blocks.append([line])
                elif service_blocks:
                    service_blocks[-1].append(line)
            for block in service_blocks:
                if not any(re.match(r"^\s*profiles\s*:", line) for line in block):
                    signals.append(block[0])
                    signals.extend(line for line in block[1:] if re.match(r"^\s*image\s*:", line))
            continue
        if not re.match(r"^(?:application|appsettings|config|settings|\.env)(?:[._-]|$)", name):
            continue
        config_lines = content.splitlines()
        disabled_lines: set[int] = set()
        for index, line in enumerate(config_lines):
            if not re.match(r"^\s*(?:enabled\s*:\s*false|optional\s*:\s*true)\s*(?:#.*)?$", line, re.I):
                continue
            indent = len(line) - len(line.lstrip())
            for start in range(index - 1, -1, -1):
                previous = config_lines[start]
                parent_indent = len(previous) - len(previous.lstrip())
                if parent_indent < indent and re.match(r"^\s*[\w.-]+\s*:\s*(?:#.*)?$", previous):
                    end = start + 1
                    while end < len(config_lines):
                        candidate = config_lines[end]
                        if candidate.strip() and not candidate.lstrip().startswith("#") and len(candidate) - len(candidate.lstrip()) <= parent_indent:
                            break
                        end += 1
                    disabled_lines.update(range(start, end))
                    break
        signals.extend(
            line for index, line in enumerate(config_lines)
            if index not in disabled_lines
            if not line.lstrip().startswith(("#", "//"))
            and re.search(r"(?:database|datasource|redis|cache|broker|queue|url|uri|endpoint|host|provider)", line, re.I)
            and re.search(r"[:=]", line)
            and not re.search(r"\b(?:optional|example|sample)\b", line, re.I)
        )
    source = "\n".join(signals).lower()
    stores, services = set(), set()
    for term, (name, kind) in _SERVICE_TERMS.items():
        if not re.search(rf"\b{re.escape(term)}\b", source):
            continue
        fact = f"{name} ({kind})"
        (stores if "database" in kind or kind == "cache" else services).add(fact)
    return sorted(services), sorted(stores)


def _execution_flows(
    components: list[ArchitectureComponent],
    relationships: list[ArchitectureRelationship],
    entry_points: list[str],
    external_dependencies: list[str],
    public_entries: list[str],
    *,
    require_execution_evidence: bool = False,
) -> list[dict]:
    if not relationships:
        return []
    flow_types = {
        "executes", "invokes", "produces", "handles", "registers",
        "registers with", "returns", "contains", "uses",
        "dispatches to", "delegates to", "routes to", "creates", "populates",
        "renders", "reads and updates", "requests data through", "applies",
        "reads and writes through", "passes through", "authorizes", "wraps",
        "discovers through", "makes available", "tracks",
    }
    outgoing: dict[str, list[ArchitectureRelationship]] = {}
    incoming = set()
    for relation in relationships:
        if relation.type == "can expose as a tool":
            continue
        if require_execution_evidence and relation.type not in {
            "executes", "invokes", "dispatches to", "delegates to", "routes to",
        }:
            continue
        outgoing.setdefault(relation.source, []).append(relation)
        incoming.add(relation.target)
    roots = [
        component.id for component in components
        if component.id not in incoming and outgoing.get(component.id)
    ]
    entry_owners = [
        owner.id for entry in entry_points
        for owner in [_source_owner(entry, components)]
        if owner and outgoing.get(owner.id)
    ]
    if not entry_owners:
        entry_owners = [component_id for component_id in public_entries if outgoing.get(component_id)]
    if entry_owners:
        roots = list(dict.fromkeys(entry_owners))
    if not roots:
        roots = [component.id for component in components if outgoing.get(component.id)]
    by_id = {component.id: component for component in components}
    roots.sort(key=lambda item: (-by_id[item].significance, item))
    paths: list[tuple[list[str], list[ArchitectureRelationship]]] = []

    def walk(
        component_id: str,
        ids: list[str],
        relations: list[ArchitectureRelationship],
        root_paths: list[tuple[list[str], list[ArchitectureRelationship]]],
    ) -> None:
        if len(root_paths) >= 64:
            return
        if relations:
            root_paths.append((ids, relations))
        if len(ids) >= 8:
            return
        available_edges = [
            edge for edge in outgoing.get(component_id, []) if edge.target not in ids
        ]
        best_edges: dict[str, ArchitectureRelationship] = {}
        for edge in available_edges:
            existing = best_edges.get(edge.target)
            rank = (edge.type in flow_types, edge.confidence)
            if existing is None or rank > (existing.type in flow_types, existing.confidence):
                best_edges[edge.target] = edge
        next_edges = sorted(
            best_edges.values(),
            key=lambda edge: (edge.type not in flow_types, -edge.confidence, edge.target),
        )
        for edge in next_edges:
            walk(edge.target, [*ids, edge.target], [*relations, edge], root_paths)

    for root in roots[:20]:
        root_paths: list[tuple[list[str], list[ArchitectureRelationship]]] = []
        walk(root, [root], [], root_paths)
        paths.extend(root_paths)
    if not paths:
        return []
    component_order = {component.id: component.name for component in components}

    def path_score(path_item: tuple[list[str], list[ArchitectureRelationship]]) -> tuple[float, int, tuple[str, ...]]:
        path, path_relationships = path_item
        score = sum(
            relation.confidence * (1.0 if relation.type in flow_types else 0.7)
            for relation in path_relationships
        )
        return (
            score / len(path_relationships)
            + sum(by_id[item].significance for item in path) / len(path)
            + 0.08 * min(sum(relation.type in flow_types for relation in path_relationships), 4)
            + 0.12 * min(len(path_relationships), 4),
            len(path_relationships),
            tuple(component_order.get(component_id, "") for component_id in path),
        )

    path, path_relationships = max(
        paths,
        key=path_score,
    )
    flow_paths = [{
        "component_ids": path,
        "relationship_types": [relation.type for relation in path_relationships],
        "relationship_confidences": [relation.confidence for relation in path_relationships],
        "relationship_evidence": [relation.evidence for relation in path_relationships],
    }]
    for relation in relationships:
        if (
            relation.type == "can expose as a tool"
            and relation.source in path
            and relation.target not in path
        ):
            flow_paths.append({
                "component_ids": [relation.source, relation.target],
                "relationship_types": [relation.type],
                "relationship_confidences": [relation.confidence],
                "relationship_evidence": [relation.evidence],
                "kind": "optional",
            })
    return [{
        "name": "Likely conceptual flow",
        "paths": flow_paths,
        "entry_points": entry_points,
        "external_dependencies": external_dependencies,
    }]


def extract_architecture(model: RepositoryModel) -> ArchitectureModel:
    """Discover architectural concepts and relationships from a RepositoryModel."""
    relevance = analyze_relevance(model)
    model = relevant_model(model)
    source_text = _read_model_sources(model)
    relationship_sources = _read_relationship_sources(model)
    runtime_entry_points = _entry_points(model, source_text)
    entry_points = _entry_points(model, source_text, relationship_sources)
    framework = _framework_key(model)
    components = _discover_components(model, relationship_sources, include_features=len(relevance.areas) <= 12)
    relationships = _discover_relationships(
        model, components, framework, relationship_sources
    )
    _rank_components(model, components, relationships, relationship_sources, entry_points)
    _score_significance(components, relationships, [])
    external_dependencies, data_stores = _external_facts(model, relationship_sources)
    source_paths = {file.path for file in model.files if file.kind == "source"}
    public_api_paths = [
        path for path, content in relationship_sources.items()
        if Path(path).name == "__init__.py"
        and not set(_parts(path)) & _IGNORED_AREAS
        and any(
            _import_candidates(import_path, path, source_paths)
            for _, import_path in _public_imports(path, content)
        )
    ]
    if public_api_paths:
        min_depth = min(len(Path(path).parts) for path in public_api_paths)
        public_api_paths = sorted(
            path for path in public_api_paths if len(Path(path).parts) == min_depth
        )[:3]
    public_entries = [
        target.id for entry in entry_points
        for _, import_path in _public_imports(entry, relationship_sources.get(entry, ""))
        for target in [_target_component(import_path, entry, components, source_paths)]
        if target is not None
    ]
    flow = _execution_flows(
        components, relationships, entry_points, external_dependencies, public_entries,
        require_execution_evidence=framework == "magento",
    )
    _score_significance(components, relationships, flow)
    deployment = []
    file_names = {Path(file.path).name.lower() for file in model.files}
    if file_names & {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
        deployment.append("Container configuration is present.")
    if model.ci_cd_files:
        deployment.append("CI/CD configuration is present.")
    guidance = [
        sentence for key, sentence in _FRAMEWORK_GUIDANCE.items()
        if _framework(model, key)
    ]
    return ArchitectureModel(
        system_name=model.repository_name,
        system_type=_system_type(model, source_text.lower(), runtime_entry_points),
        description=_system_description(model, relationship_sources, components, relevance),
        components=components,
        subsystems=_subsystems(components),
        layers=_layers(components),
        responsibilities=list(dict.fromkeys(
            responsibility
            for component in components
            for responsibility in component.responsibilities
        )),
        relationships=relationships,
        entry_points=entry_points,
        public_api_entry_points=public_api_paths,
        external_dependencies=external_dependencies,
        data_stores=data_stores,
        execution_flows=flow,
        detected_patterns=list(model.detected_patterns),
        recommended_learning_path=list(dict.fromkeys([
            *[path for path in model.onboarding_docs if Path(path).name.lower().startswith("readme")],
            *entry_points,
            *[area.path for area in relevance.areas],
            *[file for component in components for file in component.locations[:1]],
        ]))[:10],
        framework_architecture=guidance,
        deployment_architecture=deployment,
        frameworks=list(model.frameworks),
        repository_relevance=relevance,
    )


def _mermaid_text(text: str) -> str:
    return text.replace(";", "#59;").replace('"', "#quot;").replace("\n", " ").replace("|", "#124;")


def _diagram_relationships(
    relationships: list[ArchitectureRelationship],
) -> list[ArchitectureRelationship]:
    priority = {
        "executes": 10,
        "produces": 10,
        "contains": 10,
        "tracks": 10,
        "handles": 9,
        "returns": 9,
        "delegates to": 9,
        "dispatches to": 9,
        "routes to": 9,
        "invokes": 9,
        "registers with": 8,
        "registers": 8,
        "makes available": 8,
        "uses": 7,
        "imports": 6,
        "re-exports": 6,
        "constructs": 5,
        "depends on": 4,
        "extends": 4,
        "implements": 4,
        "references": 3,
    }
    primary: dict[tuple[str, str], ArchitectureRelationship] = {}
    for relation in relationships:
        key = (relation.source, relation.target)
        current = primary.get(key)
        relation_rank = (relation.confidence, priority.get(relation.type, 0))
        current_rank = (
            current.confidence,
            priority.get(current.type, 0),
        ) if current else (-1, -1.0)
        if relation_rank > current_rank:
            primary[key] = relation
    return sorted(primary.values(), key=lambda item: (item.source, item.target))


def _needs_aggregation(model: ArchitectureModel) -> bool:
    return bool(model.repository_relevance.areas) or len(model.components) + len(model.subsystems) + 1 > 15


def _aggregated_graph(model: ArchitectureModel, detail: bool) -> str:
    groups: dict[str, list[str]] = {}
    labels = {
        "custom module": "Custom Modules",
        "workspace module": "Workspace Modules",
        "business area": "Business Areas",
        "theme": "Storefront Themes",
    }
    for area in model.repository_relevance.areas:
        groups.setdefault(labels[area.kind], []).append(f"{area.name} ({area.path})")
    if not groups and detail:
        components = {component.id: component.name for component in model.components}
        for subsystem in model.subsystems:
            groups[subsystem.name] = [components[item] for item in subsystem.components]
    elif not detail:
        for subsystem in model.subsystems:
            groups.setdefault(subsystem.name, [])
    if not detail and model.frameworks:
        groups.setdefault("Frameworks: " + ", ".join(model.frameworks), [])
    if not detail and model.repository_relevance.paths.get("low"):
        groups.setdefault("Vendor and third-party code", [])
    if not detail and model.repository_relevance.paths.get("medium") and any(
        "infra" in path.lower() or "deploy" in path.lower() or "config" in path.lower()
        for path in model.repository_relevance.paths["medium"]
    ):
        groups.setdefault("Configuration and infrastructure", [])

    ordered = list(groups.items())
    omitted_groups = max(0, len(ordered) - 13)
    if omitted_groups:
        ordered = ordered[:13] + [(f"Other groups ({omitted_groups})", [])]
    lines = ["flowchart TD", f'    system["{_mermaid_text(model.system_name)}"]']
    if not ordered:
        lines += ['    unknown["No architectural components identified"]', "    system --> unknown"]
        return "\n".join(lines) + "\n"
    for index, (name, children) in enumerate(ordered):
        label = f"{name} ({len(children)})" if children else name
        lines += [f'    group_{index}["{_mermaid_text(label)}"]', f"    system --> group_{index}"]
    if not detail:
        group_index = {name: index for index, (name, _) in enumerate(ordered)}
        component_group = {
            component_id: group_index[subsystem.name]
            for subsystem in model.subsystems if subsystem.name in group_index
            for component_id in subsystem.components
        }
        edges: dict[tuple[int, int], ArchitectureRelationship] = {}
        for relation in _diagram_relationships(model.relationships):
            source = component_group.get(relation.source)
            target = component_group.get(relation.target)
            if source is not None and target is not None and source != target:
                edges.setdefault((source, target), relation)
        for (source, target), relation in list(edges.items())[:20]:
            lines.append(f"    group_{source} -->|{_mermaid_text(relation.type)}| group_{target}")
    if detail:
        candidates = [(index, child) for index, (_, children) in enumerate(ordered) for child in children]
        available = 15 - 1 - len(ordered)
        shown = candidates[:available] if len(candidates) <= available else candidates[:max(0, available - 1)]
        for index, (group, child) in enumerate(shown):
            lines += [f'    area_{index}["{_mermaid_text(child)}"]', f"    group_{group} --> area_{index}"]
        remaining = len(candidates) - len(shown)
        if remaining and available:
            lines += [f'    more["Other areas ({remaining})"]', "    system --> more"]
    return "\n".join(lines) + "\n"


def render_system_overview_mermaid(model: ArchitectureModel) -> str:
    if _needs_aggregation(model):
        return _aggregated_graph(model, detail=False)
    lines = ["flowchart TD", f'    system["{_mermaid_text(model.system_name)}"]']
    if not model.components:
        lines += ['    unknown["No architectural components identified"]', "    system --> unknown"]
    for subsystem in model.subsystems:
        lines.append(f'    {subsystem.id}["{_mermaid_text(subsystem.name)}"]')
        lines.append(f"    system --> {subsystem.id}")
        for component_id in subsystem.components:
            lines.append(f"    {subsystem.id} --> {component_id}")
    for component in model.components:
        lines.append(f'    {component.id}["{_mermaid_text(component.name)}"]')
    if model.components:
        lines += [
            "    classDef high fill:#dbeafe,stroke:#1d4ed8,stroke-width:3px",
            "    classDef medium fill:#f0f9ff,stroke:#0284c7,stroke-width:2px",
            "    classDef low fill:#f8fafc,stroke:#94a3b8,stroke-width:1px",
        ]
        for component in model.components:
            lines.append(f"    class {component.id} {_significance_label(component).lower()}")
    for relation in _diagram_relationships(model.relationships):
        lines.append(f"    {relation.source} -->|{_mermaid_text(relation.type)}| {relation.target}")
    return "\n".join(lines) + "\n"


def render_execution_flow_mermaid(model: ArchitectureModel) -> str:
    lines = ["sequenceDiagram", "    actor User"]
    components = {component.id: component for component in model.components}
    flows = model.execution_flows
    if not flows:
        lines.append("    Note over User: No component execution path could be inferred")
        return "\n".join(lines) + "\n"

    lines.append("    Note over User: Conceptual flow inferred from relationships, not a runtime trace")
    flow = flows[0]
    used = set()
    for path in flow["paths"]:
        for component_id in path["component_ids"]:
            component = components[component_id]
            if component_id not in used:
                lines.append(f"    participant {component.id} as {_mermaid_text(component.name)}")
                used.add(component_id)
    for path in flow["paths"]:
        ids = path["component_ids"]
        first = components[ids[0]]
        optional = path.get("kind") == "optional"
        if optional:
            lines.append("    opt Optional integration")
        elif flow["entry_points"] and all(
            Path(entry).name == "__init__.py" for entry in flow["entry_points"]
        ):
            lines.append(
                f"    Note over {first.id}: Public API: "
                f"{_mermaid_text(', '.join(flow['entry_points']))}"
            )
        else:
            lines.append(
                f"    User->>{first.id}: Start at "
                f"{_mermaid_text(', '.join(flow['entry_points']) or 'application entry')}"
            )
        for source_id, target_id, relation in zip(
            ids, ids[1:], path["relationship_types"]
        ):
            lines.append(f"    {source_id}->>{target_id}: {_mermaid_text(relation)}")
        if optional:
            lines.append("    end")
    return "\n".join(lines) + "\n"


def render_subsystem_map_mermaid(model: ArchitectureModel) -> str:
    if _needs_aggregation(model):
        return _aggregated_graph(model, detail=True)
    lines = ["flowchart TD", f'    system["{_mermaid_text(model.system_name)}"]']
    if not model.subsystems:
        lines += ['    unknown["No subsystem boundaries identified"]', "    system --> unknown"]
        return "\n".join(lines) + "\n"
    components = {component.id: component for component in model.components}
    for subsystem in model.subsystems:
        lines.append(f'    subgraph {subsystem.id}["{_mermaid_text(subsystem.name)}"]')
        for component_id in subsystem.components:
            lines.append(
                f'        {component_id}["{_mermaid_text(components[component_id].name)}"]'
            )
        lines.append("    end")
        for component_id in subsystem.components:
            lines.append(f"    system --> {component_id}")
    for relationship in _diagram_relationships(model.relationships):
        lines.append(
            f"    {relationship.source} -->|{_mermaid_text(relationship.type)}| "
            f"{relationship.target}"
        )
    return "\n".join(lines) + "\n"


def render_module_graph_mermaid(model: ArchitectureModel, module_path: str) -> str:
    area = next((item for item in model.repository_relevance.areas if item.path == module_path), None)
    if area is None:
        raise ValueError(f"Unknown module or business area: {module_path}")
    prefix = area.path.rstrip("/") + "/"
    components = [
        component for component in model.components
        if any(location == area.path or location.startswith(prefix) for location in component.locations)
        and not (component.type == "feature" and area.path in component.locations)
    ]
    ids = {component.id for component in components}
    lines = ["flowchart TD", f'    module["{_mermaid_text(area.name)} ({_mermaid_text(area.path)})"]']
    if not components:
        lines += ['    unknown["No module-level components identified"]', "    module --> unknown"]
    for component in components:
        lines += [
            f'    {component.id}["{_mermaid_text(component.name)}"]',
            f"    module --> {component.id}",
        ]
    scoped_relationships = [
        relation for relation in model.relationships
        if relation.source in ids and relation.target in ids
        and any(evidence.startswith(prefix) for evidence in relation.evidence)
    ]
    for relation in _diagram_relationships(scoped_relationships):
        lines.append(f"    {relation.source} -->|{_mermaid_text(relation.type)}| {relation.target}")
    return "\n".join(lines) + "\n"


def render_architecture_summary_markdown(model: ArchitectureModel) -> str:
    components_by_id = {component.id: component for component in model.components}
    high = [component for component in model.components if _significance_label(component) == "High"]
    central = high[:6]
    if not central:
        central = model.components[:min(3, len(model.components))]
    central_ids = {component.id for component in central}
    additional_central = [component for component in high if component.id not in central_ids]
    supporting = [component for component in model.components if component.id not in central_ids and component not in additional_central]
    lines = [
        "# Architecture Overview",
        "",
        f"**{model.system_name}** is a **{model.system_type}**. {model.description}",
        "",
    ]
    if central:
        lines += [
            "The main concepts to understand first are "
            + ", ".join(f"**{component.name}**" for component in central)
            + ".",
            "",
        ]
    areas = model.repository_relevance.areas
    if areas:
        lines += [
            "The repository contains identifiable application or workspace areas: "
            + ", ".join(f"**{area.name}** (`{area.path}`)" for area in areas[:8])
            + (f", and {len(areas) - 8} more" if len(areas) > 8 else "")
            + ". Start with these project-owned areas before framework internals.",
            "",
        ]
    if model.repository_relevance.paths.get("low"):
        lines += [
            "Vendor and third-party directories are supporting dependencies, not primary onboarding material.",
            "",
        ]
    lines += ["## Main Components", ""]
    for component in central:
        priority_evidence = sorted(
            component.evidence,
            key=lambda item: (
                0 if "(readme lead)" in item else
                1 if "(public API export)" in item else
                2 if "(entry point" in item else
                3 if "(documentation)" in item else
                4 if "(structure)" in item or "(source)" in item else 5,
                item,
            ),
        )[:4]
        lines.append(
            f"- **{component.name}** — {component.description} "
            f"(significance: {_significance_label(component)}; confidence: {component.confidence:.0%}). "
            f"Evidence: {', '.join(f'`{path}`' for path in priority_evidence)}."
        )
    if not model.components:
        lines.append("- No major architectural components could be inferred.")
    if additional_central:
        lines += [
            "", "Other significant components: "
            + ", ".join(f"**{component.name}**" for component in additional_central[:8])
            + (f", and {len(additional_central) - 8} more" if len(additional_central) > 8 else "") + ".",
        ]
    if supporting:
        lines += [
            "", "## Supporting Subsystems", "",
            "Other detected components include "
            + ", ".join(
                f"**{component.name}** ({_significance_label(component)} significance, "
                f"{component.confidence:.0%} confidence)"
                for component in supporting[:8]
            )
            + (f", and {len(supporting) - 8} more" if len(supporting) > 8 else "")
            + ". Their roles and evidence are recorded in the architecture map.",
        ]
    if model.layers:
        lines += ["", "## Architectural Layers", "", "The following layers reflect the roles inferred for this repository:", ""]
        for layer in model.layers:
            names = ", ".join(components_by_id[component_id].name for component_id in layer.components[:6])
            if len(layer.components) > 6:
                names += f", and {len(layer.components) - 6} more"
            lines.append(f"- **{layer.name}**: {names}.")
    extensions = [component for component in model.components if component.type in {"extension", "registry"}]
    if extensions:
        lines += [
            "", "## Extension Points", "",
            "Potential extension or registration points include "
            + ", ".join(f"**{component.name}**" for component in extensions[:8])
            + (f", and {len(extensions) - 8} more" if len(extensions) > 8 else "")
            + "; inspect their implementations to see how capabilities are added.",
        ]
    if model.relationships:
        lines += ["", "## Relationships", ""]
        relations = sorted(
            _diagram_relationships(model.relationships),
            key=lambda relation: (
                -(components_by_id[relation.source].significance + components_by_id[relation.target].significance),
                -relation.confidence, relation.source, relation.target,
            ),
        )[:8]
        for relation in relations:
            evidence = ", ".join(f"`{item}`" for item in relation.evidence[:2])
            lines.append(
                f"- **{components_by_id[relation.source].name}** {relation.type} "
                f"**{components_by_id[relation.target].name}** "
                f"({relation.confidence:.0%} confidence). {relation.description} "
                f"Evidence: {evidence}."
            )
    lines += ["", "## Execution Flow", ""]
    for flow in model.execution_flows:
        lines.append(f"### {flow['name']}")
        lines.append(
            "This is an inferred conceptual path, not an observed runtime trace. "
            "Imports and references indicate dependencies, not necessarily calls."
        )
        for path in flow["paths"]:
            for index, (source_id, target_id, relation) in enumerate(zip(
                path["component_ids"], path["component_ids"][1:], path["relationship_types"]
            ), 1):
                lines.append(
                    f"{index}. **{components_by_id[source_id].name}** {relation} "
                    f"**{components_by_id[target_id].name}**."
                )
    if not model.execution_flows:
        lines.append("No component-to-component runtime flow could be inferred.")
    if model.entry_points:
        lines += ["", "Entry points: " + ", ".join(f"`{path}`" for path in model.entry_points) + "."]
    lines += ["", "## Key Concepts", ""]
    lines += [f"- {item}" for item in (responsibility for component in central for responsibility in component.responsibilities)] or ["- No responsibilities were inferred from repository structure."]
    if model.framework_architecture:
        lines += ["", "Framework architecture:", *[f"- {item}" for item in model.framework_architecture]]
    if model.external_dependencies or model.data_stores:
        lines += ["", "Declared or configured integrations and data stores (not proof of active deployment):"]
        lines += [f"- {item}" for item in [*model.external_dependencies, *model.data_stores]]
    if model.deployment_architecture:
        lines += ["", "Deployment architecture:", *[f"- {item}" for item in model.deployment_architecture]]
    lines += ["", "## Recommended Learning Path", ""]
    lines += [
        f"{index}. Explore `{path}`."
        for index, path in enumerate(model.recommended_learning_path, 1)
    ] or ["1. Start with the repository README and major subsystem directories."]
    return "\n".join(lines) + "\n"


def render_architecture_map_json(model: ArchitectureModel) -> str:
    return json.dumps(model.to_dict(), ensure_ascii=False, indent=2) + "\n"

