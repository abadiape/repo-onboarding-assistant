import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzers.architecture_analyzer import extract_architecture
from analyzers.ast.relationship_resolver import resolve_relationships
from analyzers.repository_scan import scan_repository
from models.models import RepositoryModel
from skills.onboarding_skill import run_onboarding

FIXTURE = Path(__file__).parent / "fixtures" / "relationship_repo"


def test_static_relationships_preserve_resolution_and_uncertainty():
    model = scan_repository(FIXTURE)
    symbols = {symbol.qualified_name: symbol for symbol in model.symbols if symbol.kind != "package"}
    by_id = {symbol.id: symbol for symbol in model.symbols}
    service = symbols["pkg.services.Service"]
    relations = model.relationships

    bases = [item for item in relations if item.source_id == service.id and item.relationship_type in {"INHERITS", "IMPLEMENTS"}]
    assert {(item.relationship_type, by_id[item.target_id].qualified_name) for item in bases if item.target_id in by_id} == {
        ("IMPLEMENTS", "pkg.contracts.Storage"),
        ("IMPLEMENTS", "pkg.contracts.AbstractBase"),
        ("INHERITS", "pkg.contracts.Base"),
    }
    assert any(item.target_id == "unresolved:python:Missing" and item.relationship_type == "INHERITS" for item in bases)
    assert all(not item.direct_observation and len(item.evidence) == 2 for item in bases if item.relationship_type == "IMPLEMENTS")
    assert all(item.direct_observation for item in bases if item.relationship_type == "INHERITS")

    decorators = [item for item in relations if item.target_id == service.id and item.relationship_type == "DECORATES"]
    assert {item.source_id for item in decorators} == {
        symbols["pkg.services.retry"].id, "unresolved:python:unknown_decorator(option=True)",
    }
    assert {item.evidence[0].line for item in decorators} == {12, 13}
    registrations = [item for item in relations if item.relationship_type == "REGISTERS"]
    assert len(registrations) == 3
    assert any(item.source_id == "unresolved:python:registry" and item.target_id == service.id for item in registrations)
    assert any(item.target_id == "unresolved:python:Missing" for item in registrations)
    assert not any("other.add" in item.evidence[0].extract for item in registrations)

    exports = [item for item in relations if item.relationship_type == "EXPORTS"]
    package = next(item for item in model.symbols if item.kind == "package")
    assert {(item.source_id, item.target_id) for item in exports} == {
        (package.id, service.id), (package.id, "unresolved:python:MissingExport"),
    }
    assert all(not item.direct_observation for item in exports)
    tests = [item for item in relations if item.relationship_type == "TESTS"]
    assert any(item.target_id == service.id and not item.direct_observation for item in tests)
    assert any(item.evidence[0].detector == "python-test-reference" and item.target_id == service.id for item in tests)
    assert all(item.evidence and item.evidence[0].path and item.evidence[0].line > 0 and item.evidence[0].detector for item in relations)
    assert RepositoryModel.from_dict(model.to_dict()).to_dict() == model.to_dict()


def test_unresolved_and_ambiguous_names_are_not_fabricated(tmp_path):
    for path, content in {
        "first.py": "class Duplicate: pass\n",
        "second.py": "class Duplicate: pass\n",
        "consumer.py": "class Service(Duplicate): pass\n@missing\ndef work(): pass\n",
        "tests/test_duplicate.py": "def test_duplicate(): pass\n",
        "pkg/__init__.py": "from .consumer import *\n__all__ = dynamic()\n",
    }.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    model = scan_repository(tmp_path)
    assert any(item.relationship_type == "INHERITS" and item.target_id == "unresolved:python:Duplicate" for item in model.relationships)
    assert any(item.relationship_type == "TESTS" and item.target_id == "unresolved:python:duplicate" for item in model.relationships)
    assert not any(item.relationship_type == "EXPORTS" for item in model.relationships)
    assert resolve_relationships([], [], []) == []


