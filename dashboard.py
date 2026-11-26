"""Self-contained HTML dashboard rendering from onboarding model artifacts."""
from __future__ import annotations

import html
import re

from models import RepositoryModel
from onboarding_analyzer import OnboardingInsights


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _inline_markdown(value: str) -> str:
    escaped = _escape(value)
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)


def _render_markdown(markdown: str) -> str:
    """Render the small Markdown subset used by the generated text artifacts."""
    rendered: list[str] = []
    paragraph: list[str] = []
    list_tag: str | None = None
    code_lines: list[str] | None = None

    def close_list() -> None:
        nonlocal list_tag
        if list_tag:
            rendered.append(f"</{list_tag}>")
            list_tag = None

    def flush_paragraph() -> None:
        if paragraph:
            rendered.append("<p>" + " ".join(paragraph) + "</p>")
            paragraph.clear()

    for line in markdown.splitlines():
        if code_lines is not None:
            if line.startswith("```"):
                rendered.append(
                    "<pre><code>" + _escape("\n".join(code_lines)) + "</code></pre>"
                )
                code_lines = None
            else:
                code_lines.append(line)
            continue

        if line.startswith("```"):
            flush_paragraph()
            close_list()
            code_lines = []
            continue
        if not line.strip():
            flush_paragraph()
            close_list()
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = len(heading.group(1))
            rendered.append(
                f"<h{level}>{_inline_markdown(heading.group(2))}</h{level}>"
            )
            continue

        unordered = re.match(r"^\s*[-*]\s+(.+)$", line)
        ordered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if unordered or ordered:
            flush_paragraph()
            expected_tag = "ul" if unordered else "ol"
            if list_tag != expected_tag:
                close_list()
                rendered.append(f"<{expected_tag}>")
                list_tag = expected_tag
            item = unordered or ordered
            rendered.append(f"<li>{_inline_markdown(item.group(1))}</li>")
            continue

        close_list()
        paragraph.append(_inline_markdown(line.strip()))

    flush_paragraph()
    close_list()
    if code_lines is not None:
        rendered.append("<pre><code>" + _escape("\n".join(code_lines)) + "</code></pre>")
    return "\n".join(rendered)


def _chips(values: list[str], empty_text: str) -> str:
    if not values:
        return f'<p class="empty">{_escape(empty_text)}</p>'
    return '<ul class="chips">' + "".join(
        f"<li>{_escape(value)}</li>" for value in values
    ) + "</ul>"


