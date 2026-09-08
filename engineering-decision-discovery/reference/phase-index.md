
# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `decision_scope`, `repository_evidence`, `interaction_policy` |
| **Tree** | [workflow/tree.md](../workflow/tree.md) | `decision_tree` |
| **Frontier** | [workflow/frontier.md](../workflow/frontier.md) | `frontier` |
| **Interaction** | [workflow/interaction.md](../workflow/interaction.md) | `resolved_decisions`, `unresolved_decisions`, `recommendations`, `alternatives_rejected` |
| **Report** | [workflow/report.md](../workflow/report.md) | `ENGINEERING_DECISION_RECORD.md`, `engineering_decision_record` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| Bounded `decision_scope` with inspectable evidence | Inputs → Tree → Frontier → Interaction → Report |
| `decision_scope` missing or unbounded | Inputs BLOCKED — ask; no Tree phase |
| Evidence shows the question is already settled | Tree may return zero nodes; Report states why, without an interview |
| `interaction_policy.unattended: true` and a material frontier remains at completion | BLOCKED with the frontier attached, per [workflow/frontier.md](../workflow/frontier.md) |
| `interaction_policy.human_available: false` | Frontier and recommendations computed, but Interaction never asks — see [workflow/interaction.md](../workflow/interaction.md) |
| User explicitly leaves a frontier node unresolved | Interaction records it and moves on; Report lists it under `unresolved_decisions`, not `resolved_decisions` |
| Resolved decisions describe one module or span multiple modules | Offer the one applicable escalation; do not invoke it |
