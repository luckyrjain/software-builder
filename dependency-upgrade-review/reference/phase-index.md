# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `dependency_name`, `current_version`, `target_version`, `changelog_text`, `manifest_excerpt` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | `breaking_changes`, `cve_findings`, `api_differences`, `transitive_impact`, `rollout_risk` |
| **Report** | [workflow/report.md](../workflow/report.md) | `DEPENDENCY_UPGRADE_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| Dependency name + current/target version, changelog text, manifest excerpt | Inputs → Analyze → Report → full verdict |
| Dependency name only, no current or target version | Inputs HARD STOP — ask, no Analyze |
| No changelog text or no manifest excerpt supplied | Analyze records the gap → Report surfaces it as an explicit Unknown, not a silent Safe-to-upgrade |
