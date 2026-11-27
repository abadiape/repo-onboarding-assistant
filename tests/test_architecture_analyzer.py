import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzers.architecture_analyzer import (
    _execution_flows,
    extract_architecture,
    render_architecture_map_json,
    render_architecture_summary_markdown,
    render_execution_flow_mermaid,
    render_module_graph_mermaid,
    render_subsystem_map_mermaid,
    render_system_overview_mermaid,
)
from analyzers.repository_relevance import (
    RepositoryArea,
    RepositoryRelevance,
    classify_path,
)
from models.architecture_model import (
    ArchitectureComponent,
    ArchitectureModel,
    ArchitectureRelationship,
)
from models.models import Dependency, RepositoryFile, RepositoryModel


def test_architecture_model_discovers_backend_components_and_renders_artifacts(tmp_path):
    (tmp_path / "README.md").write_text(
        "A task microservice that exposes an HTTP API.", encoding="utf-8"
    )
    (tmp_path / "compose.yaml").write_text(
        "services:\n  postgres:\n  redis:\n", encoding="utf-8"
    )
    model = RepositoryModel(
        repository_name="task-api",
        root_path=str(tmp_path),
        readme_summary="A task microservice.",
        frameworks=["FastAPI"],
        dependencies=[Dependency("stripe", "1.0", "requirements.txt")],
        directories=[
            "src/api",
            "src/controllers",
            "src/services",
            "src/domain",
            "src/repositories",
        ],
        files=[
            RepositoryFile("README.md", "readme"),
            RepositoryFile("compose.yaml", "docker"),
            RepositoryFile("src/main.py", "source", "Python"),
        ],
        entry_points=["src/main.py"],
        onboarding_docs=["README.md"],
        ci_cd_files=[".github/workflows/ci.yml"],
        detected_patterns=["structure:src"],
    )

    architecture = extract_architecture(model)
    component_names = {component.name for component in architecture.components}

    assert architecture.system_type == "Microservice"
    assert {
        "API Layer",
        "Controllers",
        "Services",
        "Domain Layer",
        "Persistence Layer",
    } <= component_names
    assert architecture.entry_points == ["src/main.py"]
    assert any("FastAPI" in item for item in architecture.framework_architecture)
    assert any("PostgreSQL" in item for item in architecture.data_stores)
    assert any("Redis" in item for item in architecture.data_stores)
    assert any("Stripe" in item for item in architecture.external_dependencies)
    assert architecture.relationships
    assert all(component.relationships for component in architecture.components if component.name == "API Layer")

    overview = render_system_overview_mermaid(architecture)
    flow = render_execution_flow_mermaid(architecture)
    subsystem_map = render_subsystem_map_mermaid(architecture)
    summary = render_architecture_summary_markdown(architecture)
    architecture_map = json.loads(render_architecture_map_json(architecture))
    assert "API Layer" in overview and "delegates to" in overview
    assert flow.startswith("sequenceDiagram\n")
    assert "Start at src/main.py" in flow
    assert "subgraph subsystem_" in subsystem_map
    assert "## Recommended Learning Path" in summary
    assert {
        "components",
        "subsystems",
        "responsibilities",
        "relationships",
        "entry_points",
        "external_dependencies",
        "data_stores",
        "execution_flows",
        "detected_patterns",
    } <= set(architecture_map)
    assert "1.0" not in summary


def test_relevance_excludes_vendor_and_generated_from_inference():
    assert classify_path("src/framework/runtime.py") == ("high", "application")
    assert classify_path("infra/deploy.yaml") == ("medium", "infrastructure")
    assert classify_path("vendor/package/controllers") == ("low", "vendor")
    assert classify_path("src/generated/controllers") == ("ignored", "generated")
    assert classify_path("pub/static/frontend/theme/js/app.js") == ("ignored", "generated")
    assert classify_path("var/view_preprocessed/pub/static/a.js") == ("ignored", "generated")
    architecture = extract_architecture(RepositoryModel(
        repository_name="application",
        directories=["src/services", "vendor/package/controllers", "src/generated/controllers"],
        dependencies=[Dependency("redis", None, "vendor/package/composer.json")],
    ))
    assert {component.name for component in architecture.components} == {"Services"}
    assert architecture.data_stores == []
    assert not any(path.startswith(("vendor/", "src/generated/")) for path in architecture.recommended_learning_path)


