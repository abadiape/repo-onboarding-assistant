"""Harness compatibility and onboarding artifact registration."""
from __future__ import annotations

import json
from pathlib import Path

__all__ = ["Artifact", "ArtifactRegistry", "ArtifactType", "SkillResult", "register_artifacts"]


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
                # timezone.utc also works on Python 3.10.
                "generated_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
                "artifacts": [a.to_dict() for a in self._artifacts],
            }
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            return manifest_path


def register_artifacts(out: Path, diagram_paths: dict[str, Path]) -> ArtifactRegistry:
    registry = ArtifactRegistry()
    registry.register(Artifact(
        name="summary.md", type=ArtifactType.MARKDOWN, path=str(out / "summary.md"),
        description="Repository overview in Markdown.",
    ))
    registry.register(Artifact(
        name="learning_path.md", type=ArtifactType.MARKDOWN, path=str(out / "learning_path.md"),
        description="Step-by-step suggested onboarding path.",
    ))
    registry.register(Artifact(
        name="repository_map.json", type=ArtifactType.JSON, path=str(out / "repository_map.json"),
        description="Structured RepositoryModel for the scanned repository.",
    ))
    registry.register(Artifact(
        name="architecture_summary.md",
        type=ArtifactType.MARKDOWN,
        path=str(out / "architecture_summary.md"),
        description="Onboarding-focused explanation of the inferred system architecture.",
    ))
    registry.register(Artifact(
        name="architecture_map.json",
        type=ArtifactType.JSON,
        path=str(out / "architecture_map.json"),
        description="Machine-readable architecture components and relationships.",
    ))
    registry.register(Artifact(
        name="business_domains.md",
        type=ArtifactType.MARKDOWN,
        path=str(out / "business_domains.md"),
        description="Business domains, related custom modules, and evidence.",
    ))
    registry.register(Artifact(
        name="business_capabilities.md",
        type=ArtifactType.MARKDOWN,
        path=str(out / "business_capabilities.md"),
        description="Business capabilities and inferred external ownership boundaries.",
    ))
    registry.register(Artifact(
        name="onboarding_priorities.md",
        type=ArtifactType.MARKDOWN,
        path=str(out / "onboarding_priorities.md"),
        description="Business-focused onboarding priorities and areas to defer initially.",
    ))
    registry.register(Artifact(
        name="domain_map.json",
        type=ArtifactType.JSON,
        path=str(out / "domain_map.json"),
        description="Machine-readable domains, capabilities, integrations, and priorities.",
    ))
    for name, path, description in (
        (
            "executive_summary.md",
            (out / "executive_summary.md"),
            "Concise business-value summary and recommended initial focus.",
        ),
        (
            "critical_modules.md",
            (out / "critical_modules.md"),
            "Top-ranked custom modules with domain ownership, impact, and rationale.",
        ),
        (
            "first_week_onboarding.md",
            (out / "first_week_onboarding.md"),
            "Five-day onboarding plan focused on business domains and critical workflows.",
        ),
        (
            "business_insights.md",
            (out / "business_insights.md"),
            "Evidence-based business impact and onboarding recommendations.",
        ),
        (
            "business_story.md",
            (out / "business_story.md"),
            "Narrative explanation of the inferred business purpose, flow, and priorities.",
        ),
        (
            "critical_workflows.md",
            (out / "critical_workflows.md"),
            "Capability-based workflow guides with domains, modules, and onboarding significance.",
        ),
        (
            "first_week_story.md",
            (out / "first_week_story.md"),
            "Narrative five-day learning sequence based on discovered business priorities.",
        ),
        (
            "repository_story.md",
            (out / "repository_story.md"),
            "Repository-specific explanation of business flows, domains, and customizations.",
        ),
        (
            "business_risk_story.md",
            (out / "business_risk_story.md"),
            "Heuristic onboarding sensitivity narrative for directly supported business areas.",
        ),
        (
            "first_day_briefing.md",
            (out / "first_day_briefing.md"),
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
        path=str(out / "dashboard.html"),
        description="Standalone onboarding dashboard with embedded model artifacts.",
    ))
    registry.register(Artifact(
        name="knowledge_hub.json", type=ArtifactType.JSON, path=str(out / "knowledge_hub.json"),
        description="Aggregated structured onboarding knowledge.",
    ))
    registry.register(Artifact(
        name="knowledge_hub.html", type=getattr(ArtifactType, "HTML", "html"),
        path=str(out / "knowledge_hub.html"),
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

    return registry
