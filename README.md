# Repository Onboarding Assistant

## Overview

Repository Onboarding Assistant is a repository intelligence and onboarding
platform. It builds reusable repository knowledge from a local source tree,
then turns that knowledge into architecture, domain, business, and onboarding
guidance. Its models and evidence also provide a foundation for future
repository analysis capabilities.

The analysis moves from inventory discovery through architecture and domain
discovery, business insights, and narrative generation to a navigable
Knowledge Hub. It is a standalone skill built on the
[LLM Harness Lite Artifact API](https://github.com/abadiape/llm-harness-lite)
(version 0.2.0 or later); repository analysis and its models do not depend on
the harness.

## Current Capabilities

### Repository Inventory

The inventory discovers:

- Languages and selected frameworks from manifests, file extensions, and
  framework-specific conventions
- Normalized manifest dependencies, their source and scope, and dependency
  categories; Composer and npm lockfile entries are also collected
- Repository-relative file records, directory paths, detected conventions,
  top-level directories, important files, and onboarding documents
- Package managers, build backends, common test frameworks, and likely entry
  points
- Build and test suggestions, commands in relevant Markdown code blocks, CI/CD
  configuration files, and inline `run` commands in CI workflow YAML
- API operations declared in local OpenAPI 3.x and Swagger 2.0 JSON or YAML
  documents, and project-owned Magento `app/code/*/*/etc/webapi.xml` route
  declarations with best-effort local service contract details

Path conventions classify application, infrastructure, supporting, vendor, and
generated areas. Vendor and generated directory boundaries are recorded but
not traversed. Custom modules, themes, workspace packages, and layered business
areas are retained for exploration. Ownership and framework group labels are
heuristics.

Composer and npm lockfiles contribute distinct declared or locked package names
to namespace-level groups. Counts are deduplicated by package name, not
installation or version. Individual entries and group members remain available
for drill-down; large lists are summarized.

### AST Symbol Inventory

The scanner parses inventoried Python files with the standard-library AST
parser. It records modules, packages with `__init__.py`, classes, functions,
methods, declarations, containment, and imports in `RepositoryModel` and
`repository_symbols.json`. Locations use repository-relative paths, 1-based
lines, and 0-based UTF-8 byte columns, as provided by Python's AST. Evidence
includes the source line and detector. Parse and read failures are logged and
do not stop the scan; a readable file with invalid syntax still has a module
record.

Import statements are direct observations; local target resolution is
best-effort based on unique names and is not runtime resolution. Imports
without a unique matching local symbol use an `unresolved:python:` target ID
followed by the observed import name, including relative dots. Such IDs do not
refer to inventory symbols and may denote external imports, ambiguous names,
or unresolved local names. Package names are derived from repository paths;
unique suffix matching supports source-root layouts, but runtime search paths,
re-exports, and dynamically defined symbols are not inferred.

### Architecture Discovery

Architecture Discovery combines repository structure and conventions with
bounded source, README, documentation, and configuration evidence to infer
components, responsibilities, relationships, subsystems, and supported
architectural layers. It recognizes feature boundaries containing multiple
layers and uniquely matched public modules. Resolved Python AST imports add
evidence alongside existing lexical discovery. Diagrams focus on the repository's
components and relationships, and their legends include available evidence.

Components accumulate evidence across categories. Confidence measures support
for a component; significance combines relevance, distinct relationships,
references from prominent components, and position in the selected conceptual
flow. Significance is displayed as High (at least 0.55), Medium (at least 0.20),
or Low. The architecture JSON also retains relevance scores and locations.
File count alone does not determine priority.

External services and data stores are inferred from runtime dependencies,
top-level imports, and recognized runtime configuration. Recognized optional
integration dependencies are reported separately, with the manifest and extra
when available. An explicitly documented retrieval-as-tool integration is
shown as an optional branch, not a mandatory agent step.

For Magento, model and provider names are treated as cross-module conventions,
not as evidence of one shared domain layer or a specific integration role.
Architecture overviews summarize the detected module and theme layout rather
than treating an inherited README template as the current deployment's
authoritative description. Elsewhere, README descriptions remain attributed
to the README. A Python package initializer that re-exports local modules is
identified as a public API starting point, not necessarily a runtime entry
point.

### Domain Discovery

Repository archetype classification uses bounded README and manifest
descriptions, repository names, declared Magento dependencies, and project
layout. The selected archetype, heuristic confidence, evidence, and alternative
candidates are recorded in `knowledge_hub.json` and `domain_map.json`. An
unknown classification remains unknown rather than defaulting to a business
application.

For inferred business applications, Domain Discovery uses project-owned
module boundaries, documentation, source paths, and Architecture Discovery's
external dependency facts to suggest business domains, capabilities, and
integration boundaries. It places business-focused steps first in the
learning path. For other archetypes, including unknown, commerce-specific
inference is suppressed and technical reports and learning paths point to
matching source and documentation evidence.

### Business Analysis

Business Insights assesses evidence confidence separately from estimated
business impact and onboarding importance. It ranks modules, prioritizes
workflows, and recommends a first-week learning plan. Impact reflects workflow
categories: payment and order workflows are rated Critical; inventory, ERP,
shipping, and customer workflows are High when there is direct evidence.
Documentation-only mentions remain low impact unless supported by a custom
module, source path, or Architecture Discovery integration evidence.

Module recommendations favor domain representatives and use name-based
heuristics to defer some supporting customizations. Human-readable reports
show at most ten prioritized modules; the domain map retains the complete
inventory. Domain evidence appears in expandable report sections and the
domain map.

Narrative Generation combines architecture, domain, and business findings into
repository-specific stories, workflow guides, and onboarding briefs. It
prioritizes matched custom modules, capabilities, and configured integrations;
repository descriptions provide fallback context when direct business
evidence is unavailable.

### Knowledge Hub and Dashboard

The generated Knowledge Hub brings archetype evidence, technical topics or
business findings, architecture, a five-day plan, and an artifact explorer
together in an offline HTML experience. A separate dashboard presents
onboarding content and architecture diagrams. When API declarations or
discovery warnings are found, the hub also provides a searchable API
Inventory. See [Knowledge Hub](#knowledge-hub) for details.

## Analysis Architecture

```text
Repository
    ↓
Inventory Discovery
    ↓
AST Extraction and Relationship Resolution
    ↓
Repository Knowledge Model
    ↓
Architecture Discovery
    ↓
Domain Discovery
    ↓
Business Insights
    ↓
Narrative Generation
    ↓
Knowledge Hub
```

This is a conceptual view of the processing flow, not a strictly linear data
dependency: later stages also consume earlier models directly.

1. **Inventory Discovery** scans the repository and enriches a
   `RepositoryModel` with files, dependencies, tooling, commands, and other
   observed or convention-based facts.
   **AST Extraction and Relationship Resolution** adds a reusable symbol and
   relationship inventory to that model before architecture discovery.
2. **Architecture Discovery** derives an `ArchitectureModel` of components,
   relationships, evidence, and architectural groupings.
3. **Domain Discovery** uses an independently determined repository archetype
   alongside inventory and architecture findings to identify relevant domains,
   capabilities, and integrations.
4. **Business Insights** prioritizes domain and architecture findings, or
   produces technical guidance for non-business archetypes.
5. **Narrative Generation** synthesizes those findings into stories, workflow
   guidance, and onboarding briefs.
6. **Knowledge Hub** aggregates the structured results into JSON and renders
   the offline HTML experience. Separate renderers produce Markdown, diagrams,
   the dashboard, and other artifacts.

Archetype classification runs after inventory discovery and before domain
discovery. Inventory-based onboarding analysis also contributes to the summary
and learning path.

## Repository Knowledge Model

Repository knowledge is represented by related, tool-independent models rather
than a single scanner report:

| Entity or finding | Current representation |
|---|---|
| Repository, files, directories | Metadata, relative paths, file roles, languages, and detected patterns in `RepositoryModel` |
| Dependencies | Manifest declarations and lockfile entries with source, scope, and category |
| Symbols and source relationships | Python AST declarations, package containment, and observed imports with source evidence in `RepositoryModel` |
| Components and architecture | Components, subsystems, layers, responsibilities, locations, and inferred flows in `ArchitectureModel` |
| Domains and capabilities | Inferred business domains, responsibilities, capabilities, and custom modules in `DomainDiscovery` |
| Integrations | Architecture dependency and data-store signals, optional integrations, and inferred business integration boundaries |
| Evidence and relationships | Supporting evidence on findings; architectural relationships with source, target, type, confidence, and evidence |
| Business insights | Domain impacts, module priorities, recommendations, and learning plans |

Inventory facts are kept separate from consumer-specific conclusions:
onboarding, architecture, and business analysis interpret the available
evidence for different purposes. Findings retain supporting provenance where
available, including source paths and, for some relationships, line locations.
Not every current finding has a detector identifier or a full source span.
Direct observations should be distinguished from inferences; unresolved or
unknown relationships must not be presented as certain.

## Analyzer Extensions

[`analyzers/analyzers.py`](analyzers/analyzers.py) runs `GenericAnalyzer`
followed by each applicable language analyzer. Implement the `Analyzer`
interface (`supports` and `analyze`) and add the analyzer to
`DEFAULT_ANALYZERS`; callers can also pass a custom analyzer sequence to
`scan_repository`. Analyzers enrich `RepositoryModel`, while artifact renderers
consume the resulting models separately.

Scanner helpers are grouped by file discovery, manifests, tooling, and
onboarding evidence. Architecture discovery separates evidence collection,
component and relationship inference, scoring, and model assembly from diagram
and report rendering. Business models live in `models/`, and business report
renderers live in `artifacts/`. Existing public analyzer import paths remain
available for callers.

## Running the Skill

From the repository root:

```bash
pip install -r requirements.txt
python skills/onboarding_skill.py /path/to/repository
python skills/onboarding_skill.py /path/to/repository --output-dir ./my-output
python skills/onboarding_skill.py /path/to/repository --module-graph packages/my-package
```

The entry point also supports `python -m skills.onboarding_skill`. The optional
`--module-graph` argument accepts a detected repository-relative area listed in
`architecture_map.json` or the dashboard and generates `module_graph.mmd`.
An unknown area is reported as an error. Skill metadata is in
[`skills/skill.yaml`](skills/skill.yaml); its entry point and capability paths
are relative to that file.

Run the tests with:

```bash
pytest tests/ -v
```

## Generated Artifacts

By default, the skill writes to `outputs/`:

| Artifact | Description |
|---|---|
| `summary.md` | Technologies, structure, reading suggestions, and documented setup and CI commands |
| `learning_path.md` | Suggested sequence for becoming productive |
| `repository_map.json` | Serialized `RepositoryModel`, including metadata, dependencies, directories, files, and detected patterns |
| `repository_symbols.json` | Symbol and relationship inventories with source evidence |
| `architecture_summary.md` | System narrative, responsibilities, conceptual flow, and recommended exploration order |
| `architecture_map.json` | Components, subsystems, layers, relationships and evidence, scores, entry points, integrations, repository relevance, and grouped dependencies |
| `business_domains.md` | Inferred responsibilities, value, impact, starting modules, learning guidance, and expandable evidence |
| `business_capabilities.md` | Capabilities grouped by business workflow and inferred external ownership boundaries |
| `onboarding_priorities.md` | Suggested one-week business-first learning order and areas to defer |
| `domain_map.json` | Structured archetype, domains, capabilities, integrations, custom modules, priorities, and business-impact assessments |
| `executive_summary.md` | Concise repository purpose, value areas, and initial focus |
| `critical_modules.md` | Top ten modules with domain ownership, impact, and rationale; remaining modules are retained in the domain map |
| `first_week_onboarding.md` | Five-day business-focused onboarding plan |
| `business_insights.md` | Prioritized value areas, integration boundaries, and recommendations to confirm with maintainers |
| `business_story.md` | Inferred purpose, business flow, primary domains, integrations, and initial focus |
| `critical_workflows.md` | Capability-based workflow guides with domains, modules, and onboarding significance |
| `first_week_story.md` | Five-day learning sequence grounded in discovered business priorities |
| `repository_story.md` | Repository-specific business flow, domain evidence, patterns, and customizations |
| `business_risk_story.md` | Inferred business sensitivity for onboarding, not an operational risk assessment |
| `first_day_briefing.md` | First-day overview and recommended learning sequence |
| `system_overview.mmd` | High-level component relationship diagram |
| `execution_flow.mmd` | Inferred conceptual flow or a labeled association path |
| `subsystem_map.mmd` | Components grouped by architectural boundary |
| `module_graph.mmd` | Optional diagram scoped to the area selected by `--module-graph` |
| `knowledge_hub.json` | Structured aggregate used to generate the hub |
| `knowledge_hub.html` | Primary offline onboarding experience |
| `dashboard.html` | Standalone dashboard with embedded Mermaid source, rendered diagrams, and learning-path content |
| `manifest.json` | Artifacts registered through the harness API |

For non-business archetypes, several business-named Markdown files contain
repository-specific technical topics and learning guidance instead of
commerce-focused findings.

## Knowledge Hub

Open `knowledge_hub.html` from the output directory. It embeds the content of
`knowledge_hub.json` and works from a local file without a server or network
connection. Its SVG visualizations support zoom, drag-to-pan, fullscreen, and
export. They summarize inferred architecture relationships, conceptual flow,
and workflow/domain associations rather than executing Mermaid.

The separate dashboard loads a pinned Mermaid.js release from jsDelivr to
render its diagrams. Its HTML and Mermaid source are embedded; if the CDN is
unavailable, users can still view or copy the source. System overview and
subsystem diagrams use at most 15 nodes, aggregating large models and showing
an "Other" count when areas do not fit. The full area list is available in the
architecture map and dashboard.

### API Inventory

The inventory discovers operations in OpenAPI 3.x and Swagger 2.0 documents
(JSON or YAML) and project-owned Magento route declarations. The hub displays
findings or discovery warnings when either is present, and
`knowledge_hub.json` contains the same inventory. Declarations are grouped by
path in case-insensitive alphabetical order with expandable methods; duplicate
declarations remain separate with their sources. The inventory can be
generated from a local clone without a running environment.

OpenAPI and Swagger operations include the document version, source, and
available operation ID and summary. Their direction is **unknown**: a document
alone does not establish whether the project exposes or consumes an API, or
whether it is used or deployed. Local path-item references within a document
are followed; unresolved, cyclic, conflicting, and external path references
are reported. External references are not fetched. Discovery is limited to
JSON and YAML files, with a 10 MB limit per candidate specification; malformed
or oversized candidates are reported. The inventory does not yet extract
specification parameters, schemas, callbacks, webhooks, or outbound calls.

For Magento, the inventory reads project-owned `webapi.xml` routes, preserving
duplicate declarations and overrides with their service and access resources.
Malformed route files are reported. PHP contract extraction is best-effort, and
configured parameter values are intentionally omitted.

Paths are source declarations, not complete URLs: base URLs, REST or store
prefixes, deployed code, module enablement, and overrides can vary by
environment. Routes may be called by storefront code or external clients, and
implementations may use local data or external services. Magento extraction is
not a complete OpenAPI specification: vendor and platform routes, outbound
calls, inherited contracts, resolved dependency injection, runtime module
activation, request/response schemas, and endpoint criticality are not
determined. Confirm effective routes and checkout dependencies with maintainers
or the running deployment.

## Current Limitations

- **Evidence is bounded and lexical.** The architecture analyzer does not
  build an AST or resolve calls. It uses best-effort lexical checks for
  imports/re-exports, type and class references, registrations,
  documentation, and configuration, combined with framework and layout
  conventions. Import edges require a unique match to a model-listed local
  source file; unresolved imports are omitted. Configuration registration
  discovery recognizes provider/binding/registration sections in YAML, not
  full dependency-injection resolution.
- **Sampling is incomplete.** Relationship evidence is sampled from at most
  120 model-listed files, up to 24 KB per file and 400 KB total. Root README
  and configuration, entry points, selected public APIs, and documentation
  are prioritized; remaining files are interleaved by directory. Generated
  Magento static and preprocessed assets are excluded from architectural
  inference. Lockfiles do not prove packages are installed, and missing
  lockfiles limit dependency visibility because vendor manifests are not
  traversed.
- **Scores and boundaries are heuristic.** Confidence values are not
  calibrated probabilities, and business impacts are not measured revenue.
  Architectural layers, ownership, module roles, domains, capabilities, and
  integrations are suggestions, not authoritative runtime or business
  boundaries. Conservative archetype filtering may omit business concepts in
  mixed-purpose repositories. Confirm priorities, integration criticality,
  runtime activation, and ownership with maintainers.
- **Flows are not runtime traces.** Diagram paths and narrative links are
  onboarding hypotheses, not observed call order or operational risk.
  Imports and references do not prove calls. For Magento, imports and type
  references alone do not establish an execution sequence; when execution
  evidence is absent, the execution-flow artifact may show a labeled
  association path whose edges may come from different modules.
- **Integration signals are not deployment verification.** Documentation
  mentions and development/optional dependencies do not establish runtime
  integrations. Profile-gated Compose services, disabled YAML sections, and
  example, local, or development configuration are excluded; conservative
  filtering may miss integrations. Optional dependencies and runtime signals
  do not prove a service is active.
- **Commands are evidence, not execution instructions.** Documented commands
  are surfaced but not executed. Build and test suggestions inferred from
  manifests are heuristics; prefer commands declared by the project or CI
  when they disagree.

Repository inspection is read-only and does not execute arbitrary project code.
Generating artifacts writes to the selected output directory.

## AST Analysis Roadmap

AST-based analysis is the next major architectural milestone. It is planned,
not implemented: the existing architecture and PHP contract extraction use
the methods described above.

### Why AST Matters

Language-aware syntax extraction can identify symbols and source spans more
reliably than lexical matching, improve relationship discovery and
architecture understanding, and provide reusable facts for future
capabilities. It will complement the existing inventory and evidence-driven
analysis rather than make inferred behavior automatically certain.

### Planned Capabilities

Language adapters can extract modules, classes, functions, interfaces, methods,
imports, exports, routes, and configuration declarations where the language
and parser support them. Python's standard-library `ast` module is a
reasonable first adapter; other languages need appropriate parsers, compilers,
or language-server integrations. Planned records include qualified names,
kinds, file locations, and source spans.

### Planned Relationship Types

Planned relationships include imports, inheritance, interface implementation,
registrations, calls, and test references. Resolution must handle aliases,
conditional imports, and language-specific conventions; extracting syntax
alone does not resolve every target. Future facts should retain their source
and detector, distinguish observation from inference, and represent unresolved
targets explicitly rather than inventing edges.

Validation should use small fixture repositories and real projects, including
import cycles, aliases, generated files, monorepos, and unsupported syntax.
File cataloging, ignore behavior, bounded analysis, deterministic output,
incremental indexing, and model versioning remain important as the knowledge
model grows.

### Expected Limitations

Even with ASTs, reflection, dynamic imports, dependency injection, generated
code, and runtime configuration can hide relationships. Optional, explicitly
enabled runtime tracing or language-server indexes may eventually add
evidence; they should not replace the default read-only behavior or be
presented as currently available.

## Future Enhancements

### AST Language Adapters

Introduce language-aware adapters for Python, PHP, JavaScript, and TypeScript,
with comparable entities, provenance, and documented language-specific
limitations.

### Relationship Resolution

Improve call graph resolution, dependency-injection analysis, and
configuration linkage incrementally, preserving ambiguity and evidence rather
than claiming a complete graph. Add evidence-based discovery of outbound API
calls and additional API declaration sources as language adapters mature.

### Additional Repository Intelligence

Build consumers of shared facts for architecture exploration, security review
support, documentation generation, and modernization guidance. Each consumer
needs its own rules and evidence requirements: dependency and configuration
facts alone are not a security verdict, for example.

### Advanced Knowledge Hub Features

Expand dashboard and hub exploration as richer symbol and relationship
evidence becomes available, including navigation and drill-down into those
facts and their provenance.

## Project Layout

```text
repo-onboarding-assistant/
├── skills/                  # Skill instructions, metadata, CLI, and artifact registration
├── analyzers/               # Inventory, architecture, domain, and business analysis
├── models/                  # Repository, architecture, domain, and business models
├── artifacts/               # Report, dashboard, Knowledge Hub, and diagram renderers
├── templates/               # Reference output templates
├── outputs/                 # Default generated artifacts
└── tests/                   # Scanner, analyzer, and end-to-end tests
```

[`skills/SKILL.md`](skills/SKILL.md) describes how the skill is invoked by its
host.