def test_magento_architecture_uses_local_evidence_not_inherited_readme(tmp_path):
    files = {
        "README.md": "# Magento\n\nThis repository contains a sample Magento Commerce instance.\n",
        "pub/index.php": "<?php\n",
        "app/code/Shop/Orders/Model/Order.php": "<?php\nclass OrderModel {}\n",
        "app/code/Shop/Orders/Model/ResourceModel/Order.php": "<?php\nclass OrderResourceModel {}\n",
        "app/code/Shop/Orders/Ui/DataProvider/OrderProvider.php": "<?php\nclass OrderProvider {}\n",
        "app/code/Shop/Orders/Controller/Index.php": "<?php\nclass IndexController {}\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    model = RepositoryModel(
        repository_name="shop", root_path=str(tmp_path), frameworks=["Magento"],
        readme_summary="This repository contains a sample Magento Commerce instance.",
        directories=[
            "app/code/Shop/Orders", "app/code/Shop/Orders/Model",
            "app/code/Shop/Orders/Model/ResourceModel", "app/code/Shop/Orders/Controller",
            "app/code/Shop/Orders/Ui/DataProvider",
            "app/code/Shop/Orders/Model/sample",
        ],
        files=[RepositoryFile(path, "readme" if path == "README.md" else "source") for path in files],
        entry_points=["dev/tests/example/index.js"],
    )
    architecture = extract_architecture(model)
    components = {component.name: component for component in architecture.components}

    assert "sample Magento" not in architecture.description
    assert "1 module directory under app/code" in architecture.description
    assert "app/code/Shop/Orders" in architecture.description
    assert "Models and Domain Code" in components
    assert "Resource Models" in components
    assert "Provider Classes" in components
    assert "do not establish" in components["Models and Domain Code"].description
    assert "configuration or UI data" in components["Provider Classes"].description
    assert "pub/index.php" in architecture.entry_points
    assert not any("tests/" in path for path in architecture.entry_points)
    assert all(layer.description != "Inferred from component roles." for layer in architecture.layers)
    assert not any(
        "README.md:3" in evidence
        for relation in architecture.relationships for evidence in relation.evidence
    )


def test_magento_imports_and_type_references_are_not_execution_flow():
    components = [
        ArchitectureComponent("a", "Observers", "extension", ""),
        ArchitectureComponent("b", "Models", "domain", ""),
        ArchitectureComponent("c", "Providers", "integration", ""),
    ]
    relationships = [
        ArchitectureRelationship("a", "b", "imports", "", evidence=["app/code/A/One/a.php:1"]),
        ArchitectureRelationship("b", "c", "references", "", evidence=["app/code/A/Two/b.php:2"]),
    ]
    assert not _execution_flows(components, relationships, [], [], [], require_execution_evidence=True)
    architecture = ArchitectureModel(
        system_name="shop", system_type="application", description="",
        components=components, relationships=relationships, frameworks=["Magento"],
    )
    diagram = render_execution_flow_mermaid(architecture)
    assert diagram.startswith("flowchart LR\n")
    assert "Associations only - not a verified execution sequence or runtime calls" in diagram
    assert 'a["Observers"]' in diagram
    assert "a -->|imports| b" in diagram
    assert "b -->|references| c" in diagram
    assert "User" not in diagram
    assert architecture.execution_flows == []
    architecture.frameworks = ["Other"]
    assert "No component execution path" in render_execution_flow_mermaid(architecture)
    architecture.frameworks = ["Magento"]
    architecture.relationships = []
    assert "No component execution path" in render_execution_flow_mermaid(architecture)


def test_magento_execution_flow_takes_precedence_over_association_fallback():
    model = ArchitectureModel(
        system_name="shop", system_type="application", description="", frameworks=["Magento"],
        components=[ArchitectureComponent("a", "API", "interface", ""),
                    ArchitectureComponent("b", "Service", "application", "")],
        relationships=[ArchitectureRelationship("a", "b", "dispatches to", "")],
        execution_flows=[{"entry_points": [], "paths": [{
            "component_ids": ["a", "b"], "relationship_types": ["dispatches to"],
        }]}],
    )
    diagram = render_execution_flow_mermaid(model)
    assert diagram.startswith("sequenceDiagram\n")
    assert "a->>b: dispatches to" in diagram
    assert "Associations only" not in diagram


