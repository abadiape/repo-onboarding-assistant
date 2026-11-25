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

The current scanner is deliberately lightweight and read-only. It uses
conventions and metadata; it does not parse source code into symbols, resolve
calls, execute project commands, or produce a dependency graph.

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

Run the skill from this directory:

```bash
pip install -r requirements.txt
python onboarding_skill.py /path/to/repository
python onboarding_skill.py /path/to/repository --output-dir ./my-output
```

By default, the skill writes these artifacts to `outputs/`:

- `summary.md` — technologies, repository structure, reading suggestions, and
  documented setup/CI commands
- `learning_path.md` — a suggested sequence for becoming productive
- `repository_map.json` — the serialized `RepositoryModel`, including
  normalized metadata, dependencies, directories, files, and detected patterns
- `dependency_graph.mmd` — declared dependency relationships in Mermaid
- `module_graph.mmd` — directory and file containment in Mermaid
- `architecture_overview.mmd` — technologies, major areas, entry points, and
  other recorded architecture facts in Mermaid
- `manifest.json` — artifacts registered through the harness API

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
3. **Relationship resolution.** Extract and resolve edges such as `contains`,
   `imports`, `calls`, `inherits`, `implements`, `registers`, `tests`, and
   `configures`. Parsing identifies syntax; resolving names, aliases,
   re-exports, conditional imports, and dependency injection is a separate
   problem.
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
