# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `module_scope`, `repository_evidence`, `change_goal` |
| **Design** | [workflow/design.md](../workflow/design.md) | `module_contract`, `module_design_options`, `evidence_gaps` |
| **Report** | [workflow/report.md](../workflow/report.md) | `MODULE_DESIGN_SPEC.md`, `module_design_spec` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|------------------|----------|
| Concrete module and inspectable evidence | Inputs → Design → Report |
| No module path/responsibility or no repository evidence | Inputs HARD STOP — ask; no Design phase |
| Interface uncertainty after evidence review | Design compares two materially different designs |
| Scope becomes multi-module or architecture-wide | Offer the one applicable escalation; do not invoke it |