def test_magento_overview_preserves_specific_readme_description():
    model = RepositoryModel(
        repository_name="shop",
        frameworks=["Magento"],
        readme_summary="A Magento storefront integrating a regional fulfillment service.",
        directories=["app/code/Shop/Fulfillment"],
    )
    architecture = extract_architecture(model)
    assert "README description: A Magento storefront integrating a regional fulfillment service." in architecture.description
    assert "app/code/Shop/Fulfillment" in architecture.description


def test_document_relationships_do_not_match_unrelated_nested_directory_names(tmp_path):
    (tmp_path / "README.md").write_text(
        "# Example\n\nControllers contain a sample configuration.\n", encoding="utf-8"
    )
    model = RepositoryModel(
        repository_name="example", root_path=str(tmp_path),
        directories=["src/controllers", "src/models", "src/models/sample"],
        files=[RepositoryFile("README.md", "readme")],
    )
    architecture = extract_architecture(model)
    assert not any(
        "README.md:3" in evidence
        for relation in architecture.relationships for evidence in relation.evidence
    )


def test_module_graph_selects_relationships_within_the_requested_area():
    area = "packages/checkout"
    model = ArchitectureModel(
        system_name="shop", system_type="Application", description="",
        repository_relevance=RepositoryRelevance(areas=[RepositoryArea("checkout", area, "workspace module")]),
        components=[
            ArchitectureComponent("controller", "Controllers", "application", "", locations=[area + "/controllers"]),
            ArchitectureComponent("service", "Services", "application", "", locations=[area + "/services"]),
        ],
        relationships=[
            ArchitectureRelationship("controller", "service", "imports", "", 0.9, ["packages/catalog/controller.py:1"]),
            ArchitectureRelationship("controller", "service", "uses", "", 0.8, [area + "/controller.py:3"]),
        ],
    )
    graph = render_module_graph_mermaid(model, area)
    assert "controller -->|uses| service" in graph
    assert "imports" not in graph


def test_execution_flow_escapes_semicolons_in_diagram_text():
    model = RepositoryModel(
        repository_name="app",
        directories=["src/controllers", "src/services"],
        entry_points=["src/start;service.py"],
    )
    diagram = render_execution_flow_mermaid(extract_architecture(model))
    note = next(line for line in diagram.splitlines() if "Conceptual flow inferred" in line)
    assert ";" not in note
    assert "Start at src/start#59;service.py" in diagram


def test_readme_and_public_api_outweigh_secondary_directory_size(tmp_path):
    files = {
        "README.md": (
            "# Acme - Agent toolkit for retrieval\n\n"
            "A toolkit for agents that retrieve context.\n\n"
            "## Additional capabilities\n\nArtifacts are optional outputs.\n"
        ),
        "src/acme/__init__.py": "from .agent import Agent\n",
        "src/acme/agent.py": "class Agent:\n    pass\n",
    }
    for index in range(20):
        files[f"src/acme/artifacts/item_{index}.py"] = "value = 1\n"
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    model = RepositoryModel(
        repository_name="acme",
        root_path=str(tmp_path),
        readme_summary="A toolkit for agents that retrieve context.",
        directories=["src/acme/artifacts"],
        files=[
            RepositoryFile(path, "readme" if path == "README.md" else "source")
            for path in files
        ],
    )
    architecture = extract_architecture(model)
    components = {component.name: component for component in architecture.components}

    assert "Agent toolkit for retrieval" in architecture.description
    assert components["Agents"].relevance > components["Artifacts"].relevance
    assert components["Agents"].confidence > components["Artifacts"].confidence
    assert any("README.md:1 (readme lead)" in item for item in components["Agents"].evidence)
    assert any("public API export" in item for item in components["Agents"].evidence)
    assert architecture.entry_points == ["src/acme/__init__.py"]
    assert "src/acme/__init__.py" in architecture.recommended_learning_path
    assert architecture.components.index(components["Agents"]) < architecture.components.index(components["Artifacts"])
    assert render_architecture_summary_markdown(architecture).index("**Agents**") < render_architecture_summary_markdown(architecture).index("**Artifacts**")


