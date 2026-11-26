"""Skill entrypoint: scan a repository and generate onboarding artifacts.

Usage:
    python skills/onboarding_skill.py /path/to/repository [--output-dir outputs]
    python skills/onboarding_skill.py /path/to/repository -o /tmp/my-output

Produces (in the output dir):
    summary.md, learning_path.md, repository_map.json, architecture artifacts,
    dashboard.html, and manifest.json

Returns a harness SkillResult with registered Artifacts.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analyzers.architecture_analyzer import (
    extract_architecture,
    render_architecture_map_json,
    render_architecture_summary_markdown,
    render_execution_flow_mermaid,
    render_module_graph_mermaid,
    render_subsystem_map_mermaid,
    render_system_overview_mermaid,
)
from analyzers.business_insights import (
    analyze_business_insights,
    render_business_insights_markdown,
    render_critical_modules_markdown,
    render_executive_summary_markdown,
    render_first_week_onboarding_markdown,
)
from analyzers.narrative_generation import (
    generate_business_narrative,
    render_business_story_markdown,
    render_business_risk_story_markdown,
    render_critical_workflows_markdown,
    render_first_day_briefing_markdown,
    render_first_week_story_markdown,
    render_repository_story_markdown,
)
from artifacts.dashboard import render_dashboard_html
from artifacts.knowledge_hub import build_knowledge_hub, render_knowledge_hub_html
from analyzers.domain_discovery import (
    analyze_domains,
    domain_learning_steps,
    render_business_capabilities_markdown,
    render_business_domains_markdown,
    render_onboarding_priorities_markdown,
)
from models.models import RepositoryModel
from analyzers.onboarding_analyzer import (
    analyze_inventory,
    render_learning_path_markdown,
    render_summary_markdown,
)
from analyzers.repository_scan import scan_repository

try:
    from llm_harness_lite import Artifact, ArtifactRegistry, ArtifactType, SkillResult
except ImportError:  # Fallback so the skill logic stays testable without the harness
    from enum import Enum

    class ArtifactType(str, Enum):
        MARKDOWN = "markdown"
        JSON = "json"
        MERMAID = "mermaid"
        HTML = "html"

    class Artifact:  # type: ignore[no-redef]
        def __init__(self, name, type, path, description="", metadata=None):
            self.name = name
            self.type = type
            self.path = path
            self.description = description
            self.metadata = metadata or {}

        def to_dict(self):
            t = self.type.value if isinstance(self.type, ArtifactType) else self.type
            return {"name": self.name, "type": t, "path": str(self.path),
                    "description": self.description, "metadata": self.metadata}

    class SkillResult:  # type: ignore[no-redef]
        def __init__(self, summary, artifacts=None):
            self.summary = summary
            self.artifacts = artifacts or []

    class ArtifactRegistry:  # type: ignore[no-redef]
        def __init__(self):
            self._artifacts = []

        def register(self, artifact):
            self._artifacts.append(artifact)
            return artifact

        def list_artifacts(self):
            return list(self._artifacts)

        def export_manifest(self, path="outputs/manifest.json"):
            from datetime import datetime, timezone

            manifest_path = Path(path)
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "artifacts": [a.to_dict() for a in self._artifacts],
            }
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            return manifest_path


def run_onboarding(
    repo_path: str | Path, output_dir: str | Path = "outputs", *, module_graph: str | None = None
) -> SkillResult:
    """Run the full onboarding skill and return a harness SkillResult."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    model: RepositoryModel = scan_repository(repo_path)
    architecture = extract_architecture(model)
    domains = analyze_domains(model, architecture)
    business_insights = analyze_business_insights(architecture, domains)
    insights = analyze_inventory(model, architecture)
    top_domain_names = [
        item.name for item in business_insights.domain_impacts
        if item.onboarding_importance in {"Very High", "High"}
    ][:5]
    top_module_names = [
        item.name for item in business_insights.ranked_modules
        if item.tier != "Supporting"
    ][:3]
    top_capability_names = [
        item.name for item in business_insights.capabilities
        if item.priority != "low"
    ][:5]
    insights.learning_path = domain_learning_steps(
        domains,
        top_domain_names=top_domain_names,
        top_module_names=top_module_names,
        top_capability_names=top_capability_names,
    ) + insights.learning_path
    for step in insights.learning_path:
        if step["title"] == "Explore project-owned areas" and top_module_names:
            step["detail"] = (
                "Start with " + ", ".join(f"`{name}`" for name in top_module_names)
                + "; consult `domain_map.json` for the full area inventory."
            )
    for index, step in enumerate(insights.learning_path, 1):
        step["step"] = index
    summary_md = render_summary_markdown(model, insights)
    learning_md = render_learning_path_markdown(model, insights)
    business_domains_md = render_business_domains_markdown(domains, insights=business_insights)
    business_capabilities_md = render_business_capabilities_markdown(domains)
    onboarding_priorities_md = render_onboarding_priorities_markdown(
        domains,
        top_domain_names=top_domain_names,
        top_module_names=top_module_names,
        top_capability_names=top_capability_names,
    )
    executive_summary_md = render_executive_summary_markdown(
        architecture, business_insights
    )
    critical_modules_md = render_critical_modules_markdown(business_insights)
    first_week_onboarding_md = render_first_week_onboarding_markdown(business_insights)
    business_insights_md = render_business_insights_markdown(business_insights)
    narrative = generate_business_narrative(architecture, domains, business_insights)
    business_story_md = render_business_story_markdown(narrative)
    critical_workflows_md = render_critical_workflows_markdown(narrative)
    first_week_story_md = render_first_week_story_markdown(narrative)
    repository_story_md = render_repository_story_markdown(narrative)
    business_risk_story_md = render_business_risk_story_markdown(narrative)
    first_day_briefing_md = render_first_day_briefing_markdown(narrative)
    architecture_summary_md = render_architecture_summary_markdown(architecture)
    diagrams = {
        "system_overview.mmd": render_system_overview_mermaid(architecture),
        "execution_flow.mmd": render_execution_flow_mermaid(architecture),
        "subsystem_map.mmd": render_subsystem_map_mermaid(architecture),
    }
    if module_graph is not None:
        diagrams["module_graph.mmd"] = render_module_graph_mermaid(architecture, module_graph)

    summary_path = out / "summary.md"
    learning_path_path = out / "learning_path.md"
    repo_map_path = out / "repository_map.json"
    architecture_summary_path = out / "architecture_summary.md"
    architecture_map_path = out / "architecture_map.json"
    business_domains_path = out / "business_domains.md"
    business_capabilities_path = out / "business_capabilities.md"
    onboarding_priorities_path = out / "onboarding_priorities.md"
    executive_summary_path = out / "executive_summary.md"
    critical_modules_path = out / "critical_modules.md"
    first_week_onboarding_path = out / "first_week_onboarding.md"
    business_insights_path = out / "business_insights.md"
    business_story_path = out / "business_story.md"
    critical_workflows_path = out / "critical_workflows.md"
    first_week_story_path = out / "first_week_story.md"
    repository_story_path = out / "repository_story.md"
    business_risk_story_path = out / "business_risk_story.md"
    first_day_briefing_path = out / "first_day_briefing.md"
    domain_map_path = out / "domain_map.json"
    dashboard_path = out / "dashboard.html"
    knowledge_hub_path = out / "knowledge_hub.json"
    knowledge_hub_html_path = out / "knowledge_hub.html"

    summary_path.write_text(summary_md, encoding="utf-8")
    learning_path_path.write_text(learning_md, encoding="utf-8")
    repo_map_path.write_text(
        json.dumps(model.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    architecture_summary_path.write_text(architecture_summary_md, encoding="utf-8")
    architecture_map_path.write_text(
        render_architecture_map_json(architecture), encoding="utf-8"
    )
    business_domains_path.write_text(business_domains_md, encoding="utf-8")
    business_capabilities_path.write_text(business_capabilities_md, encoding="utf-8")
    onboarding_priorities_path.write_text(onboarding_priorities_md, encoding="utf-8")
    executive_summary_path.write_text(executive_summary_md, encoding="utf-8")
    critical_modules_path.write_text(critical_modules_md, encoding="utf-8")
    first_week_onboarding_path.write_text(first_week_onboarding_md, encoding="utf-8")
    business_insights_path.write_text(business_insights_md, encoding="utf-8")
    business_story_path.write_text(business_story_md, encoding="utf-8")
    critical_workflows_path.write_text(critical_workflows_md, encoding="utf-8")
    first_week_story_path.write_text(first_week_story_md, encoding="utf-8")
    repository_story_path.write_text(repository_story_md, encoding="utf-8")
    business_risk_story_path.write_text(business_risk_story_md, encoding="utf-8")
    first_day_briefing_path.write_text(first_day_briefing_md, encoding="utf-8")
    domain_map_path.write_text(
        json.dumps(
            {
                "repository_name": model.repository_name,
                **domains.to_dict(),
                "business_insights": business_insights.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    diagram_paths = {}
    for name, content in diagrams.items():
        diagram_path = out / name
        diagram_path.write_text(content, encoding="utf-8")
        diagram_paths[name] = diagram_path
    dashboard_path.write_text(
        render_dashboard_html(model, insights, architecture_summary_md, diagrams, architecture),
        encoding="utf-8",
    )
    artifact_names = [
        "summary.md", "learning_path.md", "repository_map.json",
        "architecture_summary.md", "architecture_map.json", "business_domains.md",
        "business_capabilities.md", "onboarding_priorities.md", "domain_map.json",
        "executive_summary.md", "critical_modules.md", "first_week_onboarding.md",
        "business_insights.md", "business_story.md", "critical_workflows.md",
        "first_week_story.md", "repository_story.md", "business_risk_story.md",
        "first_day_briefing.md", *diagrams, "dashboard.html", "knowledge_hub.json",
        "manifest.json",
    ]
    hub = build_knowledge_hub(model, architecture, domains, business_insights, narrative, artifact_names)
    knowledge_hub_path.write_text(
        json.dumps(hub, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    knowledge_hub_html_path.write_text(render_knowledge_hub_html(hub), encoding="utf-8")

    registry = ArtifactRegistry()
    registry.register(Artifact(
        name="summary.md", type=ArtifactType.MARKDOWN, path=str(summary_path),
        description="Repository overview in Markdown.",
    ))
    registry.register(Artifact(
        name="learning_path.md", type=ArtifactType.MARKDOWN, path=str(learning_path_path),
        description="Step-by-step suggested onboarding path.",
    ))
    registry.register(Artifact(
        name="repository_map.json", type=ArtifactType.JSON, path=str(repo_map_path),
        description="Structured RepositoryModel for the scanned repository.",
    ))
    registry.register(Artifact(
        name="architecture_summary.md",
        type=ArtifactType.MARKDOWN,
        path=str(architecture_summary_path),
        description="Onboarding-focused explanation of the inferred system architecture.",
    ))
    registry.register(Artifact(
        name="architecture_map.json",
        type=ArtifactType.JSON,
        path=str(architecture_map_path),
        description="Machine-readable architecture components and relationships.",
    ))
    registry.register(Artifact(
        name="business_domains.md",
        type=ArtifactType.MARKDOWN,
        path=str(business_domains_path),
        description="Business domains, related custom modules, and evidence.",
    ))
    registry.register(Artifact(
        name="business_capabilities.md",
        type=ArtifactType.MARKDOWN,
        path=str(business_capabilities_path),
        description="Business capabilities and inferred external ownership boundaries.",
    ))
    registry.register(Artifact(
        name="onboarding_priorities.md",
        type=ArtifactType.MARKDOWN,
        path=str(onboarding_priorities_path),
        description="Business-focused onboarding priorities and areas to defer initially.",
    ))
    registry.register(Artifact(
        name="domain_map.json",
        type=ArtifactType.JSON,
        path=str(domain_map_path),
        description="Machine-readable domains, capabilities, integrations, and priorities.",
    ))
    for name, path, description in (
        (
            "executive_summary.md",
            executive_summary_path,
            "Concise business-value summary and recommended initial focus.",
        ),
        (
            "critical_modules.md",
            critical_modules_path,
            "Top-ranked custom modules with domain ownership, impact, and rationale.",
        ),
        (
            "first_week_onboarding.md",
            first_week_onboarding_path,
            "Five-day onboarding plan focused on business domains and critical workflows.",
        ),
        (
            "business_insights.md",
            business_insights_path,
            "Evidence-based business impact and onboarding recommendations.",
        ),
        (
            "business_story.md",
            business_story_path,
            "Narrative explanation of the inferred business purpose, flow, and priorities.",
        ),
        (
            "critical_workflows.md",
            critical_workflows_path,
            "Capability-based workflow guides with domains, modules, and onboarding significance.",
        ),
        (
            "first_week_story.md",
            first_week_story_path,
            "Narrative five-day learning sequence based on discovered business priorities.",
        ),
        (
            "repository_story.md",
            repository_story_path,
            "Repository-specific explanation of business flows, domains, and customizations.",
        ),
        (
            "business_risk_story.md",
            business_risk_story_path,
            "Heuristic onboarding sensitivity narrative for directly supported business areas.",
        ),
        (
            "first_day_briefing.md",
            first_day_briefing_path,
            "Concise first-day introduction to this repository's business areas and learning order.",
        ),
    ):
        registry.register(Artifact(
            name=name,
            type=ArtifactType.MARKDOWN,
            path=str(path),
            description=description,
        ))
    mermaid_type = getattr(ArtifactType, "MERMAID", "mermaid")
    for name, diagram_path in diagram_paths.items():
        registry.register(Artifact(
            name=name, type=mermaid_type, path=str(diagram_path),
            description=f"Mermaid visualization generated from ArchitectureModel: {name}.",
        ))
    registry.register(Artifact(
        name="dashboard.html",
        type=getattr(ArtifactType, "HTML", "html"),
        path=str(dashboard_path),
        description="Standalone onboarding dashboard with embedded model artifacts.",
    ))
    registry.register(Artifact(
        name="knowledge_hub.json", type=ArtifactType.JSON, path=str(knowledge_hub_path),
        description="Aggregated structured onboarding knowledge.",
    ))
    registry.register(Artifact(
        name="knowledge_hub.html", type=getattr(ArtifactType, "HTML", "html"),
        path=str(knowledge_hub_html_path),
        description="Portable Knowledge Hub for repository onboarding.",
    ))

    # Register the manifest after the first export, then re-export so it
    # lists itself along with the generated artifacts.
    manifest_path = out / "manifest.json"
    registry.export_manifest(manifest_path)
    registry.register(Artifact(
        name="manifest.json", type=ArtifactType.JSON, path=str(manifest_path),
        description="Artifact manifest generated by ArtifactRegistry.",
    ))
    registry.export_manifest(manifest_path)

    result = SkillResult(
        summary="Repository onboarding analysis completed",
        artifacts=registry.list_artifacts(),
    )

    print(f"Repository: {model.repository_name}")
    print(f"Languages: {', '.join(model.languages) or 'none detected'}")
    print(f"Frameworks: {', '.join(model.frameworks) or 'none detected'}")
    print(f"Start with: {knowledge_hub_html_path.resolve()}")
    print(f"Artifacts written to {out.resolve()}:")
    for artifact in result.artifacts:
        print(f"  - {artifact.name} ({artifact.path})")

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="repo-onboarding-assistant",
        description="Analyze a source repository and generate onboarding artifacts.",
    )
    parser.add_argument("repository", help="Path to the repository to analyze")
    parser.add_argument("-o", "--output-dir", default="outputs",
                        help="Directory for generated artifacts (default: outputs)")
    parser.add_argument("--module-graph", metavar="PATH",
                        help="Also generate a module graph for a detected repository-relative area")
    args = parser.parse_args(argv)

    try:
        run_onboarding(args.repository, args.output_dir, module_graph=args.module_graph)
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
