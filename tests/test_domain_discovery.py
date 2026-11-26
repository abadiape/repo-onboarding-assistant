import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from skills.onboarding_skill import run_onboarding
from analyzers.business_insights import (
    analyze_business_insights,
    render_executive_summary_markdown,
    render_first_week_onboarding_markdown,
)
from analyzers.domain_discovery import BusinessDomain, CustomModule, DomainDiscovery
from models.architecture_model import ArchitectureModel


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
        "OPSStock",
        "HomeDelivery",
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
    assert payment_score["business_impact"] == "Critical"
    assert payment_score["onboarding_importance"] == "Very High"
    assert payment_score["starting_module"] == "ABCVisa"
    assert payment_score["learning_recommendation"]
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
        "business_story.md",
        "critical_workflows.md",
        "first_week_story.md",
        "repository_story.md",
        "business_risk_story.md",
        "first_day_briefing.md",
    }
    assert expected_artifacts <= {artifact.name for artifact in result.artifacts}
    domain_markdown = (out / "business_domains.md").read_text(encoding="utf-8")
    assert "## Payments — High priority" in domain_markdown
    assert "`ABCVisa`" in domain_markdown
    payment_section = domain_markdown.split("## Payments", 1)[1].split("\n## ", 1)[0]
    assert all(label in payment_section for label in (
        "**Description:**", "**Why it matters:**", "**Business impact:** Critical",
        "**Suggested starting module:** `ABCVisa`", "**Learning recommendation:**",
        "**Suggested learning order:**", "<details>", "Supporting evidence",
    ))
    assert payment_section.index("**Why it matters:**") < payment_section.index("<details>")
    assert "app/code/Company/ABCVisa" in payment_section
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
    assert "vendor or generated code" in executive_summary
    assert "ErpSync" in executive_summary and "OPSStock" in executive_summary
    critical_modules = (out / "critical_modules.md").read_text(encoding="utf-8")
    assert "## Business Critical" in critical_modules
    assert "### ABCVisa" in critical_modules
    assert "**Recommendation:**" in critical_modules
    assert "`app/code/Company/ABCVisa`" in critical_modules
    assert critical_modules.count("### ") <= 10
    assert "additional modules are omitted" in critical_modules
    first_week = (out / "first_week_onboarding.md").read_text(encoding="utf-8")
    assert "## Day 1:" in first_week and "## Day 5:" in first_week
    assert "Trace a critical integration" in first_week
    assert "Magento architecture" in first_week
    assert all(name in first_week for name in ("Payments", "Orders", "ERP Integrations", "Inventory"))
    insights_markdown = (out / "business_insights.md").read_text(encoding="utf-8")
    assert "Confidence estimates how much repository evidence" in insights_markdown
    business_story = (out / "business_story.md").read_text(encoding="utf-8")
    assert "ABCVisa" in business_story
    assert "Payments" in business_story
    assert "ERP Integrations" in business_story
    assert "## How Domains Connect" in business_story
    assert "Catalog ↔ Search" in business_story
    workflows = (out / "critical_workflows.md").read_text(encoding="utf-8")
    assert "Payment Authorization" in workflows
    assert "Involved domains:** Payments" in workflows
    assert "Involved modules:** `ABCVisa`" in workflows
    first_week_story = (out / "first_week_story.md").read_text(encoding="utf-8")
    assert len(first_week_story.split("## Day ")) == 6
    assert "Understand Payments" in first_week_story
    repository_story = (out / "repository_story.md").read_text(encoding="utf-8")
    assert "## What Makes This Repository Different" in repository_story
    assert "## How Value Moves Through The System" in repository_story
    assert "## Most Important Customizations" in repository_story
    assert "`ABCVisa`" in repository_story
    assert "`ErpSync`" in repository_story
    assert "`OPSStock`" in repository_story
    risk_story = (out / "business_risk_story.md").read_text(encoding="utf-8")
    assert "onboarding prioritization" in risk_story
    assert "Payments" in risk_story and "`ABCVisa`" in risk_story

    learning_path = (out / "learning_path.md").read_text(encoding="utf-8")
    assert "## Step 1: Understand the business domains" in learning_path
    assert "## Step 2: Review custom application modules" in learning_path
    assert "AttributeAddon" not in learning_path
    assert learning_path.index("Understand the business domains") < learning_path.index(
        "Learn the framework layout"
    )


def test_impact_is_separate_from_confidence_and_module_rank_covers_domains():
    architecture = ArchitectureModel("Shop", "application", "", frameworks=["Magento"])
    discovery = DomainDiscovery(
        domains=[
            BusinessDomain("Payments", "high", ["Handles payments."], ["MailAfterPayment", "ABCVisa"],
                           ["app/code/Company/ABCVisa"]),
            BusinessDomain("Inventory", "high", ["Tracks stock."], ["OPSStock"],
                           ["app/code/Company/OPSStock"]),
            BusinessDomain("Catalog", "high", ["Manages products."], ["Catalog"],
                           ["catalog/a.py", "catalog/b.py", "catalog/c.py"]),
            BusinessDomain("Loyalty", "medium", ["Rewards customers."], [], ["README.md"]),
        ],
        custom_modules=[
            CustomModule(name, f"app/code/Company/{name}", "custom module")
            for name in ("MailAfterPayment", "ABCVisa", "OPSStock", "Catalog")
        ],
    )

    insights = analyze_business_insights(architecture, discovery)
    impacts = {item.name: item for item in insights.domain_impacts}
    assert impacts["Catalog"].confidence > impacts["Payments"].confidence
    assert impacts["Catalog"].business_impact == "Medium"
    assert impacts["Payments"].business_impact == "Critical"
    assert impacts["Loyalty"].business_impact == "Low"
    assert impacts["Loyalty"].starting_module is None
    assert impacts["Payments"].learning_order == ["ABCVisa", "MailAfterPayment"]
    assert [module.name for module in insights.ranked_modules[:2]] == ["ABCVisa", "OPSStock"]
    week = render_first_week_onboarding_markdown(insights)
    assert week.count("## Day ") == 5
    assert "Magento architecture" in week
    assert "None" not in week


def test_erp_domain_guidance_does_not_invent_external_service():
    architecture = ArchitectureModel("Shop", "application", "")
    discovery = DomainDiscovery(
        domains=[BusinessDomain("ERP Integrations", "high", ["Synchronizes orders."],
                                ["ErpSync"], ["app/code/Company/ErpSync"])],
        custom_modules=[CustomModule("ErpSync", "app/code/Company/ErpSync", "custom module")],
    )
    insights = analyze_business_insights(architecture, discovery)
    assert not insights.critical_integrations
    week = render_first_week_onboarding_markdown(insights)
    assert "Trace the external ERP boundary" in week
    summary = render_executive_summary_markdown(architecture, insights)
    assert "no specific business-critical external service was identified" in summary
