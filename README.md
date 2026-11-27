# Repository Onboarding Assistant

Repository Onboarding Assistant scans a source repository and creates a
developer-oriented overview, learning path, and machine-readable inventory.
It is a standalone skill built on the
[LLM Harness Lite Artifact API](https://github.com/abadiape/llm-harness-lite);
the repository scanner and analysis models do not depend on the harness.

The scanner is intended to become the shared foundation for repository
onboarding, architecture exploration, security review, documentation
generation, and modernization advice. Those capabilities should consume
reusable repository facts rather than each implementing a separate scanner.

## Current MVP

The scanner and architecture analyzer are deliberately lightweight and
read-only. The architecture analyzer does not build an AST or resolve calls;
it uses bounded lexical checks for imports/re-exports, type and class
references, dependency registrations, documentation, and configuration, then
combines those signals with framework/layout conventions. Relationships carry
confidence and file/line evidence, and are not presented as observed call edges.
Confidence values are heuristic scores, not calibrated probabilities. Import
edges require a unique match to a model-listed local source file; unresolved
imports are omitted. Configuration registration discovery currently recognizes
provider/binding/registration sections in YAML, and other detections are
best-effort lexical heuristics, not full language or dependency-injection
resolution.

It currently inventories:

- Languages and selected frameworks, detected from manifests and file extensions
- Framework-specific conventions and dependency categories from applicable analyzers
- Normalized dependencies and their manifest source/scope
- Repository-relative file records, directory paths, and detected conventions
- Package managers, build backends, and common test frameworks
- Important files, onboarding documents, and top-level directories
- Likely entry points, build/test suggestions, and CI/CD configuration files
- Shell commands documented in relevant Markdown code blocks
- Inline `run` commands found in CI workflow YAML
- Project-owned Magento `app/code/*/*/etc/webapi.xml` route declarations and
  locally declared service contract parameters and return types

When Magento route declarations are present, the offline knowledge hub includes
a searchable API Inventory view and `knowledge_hub.json` contains the same
data. The view groups declarations by path in case-insensitive alphabetical
order, with expandable methods; duplicate
declarations or overrides remain separate, with their source, service and
access resources. It can be generated from a local clone without access to a
running environment. Paths are source declarations, not complete URLs; base
URLs and REST or store prefixes can vary by environment, as can deployed code,
module enablement and overrides. Routes may be called by storefront code or
external clients, and their implementations may use local data or call external
services. The PHP contract extraction is best-effort, and configured parameter
values are intentionally omitted. This is
not Swagger or a complete OpenAPI specification: vendor/platform routes,
outbound service calls, inherited contracts, resolved dependency injection,
runtime module activation, request/response schemas and endpoint criticality
are not determined. Confirm the effective routes and checkout dependencies with
maintainers or the running deployment. Malformed route files are reported in
the inventory rather than silently omitted.

Documented commands are surfaced as evidence, not executed. Build and test
suggestions inferred from manifests are heuristics; the commands declared by
the project or its CI should be preferred when they disagree.

## Analyzer extensions

`analyzers/analyzers.py` runs `GenericAnalyzer` followed by each applicable language
analyzer. Implement the small `Analyzer` interface (`supports` and `analyze`),
then add the analyzer to `DEFAULT_ANALYZERS`; callers can also pass a custom
analyzer sequence to `scan_repository`. Analyzers enrich `RepositoryModel`;
artifact renderers consume that model separately from scanning.
Scanner helpers are grouped by file discovery, manifests, tooling, and
onboarding evidence. Architecture discovery separates evidence collection,
component and relationship inference, and model assembly from diagram and
report rendering. Business models live in `models/`, while business report
renderers live in `artifacts/`. Existing public analyzer import paths remain
available for callers.
`analyzers/architecture_analyzer.py` extracts a framework-aware `ArchitectureModel`
from repository structure, patterns, public API exports, source references,
and bounded README, documentation, and configuration evidence, then renders
architecture artifacts from that intermediate model. It also recognizes feature
boundaries containing multiple architectural layers and uniquely matched public
modules. Components accumulate evidence across categories: confidence measures
support for a component, while significance combines relevance, distinct
relationships, references from prominent components, and position in the
selected conceptual flow. The JSON retains the earlier relevance score.
Significance is shown as High (at least 0.55), Medium (at least 0.20), or Low.
All scores are heuristics rather than probabilities, and the number of files
alone does not determine priority. The analyzer groups recognized roles into
only the architectural layers supported by the detected components, and
describes their constituent roles and representative paths. These groupings
are not proof of actual runtime boundaries. For Magento, model and provider
names are treated as cross-module conventions, not a single domain layer or a
specific integration role. Generated Magento static and preprocessed assets are
excluded from architectural inference.
Diagrams focus on the analyzed repository's components and inferred
relationships, not the scanner pipeline or a dependency inventory.
Recognized optional integration dependencies are reported separately from
runtime integration signals, with their manifest and extra when available.
Neither establishes which services are active in a particular deployment.
Diagram legends explain component names and include available relationship
evidence. Magento imports and type references alone do not establish an
execution sequence. Magento architecture overviews summarize the detected
module and theme layout rather than treating an inherited README template as
an authoritative description of the current deployment; other README descriptions
remain attributed to the README.
For other repositories, README and documentation evidence remains available
to architecture inference. An explicitly documented retrieval-as-tool
integration appears as an optional branch, not a mandatory agent step.
When a Python package initializer re-exports local modules, the first-day
plan identifies it as a public API starting point, not necessarily a runtime
entry point.
`analyzers/repository_archetype.py` classifies repository purpose before domain
discovery using bounded README and manifest descriptions, repository names,
declared Magento dependencies, and project layout. The selected archetype,
heuristic confidence, evidence, and alternative candidates are recorded in
`knowledge_hub.json` and `domain_map.json`. Scores are not probabilities and
classifications can be wrong; review the evidence with a maintainer. An unknown
classification remains unknown rather than assuming a business application.

For inferred business applications, `analyzers/domain_discovery.py` consumes project-owned module boundaries, repository
documentation, source paths, and Architecture Discovery's external dependency
facts to infer business domains, capabilities, and integration boundaries.
These are convention-based suggestions with supporting evidence, not
authoritative ownership or business rules. Domain Discovery is separate from
Architecture Discovery and puts business-focused steps first in the learning
path. For all other archetypes, including unknown, commerce-specific domain
inference is conservatively suppressed; this may omit real business concepts
in mixed-purpose repositories. Technical reports and learning paths instead
point to matching source and documentation evidence.
`analyzers/business_insights.py` scores evidence confidence separately from estimated
business impact (Critical, High, Medium, or Low) and onboarding importance, then
ranks modules and plans a first week. Impact reflects workflow categories, not
confidence: payment and order workflows are rated Critical; inventory, ERP,
shipping, and customer workflows are High when there is direct evidence.
Module recommendations favor domain representatives and use name-based
heuristics to defer some supporting customizations; they do not prove a module's
runtime role. Human-readable reports show at most ten prioritized modules; the
domain map retains the complete inventory. Domain evidence is available in
expandable report sections and the domain map. Scores are heuristic and do not
represent measured revenue or calibrated probabilities. Documentation-only
mentions remain low impact unless supported by a custom module, source path, or
Architecture Discovery integration evidence. Integration criticality and runtime
activation must be confirmed with maintainers.
`analyzers/narrative_generation.py` combines architecture, domain-discovery, and
business-insight findings into repository-specific stories, workflow guides,
and onboarding briefs. Business narrative summaries prioritize matched custom modules,
capabilities, and configured integrations; repository descriptions are fallback
context rather than the primary explanation when direct business evidence exists.
Module/domain links and inferred flows remain onboarding hypotheses, not observed
runtime call order or operational risk.

`analyzers/repository_relevance.py` classifies project, infrastructure, vendor, and
generated areas using path conventions. The scanner records vendor/generated
directory boundaries but does not descend into them. Application architecture
is inferred from the remaining paths; ownership and framework group labels
are heuristic, not authoritative. Custom module, theme, workspace package,
and layered business-area paths are retained for exploration.

Composer and npm lockfiles contribute distinct declared or locked package
names to namespace-level groups. Counts are deduplicated by package name, not
installation or version, and lockfiles do not prove packages are installed.
Lockfile entries and individual group members remain available for drill-down;
vendor manifests are not traversed, so a missing lockfile limits visibility.
Large dependency lists are summarized rather than displayed as individual
declarations.

Run the skill from this directory:

```bash
pip install -r requirements.txt
python skills/onboarding_skill.py /path/to/repository
python skills/onboarding_skill.py /path/to/repository --output-dir ./my-output
python skills/onboarding_skill.py /path/to/repository --module-graph app/code/Company/Module
```

The entry point can also be run as `python -m skills.onboarding_skill` from
the repository root. Skill metadata is in `skills/skill.yaml`; its entry point
and capability paths are relative to that file.

Open `knowledge_hub.html` in the output directory to start onboarding. It is
generated from `knowledge_hub.json`, embeds its content, and works from a local
file without a server or network connection. The hub presents archetype evidence,
repository-specific technical topics or business findings, architecture, a five-day plan, and an artifact
explorer. Its SVG visualizations support zoom, drag-to-pan, fullscreen, and
export; they summarize inferred architecture relationships, conceptual flow,
and workflow/domain associations rather than executing Mermaid or showing
runtime traces. Inferred priorities and business impacts should be confirmed
with maintainers.

`--module-graph` is optional and accepts a detected repository-relative area
listed in `architecture_map.json` or the dashboard. It generates
`module_graph.mmd`; an unknown area is reported as an error. System overview
and subsystem diagrams use at most 15 nodes, aggregating large models and
showing an "Other" count when areas do not fit. The full area list is in the
architecture map and dashboard.

By default, the skill writes these artifacts to `outputs/`:

- `summary.md` — technologies, repository structure, reading suggestions, and
  documented setup/CI commands
- `learning_path.md` — a suggested sequence for becoming productive
- `repository_map.json` — the serialized `RepositoryModel`, including
  normalized metadata, dependencies, directories, files, and detected patterns
- `architecture_summary.md` — system narrative, responsibilities, execution
  flow, and recommended exploration order
- `architecture_map.json` — machine-readable components, subsystems, layers,
  responsibilities, inferred relationships, entry points, external
  integrations, data stores, and detected patterns; each relationship includes
  a confidence score and supporting evidence; components also include relevance
  and significance scores and locations, plus repository relevance and grouped
  dependency information
- `business_domains.md` — inferred responsibilities, business value, impact,
  starting modules, learning guidance, and expandable evidence
- `business_capabilities.md` — capabilities grouped by business workflow and
  inferred external ownership boundaries
- `onboarding_priorities.md` — a suggested one-week business-first learning
  order, including areas to defer initially
- `domain_map.json` — structured domains, capabilities, integrations, custom
  modules, priorities, and business-impact assessments
- `executive_summary.md` — concise repository purpose, value areas, and initial
  focus
- `critical_modules.md` — top ten modules with domain ownership, impact, and
  rationale; the domain map retains remaining modules
- `first_week_onboarding.md` — a five-day business-focused onboarding plan
- `business_insights.md` — prioritized value areas, integration boundaries, and
  maintainer-confirmable recommendations
- `business_story.md` — inferred system purpose, business flow, primary domains,
  critical integrations, and first-focus recommendations
- `critical_workflows.md` — capability-based workflow guides with involved
  domains, modules, and onboarding significance
- `first_week_story.md` — a five-day learning sequence grounded in discovered
  business priorities
- `repository_story.md` — repository-specific business flow, domain evidence,
  detected patterns, and prioritized customizations
- `business_risk_story.md` — inferred areas of business sensitivity for
  onboarding, not an operational risk assessment
- `first_day_briefing.md` — concise first-day overview and recommended learning
  sequence
- `system_overview.mmd` — high-level component relationship diagram
- `execution_flow.mmd` — inferred application execution sequence
- `subsystem_map.mmd` — components grouped by architectural boundary
- `knowledge_hub.json` — structured aggregate used to generate the hub
- `knowledge_hub.html` — primary, offline onboarding experience
- `dashboard.html` — standalone onboarding dashboard with embedded diagram
  source, rendered Mermaid diagrams, and learning-path content
- `manifest.json` — artifacts registered through the harness API

The dashboard loads a pinned Mermaid.js release from jsDelivr to render the
diagrams. The HTML and Mermaid source are embedded in the artifact; if the CDN
is unavailable, users can still view or copy the Mermaid source.
Execution-flow diagrams depict a likely conceptual path through relationships,
not observed runtime events; imports and references are not proof of calls.
When Magento lacks execution-specific evidence but has component relationships,
the execution-flow artifact instead shows a labeled association path. Its edges
may come from different modules and do not establish execution order or calls.
External services and data stores are inferred from runtime dependencies,
top-level imports, and recognized runtime configuration, not documentation
mentions or development/optional dependencies. Profile-gated Compose services
and disabled YAML sections, as well as example, local, or development
configuration, are excluded. These signals
do not prove an integration is active in a deployment, and conservative
filtering may miss integrations. Architecture evidence is sampled from at most 120
model-listed files, up to 24 KB per file and 400 KB total. Root README and
configuration, entry points, selected public APIs, and documentation are
prioritized; remaining files are interleaved by directory. Sampling and lexical
matching are incomplete and do not resolve a call graph.

Run the tests with:

```bash
pytest tests/ -v
```

## Why the model is the foundation

The model should be a stable, tool-independent description of what the
scanner can observe. It should not contain conclusions that belong to a
particular consumer. For example, a future code analyzer can record that module A
imports module B and that a test file references module A; onboarding can use
those facts to suggest a reading order, while an architecture explorer can use
them to show module dependencies.

The current model already records repository metadata, manifest dependencies,
file paths and roles, directories, and detected patterns. Future work can add
versioning and deeper code-level records such as:

| Record | Useful facts |
|---|---|
| Repository snapshot | Root, metadata, detected languages |
| File | Relative path, broad kind, language |
| Manifest | Build system, normalized dependencies, scripts, runtime constraints |
| Symbol | Qualified name, kind (module/class/function), file and line span |
| Relationship | Source, relation type, target, evidence location, confidence |

Every derived fact should retain its provenance: which file and line support
it, which detector produced it, and whether it is directly observed or
inferred. A consumer should be able to distinguish “the manifest declares
FastAPI” from “this route function is registered with FastAPI.” Unknown or
unresolved relationships should remain unknown, rather than being presented
as certain.

## What deeper architecture analysis requires

File names and manifests reveal the repository's broad shape, but not how code
is organized internally. Deeper analysis needs at least:

1. **A complete, bounded file catalog.** Normalize relative paths, identify
   generated/vendor/build outputs, respect ignore rules, and make scanning
   deterministic. Large repositories need limits and incremental indexing.
2. **Language-aware syntax extraction.** Parse source into modules and symbols
   (functions, classes, methods, types, routes, and configuration declarations)
   with source spans. For Python, the standard-library `ast` module is a
   reasonable first adapter. Other languages need their own parser, compiler,
   or language-server integration; file extensions alone are not enough.
3. **Relationship resolution.** The current analyzer makes a bounded lexical
   first pass over imports/re-exports, type/class references, registrations,
   configuration, and explicit documentation statements. Deeper edges such as
   `calls`, `tests`, and fully resolved dependency injection still require
   syntax extraction and resolution of aliases, conditional imports, and
   runtime configuration.
4. **An explicit confidence model.** An import can often be observed directly;
   a call target may be ambiguous; a runtime plugin target may be unknowable
   statically. Preserve those differences instead of flattening all edges into
   a single “architecture” claim.
5. **Evidence and validation.** Store paths and line ranges for findings, then
   test the extracted facts against small fixture repositories and real
   projects. Keep fixtures for edge cases such as import cycles, aliases,
   generated files, monorepos, and unsupported syntax.

Static analysis will still have limits: reflection, dynamic imports,
dependency injection, generated code, and runtime configuration can hide
relationships. When static evidence is insufficient, an optional, explicitly
enabled runtime trace or language-server index could add evidence. Repository
scanning should remain read-only by default and must not run arbitrary project
code to “discover” behavior.

## How future capabilities can reuse it

| Capability | Inventory and relationship facts it can consume |
|---|---|
| **Repository onboarding** | Setup docs, manifests, entry points, module/import relationships, tests, and CI commands to suggest a supported first-reading path |
| **Architecture explorer** | Modules, symbols, imports, calls, inheritance, registration, and configuration relationships, with paths and evidence |
| **Security review** | Dependency declarations, configuration and secret-handling locations, and source-to-sink relationships; a dedicated ruleset must interpret these facts and report evidence rather than treating inventory as a security verdict |
| **Documentation generator** | Public symbols, docstrings/comments, module structure, examples, and existing documentation to draft and cross-link reference material |
| **Modernization advisor** | Runtime constraints, dependency versions, build/test configuration, deprecated APIs, and migration rules to identify evidence-backed update opportunities |

The shared scanner should provide facts and relationships. Capability-specific
logic should decide what those facts mean, what recommendations to make, and
how to render them. This separation lets the scanner improve without turning
the inventory into five unrelated sets of heuristics.

## Suggested implementation sequence

1. **Harden the inventory contract.** Add a schema version and stable file
   records; keep path handling, ignore behavior, and manifest extraction
   deterministic and well tested.
2. **Add one language adapter.** Start with Python and extract modules,
   classes, functions, definitions, imports, and source spans. Build a small
   import graph and preserve unresolved imports explicitly.
3. **Use those facts in onboarding.** Recommend entry modules and tests based
   on observed imports and test references, while showing the evidence behind
   each suggestion.
4. **Add relationship types incrementally.** Calls, inheritance, registration,
   and configuration links each need separate resolution rules and tests.
   Avoid claiming a complete call graph where static resolution is ambiguous.
5. **Add other language adapters behind a shared interface.** Expand language
   coverage only when each adapter can provide comparable entities,
   relationships, provenance, and known limitations.
6. **Build capability-specific consumers.** Architecture, security,
   documentation, and modernization should query the same versioned facts and
   add their own rules, evidence requirements, and output formats.

This sequence keeps the first useful capability small while creating a path
for deeper analysis. It also avoids making an early parser choice or one
capability's assumptions part of the permanent inventory contract.

## Project layout

```text
repo-onboarding-assistant/
├── skills/                  # Skill instructions, metadata, and CLI entry point
├── analyzers/               # Scanning, analysis, domain and business logic
├── models/                  # Repository and architecture data models
├── artifacts/               # Dashboard and visualization renderers
├── templates/               # Reference output templates
├── outputs/                 # Default generated artifacts
└── tests/                   # Scanner, analyzer, and end-to-end tests
```

`skills/SKILL.md` describes how the skill is invoked by its host. This README describes
the project, the current scanner boundary, and the planned evolution of the
shared inventory.
