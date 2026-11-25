"""Onboarding Analyzer — heuristic insights built on RepositoryInventory.

No LLM calls, no AST parsing. Pure convention-based heuristics so the
skill stays small, deterministic, and easy to extend.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from models import RepositoryInventory


@dataclass
class OnboardingInsights:
    summary: str
    main_technologies: list[str] = field(default_factory=list)
    learning_path: list[dict] = field(default_factory=list)
    files_to_read_first: list[str] = field(default_factory=list)
    build_instructions: list[str] = field(default_factory=list)
    test_instructions: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


def analyze_inventory(inv: RepositoryInventory) -> OnboardingInsights:
    techs = [*inv.languages, *inv.frameworks]
    if inv.package_managers:
        techs.append(f"managed with {', '.join(inv.package_managers)}")

    if techs:
        summary = (
            f"`{inv.repository_name}` is a "
            f"{'/'.join(inv.languages) if inv.languages else 'multi-file'} project"
            + (f" using {', '.join(inv.frameworks)}" if inv.frameworks else "")
            + "."
        )
    else:
        summary = (
            f"`{inv.repository_name}` has no recognized language manifests. "
            "It may be documentation, config, or a polyglot/experimental layout — "
            "start from the README and top-level directories."
        )

    if inv.readme_summary:
        summary += f" README description: {inv.readme_summary}"

    if inv.top_level_directories:
        summary += f" Top-level areas: {', '.join(inv.top_level_directories[:8])}."
    if inv.entry_points:
        summary += f" Likely entry point(s): {', '.join(inv.entry_points[:3])}."

    files_first = _files_to_read_first(inv)
    learning_path = _learning_path(inv, files_first)
    open_questions = _open_questions(inv)

    return OnboardingInsights(
        summary=summary.strip(),
        main_technologies=techs,
        learning_path=learning_path,
        files_to_read_first=files_first,
        build_instructions=list(inv.build_instructions),
        test_instructions=list(inv.test_instructions),
        open_questions=open_questions,
    )


def _files_to_read_first(inv: RepositoryInventory) -> list[str]:
    """Order important files by onboarding value: docs first, then manifests."""
    priority_order = [
        "readme.md", "readme.rst", "readme",
        "local_setup.md", "setup.md", "getting_started.md",
        "development.md", "dev_setup.md", "install.md",
        "contributing.md", "contributing.rst",
        "changelog.md", "changelog.rst",
        "package.json", "pyproject.toml", "requirements.txt",
        "composer.json", "go.mod", "cargo.toml",
        "pom.xml", "build.gradle",
        "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "makefile",
    ]

    def rank(path: str) -> tuple:
        base = path.split("/")[-1].lower()
        try:
            return (priority_order.index(base), path)
        except ValueError:
            return (99, path)

    ordered = sorted(set(inv.important_files + inv.onboarding_docs), key=rank)
    for entry in inv.entry_points:
        if entry not in ordered:
            ordered.append(entry)
    return ordered[:12]


def _learning_path(inv: RepositoryInventory, files_first: list[str]) -> list[dict]:
    steps: list[dict] = []
    step_no = 1

    def add(title: str, detail: str) -> None:
        nonlocal step_no
        steps.append({"step": step_no, "title": title, "detail": detail})
        step_no += 1

    readmes = [f for f in files_first if "readme" in f.lower()]
    if readmes:
        add("Orient with the README", f"Read {', '.join(readmes)} for purpose, setup, and usage.")
    else:
        add("Look for docs", "No README found — check top-level docs/ or ask a maintainer what this repo does.")

    if inv.setup_guides:
        add(
            "Follow the project setup guide",
            f"Use {', '.join(f'`{path}`' for path in inv.setup_guides)} for project-specific "
            "environment, dependency, and run instructions.",
        )

    if files_first:
        add("Read the key files", "Skim in this order: " + ", ".join(f"`{f}`" for f in files_first[:6]) + ".")
    if inv.top_level_directories:
        add(
            "Tour the structure",
            "Browse " + ", ".join(f"`{d}/`" for d in inv.top_level_directories[:8])
            + " to learn where code, tests, and config live.",
        )
    if inv.frameworks:
        add(
            "Learn the framework layout",
            f"Follow the {', '.join(inv.frameworks)} conventions (routing, config, entry points) "
            "rather than reading every file.",
        )
    if inv.entry_points:
        add("Trace from the entry point", f"Start at {', '.join(f'`{e}`' for e in inv.entry_points[:3])} and follow imports/calls.")
    if inv.build_instructions:
        add("Build the project", "Run: " + " → ".join(f"`{c}`" for c in inv.build_instructions[:4]) + ".")
    if inv.test_instructions:
        add("Run the tests", "Run: " + " → ".join(f"`{c}`" for c in inv.test_instructions[:3]) + " to verify your setup.")
    if inv.ci_cd_files:
        add("Check CI/CD", f"Read {', '.join(f'`{c}`' for c in inv.ci_cd_files[:3])} to see how build/test/deploy run in CI.")
    add("Make a first change", "Pick a small test or doc fix, run the relevant tests, and open a PR.")
    return steps


def _open_questions(inv: RepositoryInventory) -> list[str]:
    questions: list[str] = []
    if not inv.languages:
        questions.append("No language manifests detected — confirm the primary language with a maintainer.")
    if not inv.test_frameworks:
        questions.append("No test framework detected — ask how this project is verified.")
    if not inv.ci_cd_files:
        questions.append("No CI/CD config found — ask how releases/deploys happen.")
    if not inv.important_files:
        questions.append("No README or manifest found — ask where onboarding docs live.")
    return questions


# ---------------------------------------------------------------------------
# Markdown rendering (used for summary.md and learning_path.md artifacts)
# ---------------------------------------------------------------------------

def render_summary_markdown(inv: RepositoryInventory, insights: OnboardingInsights) -> str:
    lines = [
        f"# Repository Overview — {inv.repository_name}",
        "",
        insights.summary,
        "",
        "## Main technologies",
        "",
    ]
    if insights.main_technologies:
        lines += [f"- {t}" for t in insights.main_technologies]
    else:
        lines.append("- _None detected_")
    lines += [
        "",
        "## High-level structure",
        "",
    ]
    if inv.top_level_directories:
        lines += [f"- `{d}/`" for d in inv.top_level_directories]
    else:
        lines.append("- _No subdirectories_")
    lines += ["", "## Recommended files to read first", ""]
    if insights.files_to_read_first:
        for i, f in enumerate(insights.files_to_read_first, 1):
            lines.append(f"{i}. `{f}`")
    else:
        lines.append("_No candidate files found._")
    if inv.onboarding_docs:
        lines += ["", "## Onboarding documentation", ""]
        lines += [f"- `{path}`" for path in inv.onboarding_docs]
    if inv.documented_setup_commands:
        lines += ["", "## Setup commands documented by the project", ""]
        current_source = ""
        for item in inv.documented_setup_commands:
            if item["source"] != current_source:
                current_source = item["source"]
                lines.append(f"- From `{current_source}`:")
            section = f" ({item['section']})" if item["section"] else ""
            lines.append(f"  - `{item['command']}`{section}")
    lines += ["", "## Build / install (inferred from metadata)", ""]
    lines += [f"- `{c}`" for c in insights.build_instructions] or ["- _No build steps detected._"]
    lines += ["", "## Test", ""]
    lines += [f"- `{c}`" for c in insights.test_instructions] or ["- _No test commands detected._"]
    if inv.ci_cd_files:
        lines += ["", "## CI/CD", ""]
        lines += [f"- `{c}`" for c in inv.ci_cd_files]
    if inv.ci_commands:
        lines += ["", "### Commands observed in CI", ""]
        lines += [
            f"- `{item['command']}` — `{item['source']}`"
            for item in inv.ci_commands
        ]
    if insights.open_questions:
        lines += ["", "## Open questions", ""]
        lines += [f"- {q}" for q in insights.open_questions]
    lines.append("")
    return "\n".join(lines)


def render_learning_path_markdown(inv: RepositoryInventory, insights: OnboardingInsights) -> str:
    lines = [
        f"# Learning Path — {inv.repository_name}",
        "",
        "Suggested step-by-step onboarding path for a new developer.",
        "",
    ]
    for step in insights.learning_path:
        lines += [f"## Step {step['step']}: {step['title']}", "", step["detail"], ""]
    files_section = [f"- `{f}`" for f in insights.files_to_read_first] or ["- _None found._"]
    lines += [
        "## Files to read first",
        "",
        *files_section,
        "",
        "## Build & test cheat sheet",
        "",
        "```sh",
        *insights.build_instructions,
        *insights.test_instructions,
        "```",
        "",
    ]
    return "\n".join(lines)