def test_significance_is_distinct_from_confidence_and_visible_in_artifacts(tmp_path):
    files = {
        "README.md": "# Toolkit - Agents execute requests\n\nAgents coordinate requests.\n\n## Extras\nArtifacts are optional.\n",
        "src/toolkit/__init__.py": "from .agent import Agent\nfrom .artifacts import Artifact\n",
        "src/toolkit/agent/__init__.py": "class Agent:\n    pass\n",
        "src/toolkit/artifacts/__init__.py": "class Artifact:\n    pass\n",
        "docs/architecture.md": "Artifacts are optional. Agents execute requests.\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="toolkit", root_path=str(tmp_path),
        directories=["src/toolkit/agent", "src/toolkit/artifacts"],
        files=[RepositoryFile(path, "source" if path.endswith(".py") else "file") for path in files],
    ))
    by_name = {component.name: component for component in architecture.components}
    assert by_name["Agents"].confidence >= 0.8
    assert by_name["Artifacts"].confidence >= 0.8
    assert by_name["Agents"].significance > by_name["Artifacts"].significance
    assert "significance: High" in render_architecture_summary_markdown(architecture)
    assert "## Supporting Subsystems" in render_architecture_summary_markdown(architecture)
    serialized = json.loads(render_architecture_map_json(architecture))
    assert next(item for item in serialized["components"] if item["name"] == "Agents")["significance"] == by_name["Agents"].significance
    assert "class component_agents high" in render_system_overview_mermaid(architecture)


def test_flow_prefers_documented_behavior_over_an_import_shortcut(tmp_path):
    files = {
        "README.md": (
            "Runtime executes Skills. Skills invokes Providers. "
            "Providers returns Model Responses. Model Responses populates Skill Result. "
            "Skill Result contains Artifacts.\n"
        ),
        "src/runtime/runtime.py": "from src.artifacts.artifact import Artifact\nclass Runtime:\n    pass\n",
        "src/skills/build.py": "class BuildSkill:\n    pass\n",
        "src/providers/provider.py": "class ModelProvider:\n    pass\nclass ModelResponse:\n    pass\n",
        "src/results/result.py": "class SkillResult:\n    pass\n",
        "src/artifacts/artifact.py": "class Artifact:\n    pass\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="runtime", root_path=str(tmp_path),
        entry_points=["src/runtime/runtime.py"],
        directories=["src/runtime", "src/skills", "src/providers", "src/results", "src/artifacts"],
        files=[RepositoryFile(path, "readme" if path.endswith(".md") else "source") for path in files],
    ))
    path = architecture.execution_flows[0]["paths"][0]
    names = {component.id: component.name for component in architecture.components}
    assert [names[item] for item in path["component_ids"]] == [
        "Runtime", "Skills", "Providers", "Model Responses", "Skill Result", "Artifacts",
    ]
    assert path["relationship_types"] == ["executes", "invokes", "returns", "populates", "contains"]
    assert all(evidence for evidence in path["relationship_evidence"])
    summary = render_architecture_summary_markdown(architecture)
    assert "**Runtime** executes **Skills**" in summary
    assert "not an observed runtime trace" in summary


