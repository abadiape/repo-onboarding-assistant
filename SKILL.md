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

Out of scope for the MVP: architecture graphs, dashboards, AST analysis,
dependency graphs, Mermaid diagrams, security analysis.

## How it works

1. **Repository Scan Capability** (`repository_scan.py`, local to the skill) —
   convention-based inspection of filenames and manifest contents builds a
   `RepositoryInventory` (see `models.py`): languages, frameworks, package
   managers, build tools, test frameworks, important files, CI/CD files,
   top-level directories, entry points, build/test instructions, and onboarding
   documents. Markdown setup guides are scanned for shell commands in relevant
   fenced code blocks, and CI YAML files are checked for inline `run` steps.
   Commands are reported with their source and section and are never executed.
2. **Onboarding Analyzer** (`onboarding_analyzer.py`) — heuristic insights on
   top of the inventory: summary, main technologies, learning path,
   files-to-read-first, project-specific setup guidance, and build/test cheat
   sheet.
3. **Artifact Generation** (`onboarding_skill.py`) — writes artifacts via
   `ArtifactRegistry` and returns a harness `SkillResult`.

## Usage

```bash
pip install llm-harness-lite pytest
python onboarding_skill.py /path/to/repository
python onboarding_skill.py /path/to/repository --output-dir ./my-output
```

Output (`outputs/` by default):

- `summary.md` — repository overview in Markdown
- `learning_path.md` — step-by-step suggested onboarding path
- `repository_map.json` — structured repository inventory
- `manifest.json` — generated automatically through `ArtifactRegistry`

The skill returns:

```python
SkillResult(
    summary="Repository onboarding analysis completed",
    artifacts=[...],  # summary.md, learning_path.md, repository_map.json, manifest.json
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
├── SKILL.md
├── skill.yaml
├── onboarding_skill.py      # skill entrypoint + Artifact generation + CLI
├── repository_scan.py       # Repository Scan Capability (local to skill)
├── onboarding_analyzer.py   # heuristic insights over the inventory
├── models.py                # RepositoryInventory model
├── templates/               # reference Markdown skeletons
├── outputs/                 # generated artifacts (default target)
└── tests/                   # pytest suite with synthetic fixture repos
```

## Tests

```bash
pytest tests/ -v
```
