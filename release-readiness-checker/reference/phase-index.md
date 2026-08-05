# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `release_manifest`, `incident_lookback_hours`, `target_branch` |
| **Run check** | [workflow/run-check.md](../workflow/run-check.md) | `RELEASE_READINESS_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| `release_manifest` with 2 repos, 1 service each | Inputs → Run check (MR-range resolve → pr-review chat-only per MR → k8s per service → incident-rca Phase-1-only per service) → `RELEASE_READINESS_REPORT.md` |
| A repo with zero MRs since `since` | Run check § 1 records "no changes this release" — not a HARD STOP |
| A service's incident-rca Phase 1 finds a strong signal | Run check § 4 answers "stop here" per [gate-policy.md](gate-policy.md) — full RCA never runs; service flagged |
| `release_manifest` empty | Inputs HARD STOP — ask, no Run check |
