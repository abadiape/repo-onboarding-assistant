"""End-to-end test: run_onboarding produces artifacts + valid SkillResult."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.onboarding_skill import run_onboarding


@pytest.mark.parametrize("module", [False, True])
def test_cli_entrypoint_after_reorganization(tmp_path, module):
    root = Path(__file__).resolve().parent.parent
    repo = tmp_path / "sample"
    repo.mkdir()
    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    out = tmp_path / "generated"
    entrypoint = ["-m", "skills.onboarding_skill"] if module else [
        str(root / "skills" / "onboarding_skill.py")
    ]

    completed = subprocess.run(
        [sys.executable, *entrypoint, str(repo), "--output-dir", str(out)],
        cwd=root if module else tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Repository: sample" in completed.stdout
    assert (out / "manifest.json").is_file()
    assert json.loads((out / "repository_map.json").read_text())["repository_name"] == "sample"


def test_skill_entrypoint_loads_by_file_path(tmp_path):
    entrypoint = Path(__file__).resolve().parent.parent / "skills" / "onboarding_skill.py"
    code = (
        "import importlib.util, sys; "
        "spec = importlib.util.spec_from_file_location('onboarding_skill', sys.argv[1]); "
        "module = importlib.util.module_from_spec(spec); "
        "spec.loader.exec_module(module); "
        "assert callable(module.run_onboarding)"
    )
    subprocess.run([sys.executable, "-c", code, str(entrypoint)], cwd=tmp_path, check=True)


def test_run_onboarding_end_to_end(tmp_path):
    repo = tmp_path / "sample"
    (repo / "src").mkdir(parents=True)
    (repo / "README.md").write_text("# Sample\n", encoding="utf-8")
    (repo / "package.json").write_text(
        '{"dependencies":{"react":"^18"},"scripts":{"build":"tsc","test":"jest"}}',
        encoding="utf-8",
    )
    (repo / "tsconfig.json").write_text("{}", encoding="utf-8")
    (repo / "src" / "index.ts").write_text("console.log(1)\n", encoding="utf-8")

    out = tmp_path / "outputs"
    result = run_onboarding(repo, out)

    assert result.summary == "Repository onboarding analysis completed"
    expected_artifacts = (
        "summary.md",
        "learning_path.md",
        "repository_map.json",
        "architecture_summary.md",
        "architecture_map.json",
        "business_domains.md",
        "business_capabilities.md",
        "onboarding_priorities.md",
        "domain_map.json",
        "executive_summary.md",
        "critical_modules.md",
        "first_week_onboarding.md",
        "business_insights.md",
        "business_story.md",
        "critical_workflows.md",
        "first_week_story.md",
        "repository_story.md",
        "business_risk_story.md",
        "first_day_briefing.md",
        "system_overview.mmd",
        "execution_flow.mmd",
        "subsystem_map.mmd",
        "dashboard.html",
        "manifest.json",
    )
    assert len(result.artifacts) == len(expected_artifacts)
    for expected in expected_artifacts:
        assert (out / expected).is_file(), f"missing {expected}"
    first_week = (out / "first_week_onboarding.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^## Day \d:", first_week, re.MULTILINE)) == 5
    story = (out / "business_story.md").read_text(encoding="utf-8")
    assert "## What This System Does" in story
    assert "## Core Business Flow" in story
    assert "## Primary Domains" in story
    assert "## Critical Integrations" in story
    assert "## What Matters Most" in story
    workflows = (out / "critical_workflows.md").read_text(encoding="utf-8")
    assert "Onboarding significance" in workflows or "No actionable business capability" in workflows
    first_week_story = (out / "first_week_story.md").read_text(encoding="utf-8")
    assert len(re.findall(r"^## Day \d:", first_week_story, re.MULTILINE)) == 5
    briefing = (out / "first_day_briefing.md").read_text(encoding="utf-8")
    assert "## 1. What This Repository Appears to Do" in briefing
    assert "## 5. Recommended Learning Sequence" in briefing
    assert len(briefing.split()) < 500

    repo_map = json.loads((out / "repository_map.json").read_text(encoding="utf-8"))
    assert repo_map["repository_name"] == "sample"
    assert "TypeScript" in repo_map["languages"]
    assert repo_map["metadata"]["name"] == "sample"
    assert repo_map["directories"] == ["src"]
    assert any(item["path"] == "package.json" for item in repo_map["files"])
    assert any(item["name"] == "react" for item in repo_map["dependencies"])
    assert "manifest:package.json" in repo_map["detected_patterns"]
    assert "`react` `^18`" in (out / "summary.md").read_text(encoding="utf-8")

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert "generated_at" in manifest
    assert {artifact["name"] for artifact in manifest["artifacts"]} == set(expected_artifacts)
    assert {
        artifact["name"]: artifact["type"] for artifact in manifest["artifacts"]
    }["architecture_summary.md"] == "markdown"
    assert {
        artifact["name"]: artifact["type"] for artifact in manifest["artifacts"]
    }["architecture_map.json"] == "json"
    assert all(
        artifact["type"] == "mermaid"
        for artifact in manifest["artifacts"]
        if artifact["name"].endswith(".mmd")
    )
    assert {
        "business_story.md",
        "critical_workflows.md",
        "first_week_story.md",
        "repository_story.md",
        "business_risk_story.md",
        "first_day_briefing.md",
    } <= {artifact["name"] for artifact in manifest["artifacts"]}
    dashboard = (out / "dashboard.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in dashboard.lower()
    assert "Repository Overview" in dashboard
    assert "Detected Languages" in dashboard
    assert "Frameworks" in dashboard
    assert "Dependencies" in dashboard
    assert "Generated Mermaid Diagrams" in dashboard
    assert "Learning Path" in dashboard
    assert "Summary" in dashboard
    assert "Main Components" in dashboard
    assert "flowchart TD" in dashboard
    assert "sequenceDiagram" in dashboard
    assert 'class="mermaid"' in dashboard
    assert "View Source" in dashboard
    assert "Copy Mermaid" in dashboard
    architecture_map = json.loads((out / "architecture_map.json").read_text(encoding="utf-8"))
    assert {"components", "responsibilities", "relationships", "entry_points", "detected_patterns"} <= set(architecture_map)
    assert "# Architecture Overview" in (out / "architecture_summary.md").read_text(encoding="utf-8")
    dashboard_artifact = next(
        artifact for artifact in manifest["artifacts"]
        if artifact["name"] == "dashboard.html"
    )
    assert dashboard_artifact["type"] == "html"


def test_onboarding_writes_discovered_relationships_to_artifacts(tmp_path):
    repo = tmp_path / "shop"
    (repo / "src/controllers").mkdir(parents=True)
    (repo / "src/services").mkdir()
    (repo / "src/controllers/orders.py").write_text(
        "from src.services.orders import OrderService\n"
        "class OrderController:\n"
        "    def __init__(self, service: OrderService):\n"
        "        self.service = service\n",
        encoding="utf-8",
    )
    (repo / "src/services/orders.py").write_text(
        "class OrderService:\n    pass\n", encoding="utf-8"
    )
    out = tmp_path / "generated"
    run_onboarding(repo, out)

    architecture = json.loads((out / "architecture_map.json").read_text(encoding="utf-8"))
    controller = next(item for item in architecture["components"] if item["name"] == "Controllers")
    assert 0 < controller["confidence"] <= 1
    assert 0 < controller["relevance"] <= 1
    assert 0 < controller["significance"] <= 1
    assert architecture["layers"]
    assert any("src/controllers" in item for item in controller["evidence"])
    assert "src/controllers" in controller["locations"]
    relation = next(
        item for item in architecture["relationships"]
        if item["source"] == "component_controllers"
        and item["target"] == "component_services"
        and item["type"] == "imports"
    )
    assert 0 < relation["confidence"] <= 1
    assert any("src/controllers/orders.py:1" in item for item in relation["evidence"])
    assert any(
        item["source"] == "component_controllers"
        and item["target"] == "component_services"
        and item["type"] == "depends on"
        and any("src/controllers/orders.py:3" in evidence for evidence in item["evidence"])
        for item in architecture["relationships"]
    )
    overview = (out / "system_overview.mmd").read_text(encoding="utf-8")
    assert "component_controllers -->|imports| component_services" in overview
    assert "conceptual" in (out / "execution_flow.mmd").read_text(encoding="utf-8").lower()


def test_large_framework_repository_aggregates_and_supports_module_drilldown(tmp_path):
    repo = tmp_path / "commerce"
    repo.mkdir()
    (repo / "README.md").write_text("# Commerce\n\nA custom commerce application.\n", encoding="utf-8")
    (repo / "composer.json").write_text(json.dumps({
        "require": {"magento/product-community-edition": "^2", "symfony/console": "^7"},
    }), encoding="utf-8")
    packages = (
        [{"name": f"magento/module-{i}", "version": "1"} for i in range(35)]
        + [{"name": f"symfony/component-{i}", "version": "1"} for i in range(17)]
        + [{"name": f"partner/extension-{i}", "version": "1"} for i in range(22)]
    )
    (repo / "composer.lock").write_text(json.dumps({"packages": packages}), encoding="utf-8")
    for index in range(30):
        area = repo / "app" / "code" / "Company" / f"Module{index:02}"
        for layer, name in (("Controller", "OrderController"), ("Service", "OrderService"), ("Observer", "EventObserver")):
            target = area / layer / f"{name}.php"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f"<?php\nclass {name} {{}}\n", encoding="utf-8")
    theme = repo / "app/design/frontend/Company/shop"
    theme.mkdir(parents=True)
    (theme / "theme.xml").write_text("<theme/>", encoding="utf-8")
    vendor = repo / "vendor" / "noisy" / "package"
    vendor.mkdir(parents=True)
    (vendor / "composer.json").write_text('{"require":{"bogus/noise":"1"}}', encoding="utf-8")
    (vendor / "NoiseController.php").write_text("<?php class NoiseController {}", encoding="utf-8")
    generated = repo / "generated" / "services"
    generated.mkdir(parents=True)
    (generated / "HugeService.php").write_text("<?php class HugeService {}", encoding="utf-8")

    out = tmp_path / "out"
    run_onboarding(repo, out)
    repository = json.loads((out / "repository_map.json").read_text(encoding="utf-8"))
    architecture = json.loads((out / "architecture_map.json").read_text(encoding="utf-8"))
    assert "Magento" in repository["frameworks"]
    assert "vendor" in repository["directories"]
    assert not any(item["path"].startswith(("vendor/", "generated/")) for item in repository["files"])
    assert not any(item["name"] == "bogus/noise" for item in repository["dependencies"])
    relevance = architecture["repository_relevance"]
    assert "vendor" in relevance["paths"]["low"]
    assert "generated" in relevance["origins"]["generated"]
    assert len([area for area in relevance["areas"] if area["kind"] == "custom module"]) == 30
    assert not any(component["name"].startswith("Module") for component in architecture["components"])
    assert any(area["kind"] == "theme" for area in relevance["areas"])
    groups = {item["name"]: set(item["packages"]) for item in relevance["dependency_groups"]}
    assert len(groups["magento packages"]) == 36
    assert len(groups["symfony packages"]) == 18
    assert len(groups["partner packages"]) == 22
    assert next(item for item in relevance["dependency_groups"] if item["name"] == "magento packages")["origin"] == "framework"
    assert "bogus/noise" not in set().union(*groups.values())
    assert not any(
        location.startswith(("vendor/", "generated/"))
        for component in architecture["components"] for location in component["locations"]
    )
    for name in ("system_overview.mmd", "subsystem_map.mmd"):
        graph = (out / name).read_text(encoding="utf-8")
        assert len(re.findall(r'^\s+\w+\["', graph, re.MULTILINE)) <= 15
    assert "Custom Modules (30)" in (out / "system_overview.mmd").read_text(encoding="utf-8")
    assert "Module00" in (out / "subsystem_map.mmd").read_text(encoding="utf-8")
    dashboard = (out / "dashboard.html").read_text(encoding="utf-8")
    assert "Project-owned modules and business areas" in dashboard
    assert "Vendor and third-party code" in dashboard
    assert "magento packages" in dashboard and "36 distinct packages" in dashboard
    assert dashboard.index('id="summary"') < dashboard.index('id="dependencies"')
    assert not (out / "module_graph.mmd").exists()

    run_onboarding(repo, out, module_graph="app/code/Company/Module00")
    module = (out / "module_graph.mmd").read_text(encoding="utf-8")
    assert "Module00" in module and "Controllers" in module and "Services" in module
    assert "Module01" not in module
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert any(item["name"] == "module_graph.mmd" for item in manifest["artifacts"])
    with pytest.raises(ValueError, match="Unknown module"):
        run_onboarding(repo, tmp_path / "invalid", module_graph="vendor/noisy/package")


def test_monorepo_areas_and_scoped_lockfile_packages_are_distinct(tmp_path):
    repo = tmp_path / "workspace"
    for name in ("checkout", "catalog"):
        area = repo / "packages" / name
        area.mkdir(parents=True)
        (area / "package.json").write_text('{"dependencies":{"shared-lib":"1"}}', encoding="utf-8")
        (area / "index.ts").write_text("export const value = 1;\n", encoding="utf-8")
    dotnet = repo / "services" / "billing" / "src"
    dotnet.mkdir(parents=True)
    (dotnet / "Billing.csproj").write_text("<Project/>", encoding="utf-8")
    (repo / "package-lock.json").write_text(json.dumps({
        "packages": {
            "": {},
            "node_modules/@scope/a": {"version": "1"},
            "node_modules/@scope/b": {"version": "1"},
            "packages/checkout/node_modules/@scope/a": {"version": "2"},
        },
    }), encoding="utf-8")
    out = tmp_path / "out"
    run_onboarding(repo, out)
    architecture = json.loads((out / "architecture_map.json").read_text(encoding="utf-8"))
    relevance = architecture["repository_relevance"]
    assert {area["name"] for area in relevance["areas"] if area["kind"] == "workspace module"} == {"checkout", "catalog", "billing"}
    assert any(area["path"] == "services/billing" for area in relevance["areas"])
    group = next(group for group in relevance["dependency_groups"] if group["name"] == "@scope packages")
    assert set(group["packages"]) == {"@scope/a", "@scope/b"}
    assert "Workspace Modules (3)" in (out / "system_overview.mmd").read_text(encoding="utf-8")