def _render_dependencies(model: RepositoryModel) -> str:
    if not model.dependencies:
        return '<p class="empty">No declared dependencies.</p>'
    rows = []
    for item in model.dependencies:
        rows.append(
            "<tr>"
            f"<td>{_escape(item.name)}</td>"
            f"<td>{_escape(item.version or '—')}</td>"
            f"<td>{_escape(item.scope)}</td>"
            f"<td>{_escape(item.source)}</td>"
            f"<td>{_escape(item.category)}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Name</th><th>Version</th><th>Scope</th><th>Source</th><th>Category</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )


def _render_diagrams(diagrams: dict[str, str]) -> str:
    sections = []
    for name, source in diagrams.items():
        title = name.removesuffix(".mmd").replace("_", " ").title()
        sections.append(
            "<details>"
            f"<summary>{_escape(title)}</summary>"
            '<pre class="diagram-source"><code>'
            f"{_escape(source)}"
            "</code></pre>"
            "</details>"
        )
    return "\n".join(sections)


def render_dashboard_html(
    model: RepositoryModel,
    insights: OnboardingInsights,
    summary_markdown: str,
    diagrams: dict[str, str],
) -> str:
    """Render a portable dashboard with all content embedded in one HTML file."""
    learning_steps = "".join(
        "<article class=\"step-card\">"
        f'<span class="step-number">{_escape(step["step"])}</span>'
        "<div>"
        f"<h3>{_escape(step['title'])}</h3>"
        f"<p>{_escape(step['detail'])}</p>"
        "</div></article>"
        for step in insights.learning_path
    )
    if not learning_steps:
        learning_steps = '<p class="empty">No learning path steps available.</p>'

    overview = insights.summary or "No repository overview is available."
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{_escape(model.repository_name)} — Onboarding Dashboard</title>
  <style>
    :root {{ color-scheme: light; --ink: #172b4d; --muted: #536579; --line: #dce5ef; --accent: #2867a5; --wash: #f3f7fb; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--wash); color: var(--ink); font: 16px/1.55 system-ui, sans-serif; }}
    header {{ padding: 2.5rem max(1.25rem, calc((100% - 1100px) / 2)); background: #153b5b; color: white; }}
    header p {{ margin: .4rem 0 0; color: #d9e8f4; }}
    h1 {{ margin: 0; font-size: clamp(1.8rem, 4vw, 2.8rem); }}
    nav {{ position: sticky; top: 0; z-index: 1; display: flex; gap: .4rem; overflow-x: auto; padding: .7rem max(1.25rem, calc((100% - 1100px) / 2)); background: white; border-bottom: 1px solid var(--line); }}
    nav a {{ color: var(--accent); white-space: nowrap; text-decoration: none; padding: .3rem .6rem; border-radius: .4rem; }}
    nav a:hover, nav a:focus {{ background: #e7f1fa; }}
    main {{ max-width: 1100px; margin: auto; padding: 1.5rem 1.25rem 4rem; }}
    section {{ margin: 1.25rem 0; padding: clamp(1rem, 3vw, 1.6rem); background: white; border: 1px solid var(--line); border-radius: .8rem; box-shadow: 0 3px 14px #183a5810; scroll-margin-top: 5rem; }}
    h2 {{ margin: 0 0 1rem; font-size: 1.35rem; }}
    h3 {{ margin: .1rem 0 .35rem; font-size: 1rem; }}
    p {{ margin: .35rem 0 .8rem; }}
    .overview {{ font-size: 1.08rem; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: .55rem; margin: 0; padding: 0; list-style: none; }}
    .chips li {{ padding: .4rem .75rem; background: #eaf3fb; color: #194f7a; border: 1px solid #d5e7f6; border-radius: 999px; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; text-align: left; }}
    th, td {{ padding: .65rem .75rem; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--muted); font-size: .85rem; }}
    td:first-child {{ font-weight: 650; }}
    .step-card {{ display: flex; gap: .9rem; padding: 1rem 0; border-top: 1px solid var(--line); }}
    .step-number {{ display: grid; flex: 0 0 2rem; height: 2rem; place-items: center; border-radius: 50%; background: var(--accent); color: white; font-weight: 700; }}
    .step-card p {{ margin: 0; color: var(--muted); }}
    .empty {{ color: var(--muted); font-style: italic; }}
    details {{ border-top: 1px solid var(--line); }}
    summary {{ padding: .85rem 0; color: var(--accent); cursor: pointer; font-weight: 650; }}
    pre {{ overflow-x: auto; margin: 0; padding: 1rem; background: #12263a; color: #e4eff8; border-radius: .5rem; font: .85rem/1.5 ui-monospace, monospace; }}
    code {{ font-family: ui-monospace, monospace; }}
    .summary-content h1, .summary-content h2, .summary-content h3 {{ margin-top: 1.3rem; }}
    .summary-content pre {{ margin: .8rem 0; }}
    @media (max-width: 600px) {{ th, td {{ padding: .5rem; }} }}
  </style>
</head>
<body>
  <header>
    <h1>{_escape(model.repository_name)}</h1>
    <p>Repository onboarding dashboard</p>
  </header>
  <nav aria-label="Dashboard sections">
    <a href="#overview">Overview</a><a href="#languages">Languages</a>
    <a href="#frameworks">Frameworks</a><a href="#dependencies">Dependencies</a>
    <a href="#diagrams">Diagrams</a><a href="#learning-path">Learning Path</a>
    <a href="#summary">Summary</a>
  </nav>
  <main>
    <section id="overview">
      <h2>Repository Overview</h2>
      <p class="overview">{_escape(overview)}</p>
    </section>
    <section id="languages">
      <h2>Detected Languages</h2>
      {_chips(model.languages, "No languages detected.")}
    </section>
    <section id="frameworks">
      <h2>Frameworks</h2>
      {_chips(model.frameworks, "No frameworks detected.")}
    </section>
    <section id="dependencies">
      <h2>Dependencies</h2>
      {_render_dependencies(model)}
    </section>
    <section id="diagrams">
      <h2>Generated Mermaid Diagrams</h2>
      <p class="empty">Mermaid source is embedded below and can be copied into any Mermaid-compatible viewer.</p>
      {_render_diagrams(diagrams)}
    </section>
    <section id="learning-path">
      <h2>Learning Path</h2>
      {learning_steps}
    </section>
    <section id="summary">
      <h2>Summary</h2>
      <div class="summary-content">{_render_markdown(summary_markdown)}</div>
    </section>
  </main>
</body>
</html>
"""
