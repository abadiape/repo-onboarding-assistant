"""Architecture structure."""
from __future__ import annotations

import re
from pathlib import Path

from analyzers.architecture_concepts import _framework
from analyzers.architecture_evidence import (
    _IGNORED_AREAS,
    _parts,
    _public_imports,
)
from analyzers.repository_relevance import RepositoryRelevance
from models.architecture_model import (
    ArchitectureComponent,
    ArchitectureSubsystem,
)
from models.models import RepositoryModel


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
