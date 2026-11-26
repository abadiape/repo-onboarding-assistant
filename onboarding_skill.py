"""Skill entrypoint: scan a repository and generate onboarding artifacts.

Usage:
    python onboarding_skill.py /path/to/repository [--output-dir outputs]
    python onboarding_skill.py /path/to/repository -o /tmp/my-output

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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from architecture_analyzer import (
    extract_architecture,
    render_architecture_map_json,
    render_architecture_summary_markdown,
    render_execution_flow_mermaid,
    render_module_graph_mermaid,
    render_subsystem_map_mermaid,
    render_system_overview_mermaid,
)
from dashboard import render_dashboard_html
from models import RepositoryModel
from onboarding_analyzer import (  # noqa: E402
    analyze_inventory,
    render_learning_path_markdown,
    render_summary_markdown,
)
from repository_scan import scan_repository  # noqa: E402

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
    insights = analyze_inventory(model, architecture)
    summary_md = render_summary_markdown(model, insights)
    learning_md = render_learning_path_markdown(model, insights)
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
    dashboard_path = out / "dashboard.html"

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
    diagram_paths = {}
    for name, content in diagrams.items():
        diagram_path = out / name
        diagram_path.write_text(content, encoding="utf-8")
        diagram_paths[name] = diagram_path
    dashboard_path.write_text(
        render_dashboard_html(model, insights, architecture_summary_md, diagrams, architecture),
        encoding="utf-8",
    )

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
