"""Evidence-linked technical onboarding topics for non-business repositories."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from analyzers.repository_relevance import classify_path, relevant_model
from models.models import RepositoryModel
from models.repository_archetype import RepositoryArchetype as A


_TOPICS: dict[A, list[tuple[str, str]]] = {
    A.AI_AGENT_PLATFORM: [
        ("Core Concepts", r"agent|llm|model"),
        ("Execution Model", r"runtime|execution|loop|agent"),
        ("Skills", r"skill"),
        ("Artifact System", r"artifacts?|outputs?|result"),
        ("Capabilities", r"capabilit|tools?|registry"),
        ("Extension Points", r"plugins?|extensions?|providers?|registry|tools?"),
    ],
    A.DEVELOPER_TOOL: [
        ("Repository Analysis", r"scan|analy[sz]|repository"),
        ("Onboarding Pipeline", r"onboarding|pipeline|skill"),
        ("Generated Artifacts", r"artifacts?|outputs?|render|dashboard"),
        ("Execution Flow", r"entry|(?:^|[_./-])(?:main|cli)(?:[_./-]|$)|skill"),
        ("Customization Points", r"plugins?|extensions?|analy[sz]|templates?"),
    ],
    A.FRAMEWORK: [
        ("Core Abstractions", r"applications?|framework|routing|dependencies"),
        ("Request Lifecycle", r"requests?|routing|middleware|responses?"),
        ("Extension Points", r"plugins?|extensions?|dependencies|middleware"),
    ],
    A.LIBRARY: [
        ("Public APIs", r"api|__init__|client|sessions?"),
        ("Usage Patterns", r"examples?|quickstart|usage|\bimport\s+\w+|\b(?:get|post|put)\s*\("),
        ("Integration Points", r"adapters?|auth|client|integrations?"),
    ],
    A.SDK: [
        ("Public APIs", r"api|client|__init__"),
        ("Usage Patterns", r"examples?|usage|client"),
        ("Integration Points", r"auth|client|transport|integration"),
    ],
    A.CLI_TOOL: [
        ("Commands", r"(?:^|[_./-])(?:cli|main)(?:[_./-]|$)|commands?"),
        ("Execution Flow", r"entry|(?:^|[_./-])(?:main|cli)(?:[_./-]|$)"),
        ("Customization Points", r"config|plugins?|extensions?"),
    ],
    A.INFRASTRUCTURE: [
        ("Configuration", r"config|terraform|deploy"),
        ("Provisioning", r"terraform|modules?|deploy"),
        ("Integration Points", r"providers?|integration|config"),
    ],
    A.DATA_PIPELINE: [
        ("Inputs", r"source|input|ingest"),
        ("Processing", r"pipeline|transform|process"),
        ("Outputs", r"output|sink|export"),
    ],
    A.UNKNOWN: [("Repository Structure", r".")],
}


@dataclass
class TechnicalTopic:
    title: str
    evidence: list[str]


def technical_topics(model: RepositoryModel, archetype: A) -> list[TechnicalTopic]:
    relevant = relevant_model(model)
    paths = sorted(
        {path for path in relevant.directories + [item.path for item in relevant.files if item.kind == "source"]
         if "outputs" not in Path(path).parts},
        key=lambda path: (classify_path(path)[0] != "high", path.count("/"), len(path), path.casefold()),
    )
    documents: list[tuple[str, list[str]]] = []
    if model.root_path:
        for path in relevant.onboarding_docs[:12]:
            try:
                text = (Path(model.root_path) / path).read_text(encoding="utf-8", errors="replace")[:12000]
            except OSError as exc:
                raise OSError(f"Could not read onboarding evidence from {path}: {exc}") from exc
            documents.append((path, text.splitlines()))
    topics = []
    for title, pattern in _TOPICS.get(archetype, _TOPICS[A.UNKNOWN]):
        matches = [path for path in paths if re.search(pattern, Path(path).name, re.IGNORECASE)][:3]
        for path, lines in documents:
            match = next((i for i, line in enumerate(lines, 1) if re.search(pattern, line, re.IGNORECASE)), None)
            if match:
                matches.append(f"{path}:{match}")
                break
        if matches:
            topics.append(TechnicalTopic(title, matches))
    return topics


def repository_purpose(model: RepositoryModel, fallback: str) -> str:
    """Prefer a project description over README badges or HTML fragments."""
    for source, text in _purpose_sources(model):
        if source.startswith("README"):
            introduction = re.split(r"(?m)^##\s+", text, maxsplit=1)[0]
            for line in introduction.splitlines():
                line = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", line).replace("**", "").strip()
                if (re.match(r"^[A-Z][\w -]+ is (?:a|an)\b", line)
                        and not re.match(r"^(?:It|This|That|There)\b", line)
                        and len(line) <= 400):
                    return line
        if source == "pyproject.toml":
            match = re.search(r'(?m)^\s*description\s*=\s*["\']([^"\']+)', text)
            if match:
                return match.group(1).strip()
        if source.endswith(".json"):
            import json
            try:
                description = json.loads(text).get("description")
            except json.JSONDecodeError:
                continue
            if isinstance(description, str) and description.strip():
                return description.strip()
    summary = model.readme_summary.strip()
    if summary and not any(marker in summary for marker in ("<", "![", "[![")):
        summary = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", summary)
        if len(summary) > 240:
            summary = re.split(r"(?<=[.!?])\s+", summary, maxsplit=1)[0]
        return summary
    return fallback or f"Explore {model.repository_name} using its repository evidence."


def _purpose_sources(model: RepositoryModel) -> list[tuple[str, str]]:
    sources = []
    if model.root_path:
        for name in ("README.md", "README.rst", "README", "pyproject.toml", "package.json", "composer.json"):
            path = Path(model.root_path) / name
            if path.is_file():
                try:
                    sources.append((name, path.read_text(encoding="utf-8", errors="replace")[:16000]))
                except OSError as exc:
                    raise OSError(f"Could not read repository description from {path}: {exc}") from exc
    return sources


def technical_plan(
    archetype: A, topics: list[TechnicalTopic],
    public_api_entry_points: list[str] | None = None,
) -> list[dict[str, str]]:
    if archetype == A.AI_AGENT_PLATFORM:
        order = ["Core Concepts", "Execution Model", "Artifact System", "Capabilities", "Extension Points", "Skills"]
        topics = sorted(topics, key=lambda topic: order.index(topic.title) if topic.title in order else len(order))
    plan = [
        {"title": topic.title, "detail": "Review " + ", ".join(f"`{path}`" for path in topic.evidence) + "; confirm its role with a maintainer."}
        for topic in topics[:5]
    ]
    fallback = [
        ("Architecture", "Review the architecture map and trace a representative execution path."),
        ("Repository purpose", "Read the README and identify the intended users and primary use cases."),
        ("Integration boundaries", "Review the declared dependencies and confirm external interfaces."),
        ("Verification", "Run the documented tests and review how changes are validated."),
        ("First change", "Choose a small change and confirm its behavior with the relevant tests."),
    ]
    for title, detail in fallback:
        if len(plan) >= 5:
            break
        plan.append({"title": title, "detail": detail})
    if public_api_entry_points:
        plan[0]["detail"] += (
            " Read " + ", ".join(f"`{path}`" for path in public_api_entry_points)
            + " to understand the package's public API and re-exports."
        )
    return plan


def technical_markdown(title: str, purpose: str, topics: list[TechnicalTopic], plan: list[dict[str, str]]) -> str:
    lines = [f"# {title}", "", purpose, "", "Findings are heuristic; confirm responsibilities and runtime behavior with maintainers.", ""]
    for topic in topics:
        lines += [f"## {topic.title}", "", "Starting points: " + ", ".join(f"`{path}`" for path in topic.evidence) + ".", ""]
    if plan:
        lines += ["## Learning sequence", ""]
        for index, step in enumerate(plan, 1):
            lines += [f"## Day {index}: {step['title']}", "", step["detail"], ""]
    return "\n".join(lines)
