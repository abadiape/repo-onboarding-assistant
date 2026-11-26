import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from onboarding_skill import run_onboarding


def test_domain_discovery_outputs_and_business_first_learning_path(tmp_path):
    repo = tmp_path / "commerce"
    (repo / "README.md").parent.mkdir(parents=True)
    (repo / "README.md").write_text(
        "# Commerce\n\nCustomer registration, product search, and order processing.\n",
        encoding="utf-8",
    )
    stale_outputs = repo / "outputs"
    stale_outputs.mkdir()
    (stale_outputs / "previous_domains.md").write_text(
        "Loyalty rewards points Customer Rewards\n",
        encoding="utf-8",
    )
    (repo / "docs").mkdir()
    (repo / "docs" / "business-glossary.md").write_text(
        "Loyalty rewards points are documented as a future concept.\n",
        encoding="utf-8",
    )
    (repo / "composer.json").write_text(json.dumps({
        "require": {
            "magento/product-community-edition": "^2",
            "stripe/stripe-php": "^10",
        },
    }), encoding="utf-8")
    (repo / "vendor" / "partner").mkdir(parents=True)
    (repo / "generated").mkdir()
    for module in (
        "ABCVisa",
        "AttributeOrder",
        "AttributeLongDescription",
        "AdRendering",
        "AttrAccountCreate",
        "ErpSync",
        *(f"AttributeAddon{index:02}" for index in range(12)),
    ):
        module_dir = repo / "app" / "code" / "Company" / module / "etc"
        module_dir.mkdir(parents=True)
        (module_dir / "module.xml").write_text("<config/>", encoding="utf-8")

    out = tmp_path / "generated"
    result = run_onboarding(repo, out)

    domain_map = json.loads((out / "domain_map.json").read_text(encoding="utf-8"))
    domains = {item["name"]: item for item in domain_map["domains"]}
    assert {"Payments", "Catalog", "Marketing", "Customer Experience", "ERP Integrations"} <= set(domains)
    assert "Loyalty" in domains
    assert "docs/business-glossary.md" in domains["Loyalty"]["evidence"]
    assert not any(path.startswith("outputs/") for path in domains["Loyalty"]["evidence"])
    assert "ABCVisa" in domains["Payments"]["modules"]
    assert "AttributeOrder" in domains["Catalog"]["modules"]
    assert "Company" == next(
        item["owner"] for item in domain_map["custom_modules"] if item["name"] == "ABCVisa"
    )
    assert any("Stripe" in item["name"] for item in domain_map["integrations"])
    assert {"vendor", "generated"} <= set(domain_map["deferred_areas"])
    assert {"Customer Registration", "Product Search"} <= {
        item["name"] for item in domain_map["capabilities"]
    }
    business_insights = domain_map["business_insights"]
    payment_score = next(
        item for item in business_insights["domain_impacts"]
        if item["name"] == "Payments"
    )
    assert 0 < payment_score["confidence"] <= 1
    assert payment_score["business_impact"] == "High"
    assert payment_score["onboarding_importance"] == "Very High"
    loyalty_score = next(
        item for item in business_insights["domain_impacts"]
        if item["name"] == "Loyalty"
    )
    assert loyalty_score["business_impact"] == "Low"
    assert loyalty_score["onboarding_importance"] == "Low"
    loyalty_capability = next(
        item for item in business_insights["capabilities"]
        if item["name"] == "Customer Loyalty"
    )
    assert loyalty_capability["priority"] == "low"

    expected_artifacts = {
        "business_domains.md",
        "business_capabilities.md",
        "onboarding_priorities.md",
        "domain_map.json",
        "executive_summary.md",
        "critical_modules.md",
        "first_week_onboarding.md",
        "business_insights.md",
    }
    assert expected_artifacts <= {artifact.name for artifact in result.artifacts}
    domain_markdown = (out / "business_domains.md").read_text(encoding="utf-8")
    assert "## Payments — High priority" in domain_markdown
    assert "`ABCVisa`" in domain_markdown
    capabilities = (out / "business_capabilities.md").read_text(encoding="utf-8")
    assert "Stripe (payment service)" in capabilities
    assert "External system" in capabilities
    priorities = (out / "onboarding_priorities.md").read_text(encoding="utf-8")
    assert "one-week focus" in priorities
    assert "business-critical integrations" in priorities
    assert len(priorities.split("## Defer initially", 1)[1].splitlines()) < 20
    module_focus = priorities.split("## Focus 2:", 1)[1].split("## Focus 3:", 1)[0]
    assert "ABCVisa" in module_focus
    assert "AttributeAddon" not in module_focus

    executive_summary = (out / "executive_summary.md").read_text(encoding="utf-8")
    assert "Where business value appears concentrated" in executive_summary
    assert len(executive_summary.split()) < 300
    critical_modules = (out / "critical_modules.md").read_text(encoding="utf-8")
    assert "## Business Critical" in critical_modules
    assert "### ABCVisa" in critical_modules
    assert critical_modules.count("### ") <= 10
    assert "additional modules are omitted" in critical_modules
    first_week = (out / "first_week_onboarding.md").read_text(encoding="utf-8")
    assert "## Day 1:" in first_week and "## Day 5:" in first_week
    assert "Trace a critical integration" in first_week
    insights_markdown = (out / "business_insights.md").read_text(encoding="utf-8")
    assert "Confidence estimates how much repository evidence" in insights_markdown

    learning_path = (out / "learning_path.md").read_text(encoding="utf-8")
    assert "## Step 1: Understand the business domains" in learning_path
    assert "## Step 2: Review custom application modules" in learning_path
    assert "AttributeAddon" not in learning_path
    assert learning_path.index("Understand the business domains") < learning_path.index(
        "Learn the framework layout"
    )
