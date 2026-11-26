# Learning-path template (reference skeleton)

Used as a reference for `render_learning_path_markdown()` in `onboarding_analyzer.py`.
Placeholders use `{{name}}` style.

```markdown
# Learning Path — {{repository_name}}

Suggested step-by-step onboarding path for a new developer. Business domains,
custom modules, and critical integrations lead the general architecture path
when the repository contains enough evidence to identify them.

{{#each learning_path}}
## Step {{step}}: {{title}}

{{detail}}

{{/each}}
## Files to read first

{{#each files_to_read_first}}
- `{{this}}`
{{/each}}

## Build & test cheat sheet

\```sh
{{#each build_instructions}}
{{this}}
{{/each}}
{{#each test_instructions}}
{{this}}
{{/each}}
\```
```
