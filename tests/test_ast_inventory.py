import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzers.architecture_analyzer import extract_architecture
from analyzers.ast.parser import ParseResult
from analyzers.ast.registry import ParserRegistry
from analyzers.ast.resolver import collect_symbols
from analyzers.repository_scan import scan_repository
from models.models import RepositoryModel
from skills.onboarding_skill import run_onboarding


FIXTURE = Path(__file__).parent / "fixtures" / "ast_repo"


def test_python_inventory_resolves_imports_and_preserves_scopes(caplog):
    with caplog.at_level(logging.WARNING):
        model = scan_repository(FIXTURE)
    symbols = {symbol.qualified_name: symbol for symbol in model.symbols if symbol.kind != "package"}
    nested = symbols["pkg.service.Service.Nested"]
    method = symbols["pkg.service.Service.Nested.run"]
    inner = symbols["pkg.service.Service._helper.inner"]
    assert nested.kind == "class"
    assert method.kind == "method" and method.parent_symbol_id == nested.id
    assert inner.kind == "function" and inner.visibility == "public"
    assert symbols["pkg.service.Service._helper"].visibility == "private"
    assert (method.start_line, method.end_line) == (10, 11)
    assert method.evidence[0].path == "pkg/service.py"
    assert method.evidence[0].line == 10 and method.evidence[0].column == 8
    assert method.evidence[0].extract.strip() == "async def run(self):"
    assert "pkg.broken" in symbols
    assert "pkg/broken.py" in caplog.text

    imports = [relation for relation in model.relationships if relation.relationship_type == "IMPORTS"]
    pairs = {(rel.source_id, rel.target_id) for rel in imports}
    service = symbols["pkg.service"]
    assert (service.id, symbols["pkg.models"].id) in pairs
    assert (service.id, symbols["pkg.models.Order"].id) in pairs
    assert (method.id, symbols["pkg.models"].id) in pairs
    assert (service.id, "unresolved:python:missing_dependency.unknown") in pairs
    assert (service.id, "unresolved:python:os") in pairs
    assert all(rel.direct_observation and rel.evidence[0].detector == "python-ast" for rel in imports)
    assert any(rel.relationship_type == "DECLARES" and rel.target_id == method.id for rel in model.relationships)
    package = next(symbol for symbol in model.symbols if symbol.kind == "package")
    assert any(rel.relationship_type == "CONTAINS" and rel.source_id == package.id for rel in model.relationships)
    assert RepositoryModel.from_dict(model.to_dict()).to_dict() == model.to_dict()
    assert RepositoryModel.from_dict({"repository_name": "old"}).symbols == []


def test_unresolved_and_ambiguous_imports_do_not_guess(tmp_path):
    for path, content in {
        "first/shared.py": "",
        "second/shared.py": "",
        "main.py": "import shared\nfrom .first import shared\nfrom nowhere import Missing\n",
        "unrelated.py": "def os():\n    pass\n",
        "another.py": "import os\n",
    }.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    model = scan_repository(tmp_path)
    imports = [rel for rel in model.relationships if rel.relationship_type == "IMPORTS"]
    assert {rel.target_id for rel in imports} == {
        "unresolved:python:shared", "unresolved:python:.first.shared",
        "unresolved:python:nowhere.Missing",
        "unresolved:python:os",
    }


def test_parser_registry_supports_other_languages(tmp_path):
    class ExampleParser:
        language = "Example"
        extensions = (".example",)

        def parse(self, root, path):
            return ParseResult()

    registry = ParserRegistry((ExampleParser(),))
    assert registry.for_path("sample.example").language == "Example"
    assert registry.for_path("sample.py") is None
    assert collect_symbols(tmp_path, [], registry) == ([], [])


def test_relative_imports_package_hierarchy_and_source_root(tmp_path):
    for path, content in {
        "src/pkg/__init__.py": "",
        "src/pkg/sub/__init__.py": "from .. import models\n",
        "src/pkg/sub/consumer.py": (
            "from ..models import Thing as Alias\n"
            "from ...outside import value\n"
            "import pkg.models\n"
        ),
        "src/pkg/models.py": "class Thing:\n    pass\n",
    }.items():
        file = tmp_path / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    model = scan_repository(tmp_path)
    symbols = {item.id: item for item in model.symbols}
    imports = [item for item in model.relationships if item.relationship_type == "IMPORTS"]
    assert {symbols[item.target_id].qualified_name for item in imports if item.target_id in symbols} == {
        "src.pkg.models", "src.pkg.models.Thing",
    }
    assert any(item.target_id == "unresolved:python:...outside.value" for item in imports)
    packages = {item.qualified_name: item for item in model.symbols if item.kind == "package"}
    assert packages["src.pkg.sub"].parent_symbol_id == packages["src.pkg"].id
    assert any(
        item.relationship_type == "CONTAINS"
        and item.source_id == packages["src.pkg"].id
        and item.target_id == packages["src.pkg.sub"].id
        for item in model.relationships
    )


def test_ast_relationships_enhance_lexical_architecture_and_artifacts(tmp_path):
    repo = tmp_path / "repo"
    for path, content in {
        "controllers/main.py": "from services import (\n    worker,\n)\n",
        "services/worker.py": "def work():\n    pass\n",
        "controllers/other.py": "import services.worker\n",
    }.items():
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content, encoding="utf-8")
    model = scan_repository(repo)
    architecture = extract_architecture(model)
    imports = [relation for relation in architecture.relationships if relation.type == "imports"]
    evidence = [item for relation in imports for item in relation.evidence]
    assert any("controllers/main.py:1 (AST import" in item for item in evidence)
    assert any("controllers/other.py:1 (import" in item for item in evidence)

    out = tmp_path / "output"
    run_onboarding(repo, out)
    inventory = json.loads((out / "repository_symbols.json").read_text())
    repository = json.loads((out / "repository_map.json").read_text())
    assert inventory == {key: repository[key] for key in ("symbols", "relationships")}
    assert any(rel["relationship_type"] == "IMPORTS" for rel in inventory["relationships"])
    manifest = json.loads((out / "manifest.json").read_text())
    assert any(item["name"] == "repository_symbols.json" for item in manifest["artifacts"])
