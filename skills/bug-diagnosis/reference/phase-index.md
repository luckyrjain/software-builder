# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `symptom`, `repro_hint` |
| **Repro** | [workflow/repro.md](../workflow/repro.md) | `repro_status`, `repro_evidence` |
| **Hypotheses** | [workflow/hypotheses.md](../workflow/hypotheses.md) | `hypotheses_tested`, `root_cause` |
| **Report** | [workflow/report.md](../workflow/report.md) | `BUG_DIAGNOSIS_REPORT.md`, `bug_diagnosis_report` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| A bug, test failure, or perf regression needs its root cause found | Inputs → Repro → Hypotheses → Report |
| No `symptom` named | Inputs HARD STOP — ask; no Repro phase |
| `repro_hint` supplied | Repro verifies it against evidence rather than deriving one from scratch |
| No `repro_hint` supplied | Repro must derive one from the symptom and code/tests; absence of a hint is not evidence the bug can't be reproduced |
| A hypothesis is actively falsified and rejected | Hypotheses records it with the evidence that rejected it; Report lists it |
| No hypothesis survives falsification | `root_cause` remains unresolved; Report states this explicitly, no guessed cause |
| Evidence reveals a live production incident with an active time window | Offer `incident-rca`; do not continue this workflow |
| Root cause is confirmed and ready to fix | Report offers `loop-task-implementer`; do not apply the fix here |
| Root cause is structural, not a local bug | Offer `codebase-architecture-review`; do not widen to a full audit here |
