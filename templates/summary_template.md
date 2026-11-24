# Summary template (reference skeleton)

Used as a reference for `render_summary_markdown()` in `onboarding_analyzer.py`.
Placeholders use `{{name}}` style.

```markdown
# Repository Overview — {{repository_name}}

{{summary}}

## Main technologies

{{#each main_technologies}}
- {{this}}
{{/each}}

## High-level structure

{{#each top_level_directories}}
- `{{this}}/`
{{/each}}

## Recommended files to read first

{{#each files_to_read_first}}
1. `{{this}}`
{{/each}}

## Build

{{#each build_instructions}}
- `{{this}}`
{{/each}}

## Test

{{#each test_instructions}}
- `{{this}}`
{{/each}}
```
