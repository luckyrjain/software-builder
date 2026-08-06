# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a repo with pr-review, k8s-overprovisioning-datadog, and
incident-rca each already working interactively (see each skill's own `reference/smoke-test.md` to
confirm those first), a `release_manifest` with 2 entries, at least one repo with ≥1 MR merged since its
`since` marker, and at least one service with a recent observability error/infra signal (Datadog or the
configured incident-rca alternative) to exercise the Phase 1 "stop here" path, not just the clean path.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `release_manifest: [{repo: <repo>, service: <service>, since: <tag-or-timestamp>}, ...]`

Example: `release_manifest: [{repo: api-disbursement, service: disbursement-service, since: v2.3.0}]`

## Expected first output

MR-range resolution announced per repo (tag/timestamp resolved, MR count found), before any pr-review
invocation starts.

## A correct minimal output contains

1. **Every resolved MR reviewed via pr-review** — no inline GitLab posts, regardless of which posting
   mode pr-review's own Phase 0 detects. If it detects a write-capable mode, Phase 3 fires and is
   answered "Hold — don't post" per [gate-policy.md](gate-policy.md) — verify this actually happens
   (inspect the invocation), don't assume `chat-only` is guaranteed.
2. **Every manifest service gets a k8s verdict**, surfaced unmodified.
3. **Every manifest service gets an incident-rca Phase 1 pass**, always stopped at the checkpoint per
   [reference/gate-policy.md](gate-policy.md) — verify by inspecting the invocation (Phase 2 never
   starts), not just the summary.
4. **`RELEASE_READINESS_REPORT.md` produced**, per [reference/report-format.md](report-format.md), with
   correct MRs-reviewed / per-service rightsizing / per-service incident-signal sections — every manifest
   entry present, none silently dropped.

## Pass criteria

- No GitLab post (in any posting mode pr-review's Phase 0 might detect), no k8s manifest change, no
  incident-rca continuation past Phase 1.
- Overall verdict matches the derivation rule in [report-format.md](report-format.md) exactly, including
  `insufficient_metrics` and unresolved-`since` entries counting toward `UNKNOWN` (not `NOT_READY` —
  an evidence gap is not a proven blocker) and a flagged incident signal alone counting toward
  `CONDITIONAL` (not `NOT_READY`).
- A repo with zero MRs since `since` still appears in the report, not omitted.
- A repo whose merged-MR count exceeds one API page still returns the full set — verify pagination
  actually ran to completion (test against a repo with enough merges to force ≥2 pages if possible).

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| GitLab MCP server has no merge-date filter param | Falls back to client-side filtering of all merged MRs against `target_branch` by `merged_at`, still paginated exhaustively — not a smaller, silently-incomplete set |
| pr-review's Phase 0 detects a write-capable mode (`full`/`summary-only`/`general-only`) | Phase 3 posting confirmation fires per MR — answered "Hold — don't post"; same never-posts outcome as `chat-only` |
| incident-rca Phase 1 finds a strong signal | Answered "stop here" anyway — service flagged, full RCA never runs |
| incident-rca Phase 1 finds no signal | Service marked clear, partial report accepted as-is |
| A `release_manifest` entry's `since` is an unresolvable tag | Recorded as unresolved in the report per `workflow/run-check.md` § 1 — not silently skipped, counted toward `UNKNOWN` |
| k8s can't resolve a service after ≥2 tag strategies | Answered "proceed with unknown" — recorded as `insufficient_metrics`, counted toward `UNKNOWN`, never upgraded to `READY` |
| Datadog is unavailable but Kubernetes MCP supplies sufficient rightsizing evidence | The source-scoped Datadog failure is preserved in the k8s source profile; the service assessment continues and its degraded verdict is recorded as-is |
| Kubernetes MCP is unavailable but Datadog supplies sufficient rightsizing evidence | The source-scoped Kubernetes failure is preserved; the service assessment continues with the live-state verification gap stated explicitly |