def test_scopes_aliases_and_registration_in_signature(tmp_path):
    for path, content in {
        "pkg/__init__.py": "import pkg.service as alias\n__all__ = ['alias']\n",
        "pkg/service.py": (
            "from typing import Protocol as P\n"
            "class Interface(P[int]): pass\n"
            "class Service(Interface): pass\n"
            "def make_base(): return Interface\n"
            "class Dynamic(make_base()): pass\n"
            "@make_base()\n"
            "def decorated(): pass\n"
            "def factory(arg=registry.register(Service)): pass\n"
            "def uncertain(Service):\n"
            "    registry.register(Service)\n"
            "class Enclosing:\n"
            "    class Local: pass\n"
            "    def method(self):\n"
            "        registry.register(Local)\n"
            "class Invalid(make_base): pass\n"
        ),
    }.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    model = scan_repository(tmp_path)
    symbols = {symbol.qualified_name: symbol for symbol in model.symbols if symbol.kind != "package"}
    service = symbols["pkg.service.Service"]
    assert any(item.relationship_type == "IMPLEMENTS" and item.source_id == service.id for item in model.relationships)
    assert any(item.relationship_type == "INHERITS" and item.target_id == "unresolved:python:make_base()" for item in model.relationships)
    assert any(item.relationship_type == "DECORATES" and item.source_id == "unresolved:python:make_base()" for item in model.relationships)
    registrations = [item for item in model.relationships if item.relationship_type == "REGISTERS"]
    assert {item.target_id for item in registrations} == {
        service.id, "unresolved:python:Service", "unresolved:python:Local",
    }
    assert any(item.relationship_type == "INHERITS" and item.target_id == "unresolved:python:make_base" for item in model.relationships)
    assert any(item.relationship_type == "EXPORTS" and item.target_id == symbols["pkg.service"].id for item in model.relationships)


def test_artifact_architecture_and_hub_use_relationship_evidence(tmp_path):
    repo = tmp_path / "repo"
    for path, content in {
        "services/base.py": "class Base:\n    pass\n",
        "controllers/main.py": "from services.base import Base\nclass Controller(Base):\n    pass\n",
        "controllers/__init__.py": "from .main import Controller\n",
        "tests/test_controller.py": "from controllers.main import Controller\ndef test_controller():\n    assert Controller\n",
    }.items():
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    model = scan_repository(repo)
    architecture = extract_architecture(model)
    assert any(item.type == "AST inherits" and "controllers/main.py:2" in " ".join(item.evidence) for item in architecture.relationships)
    assert "controllers/__init__.py" in architecture.public_api_entry_points
    assert all(
        not kind.startswith("AST ")
        for flow in architecture.execution_flows for path in flow["paths"] for kind in path["relationship_types"]
    )
    out = tmp_path / "output"
    run_onboarding(repo, out)
    knowledge = (out / "repository_knowledge.json").read_bytes()
    assert knowledge == (out / "repository_symbols.json").read_bytes()
    artifact = json.loads(knowledge)
    assert all(key in artifact for key in ("symbols", "relationships", "imports", "inheritance", "implementations", "decorators", "registrations", "tests", "exports"))
    assert artifact["inheritance"] and artifact["exports"] and artifact["tests"]
    assert all(item in artifact["relationships"] for item in artifact["inheritance"])
    hub = json.loads((out / "knowledge_hub.json").read_text())
    assert {"repository_knowledge.json", "repository_symbols.json"} <= set(hub["artifacts"])
    assert hub["symbol_relationships"]["inheritance"]["count"] == len(artifact["inheritance"])
    assert hub["symbol_relationships"]["exports"]["items"][0]["evidence"][0]["path"] == "controllers/__init__.py"
    html = (out / "knowledge_hub.html").read_text()
    assert 'href="repository_knowledge.json"' in html
    assert 'href="repository_symbols.json"' in html
    assert "Symbol Relationship Evidence" in html
    assert "not runtime activation or test coverage" in html
    assert "controllers/main.py:2" in html