def test_integrations_ignore_docs_optional_profiles_and_dev_dependencies(tmp_path):
    files = {
        "README.md": "# Example\nUse MongoDB, Redis, or Stripe in examples.\n",
        "compose.yaml": (
            "services:\n  web:\n    image: app\n  postgres:\n"
            "    image: postgres\n    profiles: [optional]\n"
        ),
        "src/main.py": "# import redis\ndef optional_backend():\n    import redis\n",
        "config.example.yaml": "database_url: mysql://localhost\n",
        "config.yaml": "mongodb:\n  enabled: false\n  url: mongodb://localhost\n",
        "docs/config.yaml": "database_url: mysql://localhost\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    model = RepositoryModel(
        repository_name="app", root_path=str(tmp_path),
        files=[RepositoryFile(path, "source" if path.endswith(".py") else "file") for path in files],
        dependencies=[
            Dependency("redis", None, "package.json", "development"),
            Dependency("stripe", None, "package.json", "optional"),
        ],
    )
    architecture = extract_architecture(model)
    assert architecture.data_stores == []
    assert architecture.external_dependencies == []
    (tmp_path / "src/main.py").write_text("import redis\n", encoding="utf-8")
    (tmp_path / "compose.yaml").write_text("services:\n  postgres:\n    image: postgres\n", encoding="utf-8")
    model.dependencies.append(Dependency("stripe", None, "package.json"))
    architecture = extract_architecture(model)
    assert any("Redis" in item for item in architecture.data_stores)
    assert any("PostgreSQL" in item for item in architecture.data_stores)
    assert any("Stripe" in item for item in architecture.external_dependencies)
    assert not any("MongoDB" in item or "MySQL" in item for item in architecture.data_stores)


def test_qdrant_runtime_and_optional_evidence_are_distinct():
    model = RepositoryModel(
        repository_name="app",
        dependencies=[
            Dependency("qdrant-client", None, "pyproject.toml", "optional:qdrant"),
            Dependency("qdrant-client", None, "pyproject.toml", "optional:full"),
            Dependency("qdrant-client", None, "pyproject.toml", "optional:dev"),
            Dependency("qdrant-client", None, "vendor/pkg/pyproject.toml", "optional:qdrant"),
        ],
    )
    architecture = extract_architecture(model)
    assert architecture.data_stores == []
    assert architecture.optional_integrations == [
        "Qdrant (vector database; optional dependency qdrant-client in pyproject.toml; extras: full, qdrant)"
    ]
    assert "not proof of activation or deployment" in render_architecture_summary_markdown(architecture)
    model.dependencies = [Dependency("qdrant-client", None, "requirements.txt")]
    architecture = extract_architecture(model)
    assert architecture.data_stores == ["Qdrant (vector database)"]
    assert architecture.optional_integrations == []
    model.dependencies = [Dependency("notqdrant", None, "requirements.txt")]
    assert extract_architecture(model).data_stores == []


def test_return_annotation_does_not_mean_returning_the_entire_owner_component(tmp_path):
    files = {
        "src/tools/registry.py": (
            "from src.llm.types import ToolSpec\n"
            "class ToolRegistry:\n"
            "    def register(self) -> ToolSpec:\n"
            "        return ToolSpec()\n"
        ),
        "src/llm/types.py": "class ToolSpec:\n    pass\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="toolkit", root_path=str(tmp_path),
        directories=["src/tools", "src/llm"],
        files=[RepositoryFile(path, "source") for path in files],
    ))
    assert not any(
        relation.source == "component_tools"
        and relation.target == "component_model_backends"
        and relation.type == "returns"
        for relation in architecture.relationships
    )


def test_discovers_public_utility_and_enterprise_feature_boundaries(tmp_path):
    files = {
        "src/util/__init__.py": "from .tokenizer import Tokenizer\n",
        "src/util/tokenizer.py": "class Tokenizer:\n    pass\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="utility",
        root_path=str(tmp_path),
        files=[RepositoryFile(path, "source") for path in files],
        directories=[
            "src/main/java/com/company/billing",
            "src/main/java/com/company/billing/controller",
            "src/main/java/com/company/billing/service",
            "src/main/java/com/company/shipping",
            "src/main/java/com/company/shipping/controller",
            "src/main/java/com/company/shipping/service",
        ],
        frameworks=["Spring Boot"],
    ))
    by_name = {component.name: component for component in architecture.components}
    assert {"Tokenizer", "Billing", "Shipping", "Controllers", "Services"} <= set(by_name)
    assert any("public API export" in item for item in by_name["Tokenizer"].evidence)
    features = next(subsystem for subsystem in architecture.subsystems if subsystem.name == "Features")
    assert {by_name["Billing"].id, by_name["Shipping"].id} <= set(features.components)


