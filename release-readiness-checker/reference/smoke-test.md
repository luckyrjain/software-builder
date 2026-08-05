# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a repo with pr-review, k8s-overprovisioning-datadog, and
incident-rca each already working interactively (see each skill's own `reference/smoke-test.md` to
confirm those first), a `release_manifest` with 2 entries, at least one repo with ≥1 MR merged since its
`since` marker, and at least one service with recent Datadog error/infra signal (to exercise the Phase 1
"stop here" path, not just the clean path).

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `release_manifest: [{repo: <repo>, service: <service>, since: <tag-or-timestamp>}, ...]`

Example: `release_manifest: [{repo: api-disbursement, service: disbursement-service, since: v2.3.0}]`

## Expected first output

MR-range resolution announced per repo (tag/timestamp resolved, MR count found), before any pr-review
invocation starts.

## A correct minimal output contains

1. **Every resolved MR reviewed via pr-review `chat-only`** — no inline GitLab posts, no live posting
   confirmation (mode has none to answer).
2. **Every manifest service gets a k8s verdict**, surfaced unmodified.
3. **Every manifest service gets an incident-rca Phase 1 pass**, always stopped at the checkpoint per
   [reference/gate-policy.md](gate-policy.md) — verify by inspecting the invocation (Phase 2 never
   starts), not just the summary.
4. **`RELEASE_READINESS_REPORT.md` produced**, per [reference/report-format.md](report-format.md), with
   correct MRs-reviewed / per-service rightsizing / per-service incident-signal sections — every manifest
   entry present, none silently dropped.

## Pass criteria

- No GitLab post, no k8s manifest change, no incident-rca continuation past Phase 1.
- Overall verdict matches the derivation rule in [report-format.md](report-format.md) exactly.
- A repo with zero MRs since `since` still appears in the report, not omitted.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| GitLab MCP server has no merge-date filter param | Falls back to client-side filtering of all merged MRs against `target_branch` by `merged_at` — not a smaller, silently-incomplete set |
| incident-rca Phase 1 finds a strong signal | Answered "stop here" anyway — service flagged, full RCA never runs |
| incident-rca Phase 1 finds no signal | Service marked clear, partial report accepted as-is |
| A `release_manifest` entry's `since` is an unresolvable tag | Recorded as a gap in the report's Notes section, that entry's MR section marked unresolved — not silently skipped from the report entirely |
