"""Architecture integrations."""
from __future__ import annotations

import re
from pathlib import Path

from analyzers.architecture_evidence import _IGNORED_AREAS, _parts, _source_code_lines
from models.models import RepositoryModel

_SERVICE_TERMS = {
    "postgres": ("PostgreSQL", "relational database"),
    "postgresql": ("PostgreSQL", "relational database"),
    "psycopg": ("PostgreSQL", "relational database"),
    "psycopg2": ("PostgreSQL", "relational database"),
    "asyncpg": ("PostgreSQL", "relational database"),
    "qdrant": ("Qdrant", "vector database"),
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


def _external_facts(model: RepositoryModel, files: dict[str, str]) -> tuple[list[str], list[str]]:
    signals = [
        dependency.name for dependency in model.dependencies
        if dependency.scope == "runtime"
        and not set(_parts(dependency.source)) & _IGNORED_AREAS
        and not re.search(r"(?:^|[._-])(?:example|sample|test|dev|development|local|optional)(?:[._-]|$)", Path(dependency.source).name, re.IGNORECASE)
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
            if re.search(r"\b(?:development|dev|example|sample|optional)\b", preamble, re.IGNORECASE):
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
            if not re.match(r"^\s*(?:enabled\s*:\s*false|optional\s*:\s*true)\s*(?:#.*)?$", line, re.IGNORECASE):
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
            and re.search(r"(?:database|datasource|redis|cache|broker|queue|url|uri|endpoint|host|provider)", line, re.IGNORECASE)
            and re.search(r"[:=]", line)
            and not re.search(r"\b(?:optional|example|sample)\b", line, re.IGNORECASE)
        )
    source = "\n".join(signals).lower()
    stores, services = set(), set()
    for term, (name, kind) in _SERVICE_TERMS.items():
        if not re.search(rf"\b{re.escape(term)}\b", source):
            continue
        fact = f"{name} ({kind})"
        (stores if "database" in kind or kind == "cache" else services).add(fact)
    return sorted(services), sorted(stores)


def _optional_integrations(model: RepositoryModel) -> list[str]:
    found: dict[tuple[str, str, str, str], set[str]] = {}
    for dependency in model.dependencies:
        if not (dependency.scope == "optional" or dependency.scope.startswith("optional:")):
            continue
        if set(_parts(dependency.source)) & _IGNORED_AREAS or re.search(
            r"(?:^|[._-])(?:example|sample|test|dev|development|local)(?:[._-]|$)",
            Path(dependency.source).name, re.IGNORECASE,
        ):
            continue
        extra = dependency.scope.removeprefix("optional:")
        if extra != "optional" and re.search(
            r"(?:^|[._-])(?:example|examples|sample|test|tests|dev|development|local)(?:[._-]|$)",
            extra, re.IGNORECASE,
        ):
            continue
        for term, (name, kind) in _SERVICE_TERMS.items():
            if re.search(rf"\b{re.escape(term)}\b", dependency.name, re.IGNORECASE):
                key = (name, kind, dependency.name, dependency.source)
                found.setdefault(key, set()).add(extra)
    return [
        f"{name} ({kind}; optional dependency {package} in {source}"
        + (f'; extras: {", ".join(sorted(extras - {"optional"}))}' if extras - {"optional"} else "")
        + ")"
        for (name, kind, package, source), extras in sorted(found.items())
    ]