def test_typescript_public_api_evidence_requires_a_reexport(tmp_path):
    files = {
        "src/index.ts": 'import { Parser } from "./parser";\nexport { Tokenizer } from "./tokenizer";\n',
        "src/parser.ts": "export class Parser {}\n",
        "src/tokenizer.ts": "export class Tokenizer {}\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="utility",
        root_path=str(tmp_path),
        files=[RepositoryFile(path, "source") for path in files],
    ))
    by_name = {component.name: component for component in architecture.components}
    assert "Tokenizer" in by_name
    assert "Parser" not in by_name
    assert any("src/index.ts:2 (public API export)" in item for item in by_name["Tokenizer"].evidence)


def test_large_repository_sampling_reaches_distinct_source_areas(tmp_path):
    paths = [f"src/artifacts/item_{index:03}.py" for index in range(150)]
    paths.append("src/zcore/services/transactions.py")
    for path in paths:
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "class TransactionService:\n    pass\n" if path.endswith("transactions.py") else "value = 1\n",
            encoding="utf-8",
        )
    architecture = extract_architecture(RepositoryModel(
        repository_name="enterprise",
        root_path=str(tmp_path),
        directories=["src/artifacts", "src/zcore/services"],
        files=[RepositoryFile(path, "source") for path in paths],
    ))
    services = next(component for component in architecture.components if component.name == "Services")
    assert any("src/zcore/services/transactions.py" in evidence for evidence in services.evidence)


def test_dotnet_feature_and_constructor_reference(tmp_path):
    files = {
        "src/Billing/Controllers/InvoicesController.cs": (
            "public class InvoicesController {\n"
            "    public InvoicesController(InvoiceService service) { }\n"
            "}\n"
        ),
        "src/Billing/Services/InvoiceService.cs": "public class InvoiceService { }\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="enterprise",
        root_path=str(tmp_path),
        directories=["src/Billing", "src/Billing/Controllers", "src/Billing/Services"],
        files=[RepositoryFile(path, "source", "C#") for path in files],
    ))
    by_name = {component.name: component for component in architecture.components}
    assert {"Billing", "Controllers", "Services"} <= by_name.keys()
    assert any(layer.name == "Application Layer" for layer in architecture.layers)
    assert any(
        relation.source == by_name["Controllers"].id
        and relation.target == by_name["Services"].id
        and any("InvoicesController.cs:2" in evidence for evidence in relation.evidence)
        for relation in architecture.relationships
    )


def test_architecture_discovery_uses_framework_conventions():
    react = extract_architecture(RepositoryModel(
        repository_name="web-client",
        frameworks=["React"],
        directories=["src/pages", "src/components", "src/hooks", "src/store", "src/api"],
    ))
    react_names = {component.name for component in react.components}
    assert {"Pages", "Components", "Hooks", "State Management", "API Client Layer"} <= react_names
    assert {layer.name for layer in react.layers} >= {"Presentation Layer", "Application Layer", "Integration Layer"}
    assert any(
        relation.source == "component_pages" and relation.target == "component_components"
        for relation in react.relationships
    )
    assert react.execution_flows

    laravel = extract_architecture(RepositoryModel(
        repository_name="web-app",
        frameworks=["Laravel"],
        directories=["app/Http/Controllers", "app/Services", "app/Models", "app/Http/Middleware", "routes"],
    ))
    laravel_names = {component.name for component in laravel.components}
    assert {"Routes", "Controllers", "Services", "Models", "Middleware"} <= laravel_names
    assert any(
        relation.source == "component_controllers"
        and relation.target == "component_services"
        for relation in laravel.relationships
    )

    nestjs = extract_architecture(RepositoryModel(
        repository_name="api-server",
        frameworks=["NestJS"],
        directories=[
            "src/modules",
            "src/controllers",
            "src/providers",
            "src/guards",
            "src/interceptors",
        ],
    ))
    nestjs_names = {component.name for component in nestjs.components}
    assert {"Modules", "Controllers", "Providers", "Guards", "Interceptors"} <= nestjs_names
    assert any(
        relation.source == "component_modules"
        and relation.target == "component_providers"
        for relation in nestjs.relationships
    )

    runtime = extract_architecture(RepositoryModel(
        repository_name="plugin-runtime",
        directories=[
            "src/runtime",
            "src/registries",
            "src/providers",
            "src/plugins",
            "src/skills",
            "src/artifacts",
        ],
    ))
    runtime_names = {component.name for component in runtime.components}
    assert {"Runtime", "Registries", "Providers", "Plugins", "Skills", "Artifacts"} <= runtime_names
    assert any(
        relation.source == "component_skills"
        and relation.target == "component_artifacts"
        for relation in runtime.relationships
    )


