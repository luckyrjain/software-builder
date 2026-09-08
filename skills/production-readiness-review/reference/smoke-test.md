# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a real PR/MR with at least one required CI check, at
least one approval/policy signal, and a change shape that triggers at least one specialist dispatch
(e.g. a schema migration or a public API change) — plus a second run against a change with no
triggering surface, to exercise the all-`NOT_APPLICABLE`-specialists path too.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `assessment_target: {project: <project>, merge_request_iid: <iid>}`

Example: `assessment_target: {project: api-disbursement, merge_request_iid: 482}`

## Expected first output

`assessment_target` and resolved `criticality` announced, before any child invocation starts.

## A correct minimal output contains

1. **pr-review invoked exactly once**, retrospective mode, `posting_policy: forbidden` — no inline
   post to the PR/MR, regardless of which posting mode pr-review's own Phase 0 detects.
2. **change-impact-analyzer and deployment-risk-review reused or refreshed** — their own verdicts
   surfaced as-is.
3. **Every specialist named in the change-impact evidence dispatched with a fully-assembled mandatory
   input** — per [reference/child-input-map.md](child-input-map.md); a specialist with no triggering
   change class recorded `NOT_APPLICABLE`; a specialist whose mandatory input can't be fully assembled
   recorded `UNKNOWN`, never dispatched partially.
4. **The four operational gates evaluated at the resolved criticality tier** — per
   [reference/operational-gates.md](operational-gates.md).
5. **`production_readiness_report` produced**, per [reference/report-format.md](report-format.md),
   with every evaluated dimension present, none silently dropped.

## Pass criteria

- No merge, deploy, or rollback action taken by this skill or any invoked child.
- No PR/MR post from pr-review in any posting mode.
- Overall verdict matches the derivation rule in
  [gate-policy.md § Verdict precedence](gate-policy.md#verdict-precedence) exactly, including a
  knowingly-incomplete specialist input counting toward `UNKNOWN` (not `NOT_READY`, not `READY`) and a
  `NOT_APPLICABLE` specialist never counting toward `PASS`.
- A `tier0`/`tier1`/`unknown`-criticality target with only caller-asserted operational evidence lands
  those gates `UNKNOWN`, never `PASS`.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `host.ci.status` unavailable | CI dimension `UNKNOWN`, not assumed passing |
| `host.scm.policy.read` unavailable | SCM policy dimension `UNKNOWN` |
| `host.build.provenance.read` unavailable and a build step is known to exist | Build provenance `UNKNOWN`, never silently `NOT_APPLICABLE` |
| `host.service.metadata.read` unavailable | Criticality stays `unknown`; ownership/recovery operational gates `UNKNOWN` unless another authoritative source resolves them |
| A specialist's mandatory input can't be fully assembled | That specialist is not invoked; dimension `UNKNOWN` with the missing-field reason recorded |
| A dispatched child returns `BLOCKED` on what would have been an interactive question | Dimension `UNKNOWN`, block reason retained in `evidence_refs`; no live prompt rendered mid-aggregation |
| pr-review's Phase 0 detects a write-capable posting mode | Any Phase 3 confirmation it still renders is answered "Hold — don't post"; same never-posts outcome as `chat-only` |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
