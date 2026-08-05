# Phase index

**One `workflow/` file per phase** — do not advance until [phase-exit-criteria.md](phase-exit-criteria.md) for
that step passes (or user opts to stop). Each workflow file declares `workflow_version`, `produces`, and
`consumes`.

| Step | Read now | Produces | Exit check |
|------|----------|----------|------------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `from_time`, `to_time`, anchors | [§Inputs](phase-exit-criteria.md#inputs) |
| **Phase 0** | [workflow/phase-0.md](../workflow/phase-0.md) | `mcp_profile`, `cli_available` | [§Phase 0](phase-exit-criteria.md#phase-0-mcp-capability-check) |
| **Phase 0b** | [workflow/phase-0b.md](../workflow/phase-0b.md) | refined window *(Jira only)* | [§Phase 0b](phase-exit-criteria.md#phase-0b-jira-anchored-window-inc-xxxx-path-only) |
| **Phase 1** | [workflow/phase-1.md](../workflow/phase-1.md) | `error_signals`, `infra_signals`, `query_signals` | [§Phase 1](phase-exit-criteria.md#phase-1-symptom-detection) |
| **Phase 2** | [workflow/phase-2.md](../workflow/phase-2.md) | `deploy_events` | [§Phase 2](phase-exit-criteria.md#phase-2-change-correlation) |
| **Phase 3** | [workflow/phase-3.md](../workflow/phase-3.md) | `jira_issues`, timeline, `query_signals` | [§Phase 3](phase-exit-criteria.md#phase-3-tickets-timeline-query-investigation) |
| **Phase 4** | [workflow/phase-4.md](../workflow/phase-4.md) | `evidence_json`, `ranked_hypotheses`, `causal_graph`, `evidence_coverage` | [§Phase 4](phase-exit-criteria.md#phase-4-correlate-rank) |
| **Phase 5** | [workflow/phase-5.md](../workflow/phase-5.md) | `rca_report` | [§Phase 5](phase-exit-criteria.md#phase-5-render-report) |

Precedence: [precedence.md](precedence.md). Reference loads: [lazy-load-index.md](lazy-load-index.md).

Quick paths:

| User asks | Phases |
|-----------|--------|
| Named service + window | Inputs → 0 → 1 → 2 → 3 → 4 → 5 |
| `INC-xxxx` (Jira) | Inputs → 0 → **0b** → 1 → 2 → 3 → 4 → 5 |
| Symptom only | Inputs → 0 → 1 (org-wide → top 3) → confirm → 2 → 3 → 4 → 5 |
| "Was it the deploy?" | Inputs → 0 → 2 → 1 → 4 → 5 |