def test_relationship_discovery_uses_imports_types_registrations_and_docs(tmp_path):
    source_files = {
        "src/runtime/runtime.py": (
            "from src.skills.build import BuildSkill\n"
            "class Runtime:\n"
            "    def execute(self, skill: BuildSkill):\n"
            "        return skill.run()\n"
        ),
        "src/runtime/config.py": (
            "from src.providers.model_provider import ModelProvider\n"
            "providers = [ModelProvider]\n"
        ),
        "src/runtime/index.ts": 'export { BuildSkill } from "../skills/build";\n',
        "src/skills/build.py": (
            "from src.artifacts.artifact import Artifact\n"
            "from src.results.result import SkillResult\n"
            "class BuildSkill:\n"
            "    def run(self) -> SkillResult:\n"
            "        return SkillResult()\n"
        ),
        "src/providers/model_provider.py": (
            "class ModelProvider:\n"
            "    pass\n"
            "class ModelRequest:\n"
            "    pass\n"
            "class ModelResponse:\n"
            "    pass\n"
        ),
        "src/artifacts/artifact.py": "class Artifact:\n    pass\n",
        "src/registries/registry.py": (
            "from src.artifacts.artifact import Artifact\n"
            "class ArtifactRegistry:\n"
            "    def register(self, artifact: Artifact):\n"
            "        pass\n"
        ),
        "src/results/result.py": (
            "from src.artifacts.artifact import Artifact\n"
            "class SkillResult:\n"
            "    artifacts: list[Artifact]\n"
        ),
    }
    for relative, content in source_files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "Runtime executes Skills. Skills produce Artifacts. "
        "SkillResult contains Artifacts. Registries track Artifacts.\n",
        encoding="utf-8",
    )
    (tmp_path / "src/runtime/providers.yaml").write_text(
        "providers:\n  - ModelProvider\n", encoding="utf-8"
    )
    model = RepositoryModel(
        repository_name="plugin-runtime",
        root_path=str(tmp_path),
        directories=[
            "src/runtime",
            "src/skills",
            "src/providers",
            "src/artifacts",
            "src/registries",
            "src/results",
        ],
        files=[
            RepositoryFile(path, "source", "Python")
            for path in source_files
        ] + [
            RepositoryFile("README.md", "readme"),
            RepositoryFile("src/runtime/providers.yaml", "file"),
        ],
    )

    architecture = extract_architecture(model)
    component_names = {component.name for component in architecture.components}
    by_id = {component.id: component.name for component in architecture.components}
    relationships = {
        (by_id[item.source], by_id[item.target], item.type): item
        for item in architecture.relationships
    }

    assert {
        "Runtime", "Skills", "Providers", "Model Requests", "Model Responses",
        "Skill Result", "Artifacts", "Registries",
    } <= component_names
    assert ("Runtime", "Skills", "imports") in relationships
    assert ("Runtime", "Skills", "re-exports") in relationships
    assert ("Runtime", "Skills", "depends on") in relationships
    assert ("Runtime", "Providers", "registers") in relationships
    assert relationships[("Runtime", "Providers", "registers")].confidence >= 0.85
    assert relationships[("Runtime", "Providers", "registers")].evidence[0].startswith(
        "src/runtime/config.py:"
    )
    assert any(
        evidence.startswith("src/runtime/providers.yaml:")
        for evidence in relationships[("Runtime", "Providers", "registers")].evidence
    )
    assert ("Skills", "Skill Result", "returns") in relationships
    assert ("Skill Result", "Artifacts", "contains") in relationships
    assert ("Registries", "Artifacts", "tracks") in relationships

    flow = architecture.execution_flows[0]["paths"][0]["component_ids"]
    flow_names = [by_id[component_id] for component_id in flow]
    assert flow_names[0] == "Runtime"
    assert flow_names[-1] == "Registries"
    assert "Skills" in flow_names
    overview = render_system_overview_mermaid(architecture)
    assert "component_skills -->|imports| component_artifacts" in overview
    assert "component_registries -->|imports| component_artifacts" in overview
    architecture_map = json.loads(render_architecture_map_json(architecture))
    assert all(
        0 <= relation["confidence"] <= 1 and relation["evidence"]
        for relation in architecture_map["relationships"]
    )
    summary = render_architecture_summary_markdown(architecture)
    assert "## Relationships" in summary
    assert "confidence" in summary
    assert "src/runtime/config.py:" in summary


