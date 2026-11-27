"""Classify repository purpose from bounded, attributable lexical evidence."""
from __future__ import annotations

import json
import re
from pathlib import Path

from models.models import RepositoryModel
from models.repository_archetype import ArchetypeCandidate, ArchetypeResult, RepositoryArchetype as A
from analyzers.repository_relevance import relevant_model


def _sources(model: RepositoryModel) -> list[tuple[str, str]]:
    sources = [("Repository name", model.repository_name), ("README summary", model.readme_summary)]
    if not model.root_path:
        return sources
    root = Path(model.root_path)
    for name in ("README.md", "README.rst", "README", "pyproject.toml", "package.json", "composer.json"):
        path = root / name
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")[:16000]
        except OSError as exc:
            raise OSError(f"Could not read archetype evidence from {path}: {exc}") from exc
        if name.endswith(".json"):
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue
            text = " ".join(str(data.get(key, "")) for key in ("name", "description", "type"))
        elif name == "pyproject.toml":
            project = re.search(r"(?ms)^\[project\]\s*$((?:(?!^\[).*\n?)*)", text)
            text = "\n".join(re.findall(r"(?m)^\s*(?:name|description)\s*=.*$", project.group(1) if project else ""))
        else:
            text = re.split(r"(?m)^##\s+", text, maxsplit=1)[0]
        sources.append((name, text))
    return sources


def analyze_repository_archetype(model: RepositoryModel) -> ArchetypeResult:
    """Return bounded heuristic scores, not calibrated probabilities."""
    scores: dict[A, float] = {}
    evidence: dict[A, list[str]] = {}
    seen: dict[A, list[tuple[str, str]]] = {}

    def add(kind: A, weight: float, description: str) -> None:
        scores[kind] = scores.get(kind, 0.0) + weight
        evidence.setdefault(kind, []).append(description)

    patterns = [
        (A.BUSINESS_APPLICATION, r"\b(?:magento|mage-os|mageos)\b", 0.75),
        (A.BUSINESS_APPLICATION, r"\b(?:e-?commerce|commerce (?:platform|application)|online store|shopping cart)\b", 0.55),
        (A.DEVELOPER_TOOL, r"\b(?:repository|source code|codebase)\b.{0,80}\b(?:scan|analy[sz]|onboard|inventory)", 0.6),
        (A.DEVELOPER_TOOL, r"\b(?:developer tool|development tool|static analys[ie]s|repository scanner)\b", 0.55),
        (A.FRAMEWORK, r"\b(?:web|application|api|python)\s+framework\b|\bframework\s+for\b", 0.65),
        (A.LIBRARY, r"\b(?:http client|http library|python library|client library|library for)\b", 0.65),
        (A.SDK, r"\b(?:sdk|software development kit)\b", 0.65),
        (A.CLI_TOOL, r"\b(?:command[- ]line (?:tool|interface|utility)|cli tool)\b", 0.6),
        (A.AI_AGENT_PLATFORM, r"\b(?:agent(?:ic)?\s+(?:platform|framework|harness|runtime)|(?:llm|ai)\s+harness|universal agent)\b", 0.7),
        (A.DATA_PIPELINE, r"\b(?:data pipeline|etl pipeline|data ingestion pipeline)\b", 0.65),
        (A.INFRASTRUCTURE, r"\b(?:infrastructure as code|terraform module|deployment infrastructure)\b", 0.65),
    ]
    for source, text in _sources(model):
        for kind, pattern, weight in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                # Multiple documents often repeat the same description.
                if not any(pattern == entry[0] for entry in seen.setdefault(kind, [])):
                    seen[kind].append((pattern, source))
                    add(kind, weight, f"{source}: {match.group(0)[:120].strip()}")
    magento = next(
        (dependency for dependency in model.dependencies
         if dependency.name.casefold().startswith("magento/product-")),
        None,
    )
    if magento:
        add(A.BUSINESS_APPLICATION, 0.75, f"{magento.source}: {magento.name}")
    for framework in model.frameworks:
        if model.repository_name.casefold() == framework.casefold() and framework.casefold() != "magento":
            add(A.FRAMEWORK, 0.35, f"Repository name matches detected framework {framework}")
    relevant = relevant_model(model)
    paths = [item.path for item in relevant.files] + relevant.directories
    lowered = [path.casefold() for path in paths]
    if any("app/code/magento/" in p or "app/etc/di.xml" in p for p in lowered):
        add(A.BUSINESS_APPLICATION, 0.5, "Magento application layout detected")
    if any(re.search(r"(?:^|/)(?:analyzers|scanners)(?:/|$)", p) for p in lowered):
        add(A.DEVELOPER_TOOL, 0.2, "Analyzer or scanner directory detected")
    if any(re.search(r"(?:^|/)(?:agent|agents)(?:/|$)", p) for p in lowered) and any(
        re.search(r"(?:^|/)(?:tools|skills|registry)(?:/|$)", p) for p in lowered
    ):
        add(A.AI_AGENT_PLATFORM, 0.3, "Agent and tool/skill structure detected")
    if not scores:
        return ArchetypeResult()
    ranked = sorted(scores, key=lambda kind: (-scores[kind], kind.value))
    winner = ranked[0]
    return ArchetypeResult(
        archetype=winner,
        confidence=round(min(scores[winner], 0.95), 2),
        evidence=evidence[winner],
        alternatives=[ArchetypeCandidate(kind, round(min(scores[kind], 0.95), 2)) for kind in ranked[1:]],
    )
