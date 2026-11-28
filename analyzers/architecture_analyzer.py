"""Architecture discovery entry point."""
# Explicit aliases preserve the original import paths.
# ruff: noqa: PLC0414
from __future__ import annotations

from pathlib import Path

from analyzers.architecture_components import (
    _discover_components,
    _import_candidates,
    _target_component,
)
from analyzers.architecture_concepts import _framework, _framework_key, _system_type
from analyzers.architecture_evidence import (
    _IGNORED_AREAS,
    _parts,
    _public_imports,
    _read_model_sources,
    _read_relationship_sources,
)
from analyzers.architecture_flows import _execution_flows as _execution_flows
from analyzers.architecture_integrations import _external_facts, _optional_integrations
from analyzers.architecture_relationships import _discover_relationships
from analyzers.architecture_scoring import _rank_components, _score_significance
from analyzers.architecture_structure import (
    _entry_points,
    _layers,
    _subsystems,
    _system_description,
)
from analyzers.repository_relevance import analyze_relevance, relevant_model
from artifacts.architecture_diagrams import (
    render_execution_flow_mermaid as render_execution_flow_mermaid,
)
from artifacts.architecture_diagrams import (
    render_module_graph_mermaid as render_module_graph_mermaid,
)
from artifacts.architecture_diagrams import (
    render_subsystem_map_mermaid as render_subsystem_map_mermaid,
)
from artifacts.architecture_diagrams import (
    render_system_overview_mermaid as render_system_overview_mermaid,
)
from artifacts.architecture_reports import (
    render_architecture_map_json as render_architecture_map_json,
)
from artifacts.architecture_reports import (
    render_architecture_summary_markdown as render_architecture_summary_markdown,
)
from models.architecture_model import ArchitectureModel
from models.models import RepositoryModel

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
    symbols = {symbol.id: symbol for symbol in model.symbols}
    public_api_paths.extend(
        source.path for relation in model.relationships
        if relation.relationship_type == "EXPORTS"
        for source in [symbols.get(relation.source_id)]
        for target in [symbols.get(relation.target_id)]
        if source is not None and target is not None
        and source.path in source_paths and target.path in source_paths
        and not set(_parts(source.path)) & _IGNORED_AREAS
        and not set(_parts(target.path)) & _IGNORED_AREAS
    )
    if public_api_paths:
        min_depth = min(len(Path(path).parts) for path in public_api_paths)
        public_api_paths = sorted({
            path for path in public_api_paths if len(Path(path).parts) == min_depth
        })[:3]
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
        optional_integrations=_optional_integrations(model),
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