def test_relationship_discovery_handles_flat_module_layouts(tmp_path):
    source_files = {
        "onboarding_skill.py": (
            "from repository_scan import scan_repository\n"
            "class OnboardingSkill:\n"
            "    pass\n"
        ),
        "repository_scan.py": (
            "from models import RepositoryModel\n"
            "class RepositoryScanner:\n"
            "    def scan(self) -> RepositoryModel:\n"
            "        pass\n"
        ),
        "models.py": "class RepositoryModel:\n    pass\n",
    }
    for relative, content in source_files.items():
        (tmp_path / relative).write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="flat-project",
        root_path=str(tmp_path),
        entry_points=["onboarding_skill.py"],
        files=[
            RepositoryFile(path, "source", "Python")
            for path in source_files
        ],
    ))
    by_id = {component.id: component.name for component in architecture.components}
    relationships = {
        (by_id[item.source], by_id[item.target], item.type)
        for item in architecture.relationships
    }
    assert {
        "Skills", "Repository Scanner", "Domain Layer",
    } <= set(by_id.values())
    assert ("Skills", "Repository Scanner", "imports") in relationships
    assert ("Repository Scanner", "Domain Layer", "imports") in relationships
    flow_ids = architecture.execution_flows[0]["paths"][0]["component_ids"]
    assert [by_id[component_id] for component_id in flow_ids] == [
        "Skills", "Repository Scanner", "Domain Layer",
    ]


def test_imports_require_local_targets_and_ignore_comments(tmp_path):
    files = {
        "src/controllers/controller.ts": (
            'import { ExternalService } from "vendor/services";\n'
            '// import { Service } from "../services/service";\n'
            'import { Service } from "../services/service.js";\n'
            "class OrderController {}\n"
        ),
        "src/services/service.ts": "class Service {}\n",
    }
    for path, content in files.items():
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    architecture = extract_architecture(RepositoryModel(
        repository_name="shop",
        root_path=str(tmp_path),
        directories=["src/controllers", "src/services"],
        files=[RepositoryFile(path, "source") for path in files],
    ))
    imports = [relation for relation in architecture.relationships if relation.type == "imports"]
    assert len(imports) == 1
    assert imports[0].evidence == ["src/controllers/controller.ts:3 (import ../services/service.js)"]


def test_architecture_analysis_reads_only_model_listed_files(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("A microservice that uses Postgres.", encoding="utf-8")
    try:
        model = RepositoryModel(
            repository_name="minimal",
            root_path=str(tmp_path),
            files=[RepositoryFile("../" + outside.name, "readme")],
        )

        architecture = extract_architecture(model)

        assert architecture.system_type == "Application"
        assert architecture.data_stores == []
    finally:
        outside.unlink()


def test_architecture_analysis_handles_unknown_facts_and_classifies_apps():
    empty = extract_architecture(RepositoryModel(repository_name="empty"))

    assert empty.components == []
    assert empty.relationships == []
    assert empty.entry_points == []
    assert "No component execution path" in render_execution_flow_mermaid(empty)
    assert "No architectural components identified" in render_system_overview_mermaid(empty)

    cli = extract_architecture(RepositoryModel(
        repository_name="tool",
        files=[RepositoryFile("src/cli.py", "source", "Python")],
        entry_points=["src/cli.py"],
    ))
    library = extract_architecture(RepositoryModel(
        repository_name="shared-package",
        files=[RepositoryFile("pyproject.toml", "manifest")],
    ))

    assert cli.system_type == "CLI application"
    assert cli.entry_points == ["src/cli.py"]
    assert library.system_type == "Library or framework"
