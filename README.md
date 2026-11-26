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

Documented commands are surfaced as evidence, not executed. Build and test
suggestions inferred from manifests are heuristics; the commands declared by
the project or its CI should be preferred when they disagree.

## Analyzer extensions

`analyzers.py` runs `GenericAnalyzer` followed by each applicable language
analyzer. Implement the small `Analyzer` interface (`supports` and `analyze`),
then add the analyzer to `DEFAULT_ANALYZERS`; callers can also pass a custom
analyzer sequence to `scan_repository`. Analyzers enrich `RepositoryModel`;
artifact renderers consume that model separately from scanning.
`architecture_analyzer.py` extracts a framework-aware `ArchitectureModel`
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
only the architectural layers supported by the detected components.
Diagrams focus on the analyzed repository's components and inferred
relationships, not the scanner pipeline or a dependency inventory.

`repository_relevance.py` classifies project, infrastructure, vendor, and
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
python onboarding_skill.py /path/to/repository
python onboarding_skill.py /path/to/repository --output-dir ./my-output
python onboarding_skill.py /path/to/repository --module-graph app/code/Company/Module
```

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
- `system_overview.mmd` — high-level component relationship diagram
- `execution_flow.mmd` — inferred application execution sequence
- `subsystem_map.mmd` — components grouped by architectural boundary
- `dashboard.html` — standalone onboarding dashboard with embedded diagram
  source, rendered Mermaid diagrams, and learning-path content
- `manifest.json` — artifacts registered through the harness API

The dashboard loads a pinned Mermaid.js release from jsDelivr to render the
diagrams. The HTML and Mermaid source are embedded in the artifact; if the CDN
is unavailable, users can still view or copy the Mermaid source.
Execution-flow diagrams depict a likely conceptual path through relationships,
not observed runtime events; imports and references are not proof of calls.
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
├── SKILL.md                 # Skill/runtime instructions
├── skill.yaml               # Harness skill metadata
├── onboarding_skill.py      # CLI, artifact generation, SkillResult boundary
├── repository_scan.py       # Local repository scanner
├── analyzers.py             # Generic and language-specific model enrichers
├── onboarding_analyzer.py  # Onboarding heuristics and Markdown rendering
├── models.py                # RepositoryModel and normalized records
├── templates/               # Reference output templates
├── outputs/                 # Default generated artifacts
└── tests/                   # Scanner, analyzer, and end-to-end tests
```

`SKILL.md` describes how the skill is invoked by its host. This README describes
the project, the current scanner boundary, and the planned evolution of the
shared inventory.
