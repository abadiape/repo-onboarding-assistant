# repo-onboarding-assistant

Analyze an unfamiliar source code repository and generate onboarding artifacts
that help a new developer get oriented quickly.

Built on top of the [LLM Harness Lite](https://github.com/abadiape/llm-harness-lite)
Artifact API (`Artifact`, `ArtifactRegistry`, `ArtifactType`, `SkillResult`).
The skill itself is independent from the harness — no harness changes required.

## MVP scope (answers)

- What language(s) does this repository use?
- What framework(s) does it use?
- What is the high-level structure?
- Where should a new developer start?
- What files are most important?
- How is the project built and tested?

The architecture analyzer adds high-level component views and evidence-backed
relationship heuristics. It uses bounded lexical checks, not AST parsing or
call-graph resolution, and distinguishes direct source evidence from
lower-confidence framework/layout conventions. Confidence scores are
heuristics, not probabilities, and conceptual flows are not runtime traces.

## How it works

1. **Repository Scan Capability** (`analyzers/repository_scan.py`) —
   convention-based inspection of filenames and manifest contents builds a
   `RepositoryModel` (see `models/models.py`): repository metadata, languages,
   frameworks, normalized dependencies, directories, file records, detected
   patterns, and onboarding details. Markdown setup guides are scanned for
   shell commands in relevant fenced code blocks, and CI YAML files are
   checked for inline `run` steps. Commands are reported with their source
   and section and are never executed. `analyzers/analyzers.py` then runs the generic
   analyzer and any applicable Node.js, Python, or PHP analyzer to enrich the
   model with framework, dependency-category, structure, and convention facts.
2. **Onboarding Analyzer** (`analyzers/onboarding_analyzer.py`) — heuristic insights on
   top of the model: summary, main technologies, learning path,
   files-to-read-first, project-specific setup guidance, and build/test cheat
   sheet.
3. **Artifact Generation** (`skills/onboarding_skill.py`) — writes artifacts via
   `ArtifactRegistry` and returns a harness `SkillResult`.
4. **System Architecture Analyzer** (`analyzers/architecture_analyzer.py`) — extracts an
   `ArchitectureModel` from the repository model, framework metadata, layout,
   public API exports, source imports/type references, and listed
   docs/configuration, then generates architecture artifacts from that
   representation. Feature boundaries with multiple layers and uniquely
   matched public modules can also become components. Component confidence
   measures evidence strength; significance combines relevance with graph
   connections, references from prominent components, and conceptual-flow
   position. Significance is High at 0.55 or above, Medium at 0.20 or above,
   otherwise Low. These are heuristic scores, as are relationship confidences.
   Layers group only recognized component roles. Inferred edges are not
   presented as source-level call edges.
5. **Domain Discovery** (`analyzers/domain_discovery.py`) — groups project-owned modules
   and evidence from documentation, source paths, and inferred external
   dependencies into business domains, capabilities, and onboarding priorities.
   The findings are heuristic and complement rather than replace architecture
   analysis; business-focused steps lead the generated learning path.
6. **Business Insights** (`analyzers/business_insights.py`) — separates evidence
   confidence, estimated business impact, and onboarding importance; ranks
   critical modules and integrations; and generates a concise executive
   summary and five-day onboarding plan. Human-readable module lists are capped
   at ten; the domain map retains the full inventory. Scores are heuristic,
   not measured revenue or calibrated probabilities. Documentation-only
   mentions remain low impact without corroborating module, source-path, or
   Architecture Discovery integration evidence.

Repository relevance classifies application, infrastructure, vendor, and
generated paths before architecture inference. Vendor and generated trees are
not traversed. Detected custom modules, themes, workspace packages, and
layered business areas are prioritized in the overview and learning path.
Ownership and framework package grouping use conventions and may be incomplete.
Composer/npm lockfile names are grouped and deduplicated for drill-down; they
indicate declared or locked packages, not necessarily installed packages.

## Usage

```bash
pip install llm-harness-lite pytest
python skills/onboarding_skill.py /path/to/repository
python skills/onboarding_skill.py /path/to/repository --output-dir ./my-output
python skills/onboarding_skill.py /path/to/repository --module-graph app/code/Company/Module
```

Run these commands from the repository root. The module form
`python -m skills.onboarding_skill` is also supported.

The optional `--module-graph` argument must match an area in the architecture
map and produces `module_graph.mmd`. Overview and subsystem diagrams are capped
at 15 nodes; the architecture map and dashboard retain the full area list.

Output (`outputs/` by default):

- `summary.md` — repository overview in Markdown
- `learning_path.md` — step-by-step suggested onboarding path
- `repository_map.json` — serialized `RepositoryModel`
- `architecture_summary.md` — architecture narrative and recommended reading
- `architecture_map.json` — machine-readable components, subsystems, layers,
  responsibilities, relationships with confidence/evidence, entry points,
  integrations, and data stores; components include confidence, significance,
  relevance, evidence, and locations
- `business_domains.md` — inferred domains, responsibilities, related modules,
  priorities, and evidence
- `business_capabilities.md` — business workflows and inferred external
  integration ownership boundaries
- `onboarding_priorities.md` — suggested one-week business-first learning order
- `domain_map.json` — structured domain, capability, integration, module, and
  business-impact data
- `executive_summary.md` — concise business-value summary and recommended focus
- `critical_modules.md` — top ten modules with domain ownership, impact, and rationale
- `first_week_onboarding.md` — five-day actionable onboarding plan
- `business_insights.md` — prioritized business impacts and recommendations
- `system_overview.mmd` — high-level component relationship diagram
- `execution_flow.mmd` — inferred application execution sequence
- `subsystem_map.mmd` — major components grouped by subsystem
- `dashboard.html` — standalone onboarding dashboard with rendered Mermaid
  diagrams and source/copy controls
- `manifest.json` — generated automatically through `ArtifactRegistry`

The dashboard uses a pinned Mermaid.js CDN asset for diagram rendering.
Mermaid source remains embedded and available when the renderer cannot load.
Architecture evidence uses at most 120 model-listed files, up to 24 KB per
file and 400 KB total, prioritizing root README/configuration, entry points,
selected public APIs, and documentation, then interleaving other directories.
Lexical matching and sampled evidence are not exhaustive.
Integrations and data stores require runtime dependency, top-level import, or
recognized runtime configuration evidence; optional/development dependencies,
profile-gated Compose services, example and development configuration, and
disabled YAML sections and documentation-only mentions are excluded. These
signals are not proof of an active deployment.

The skill returns:

```python
SkillResult(
    summary="Repository onboarding analysis completed",
    artifacts=[...],  # summary.md, learning_path.md, repository_map.json,
                      # architecture_summary.md, architecture_map.json,
                      # business_domains.md, business_capabilities.md,
                      # onboarding_priorities.md, domain_map.json,
                      # executive_summary.md, critical_modules.md,
                      # first_week_onboarding.md, business_insights.md,
                      # system_overview.mmd, execution_flow.mmd,
                      # subsystem_map.mmd, dashboard.html, manifest.json
)
```

## Detection rules (convention-based, no AST)

| Signal | Language / Framework |
|---|---|
| `pyproject.toml`, `requirements.txt` | Python |
| `package.json` | Node.js / JavaScript |
| `tsconfig.json` | TypeScript |
| `composer.json`, `artisan` | PHP / Laravel |
| `pom.xml`, `build.gradle` | Java (Spring Boot if `spring-boot` found) |
| `*.csproj`, `*.sln` | .NET / C# |
| `go.mod` | Go |
| `Cargo.toml` | Rust |
| `Gemfile` | Ruby |
| `manage.py` / `django` in manifests | Django |
| `react`, `next`, `vue`, `@angular/core`, `express` in `package.json` | React / Next.js / Vue / Angular / Express |

Package managers, build tools, test frameworks, and CI/CD files
(`.github/workflows`, `.gitlab-ci.yml`, `Jenkinsfile`, `Dockerfile`, …)
are detected the same way.

## Project layout

```text
repo-onboarding-assistant/
├── skills/                  # skill instructions, metadata, and entry point
├── analyzers/               # scanning, analysis, domain and business logic
├── models/                  # repository and architecture data models
├── artifacts/               # dashboard and visualization renderers
├── templates/               # reference Markdown skeletons
├── outputs/                 # generated artifacts (default target)
└── tests/                   # pytest suite with synthetic fixture repos
```

## Tests

```bash
pytest tests/ -v
```
