# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a short PRD/proposal and a design description that
together describe a real (even if small) architectural decision — enough content to exercise every
required check, not just a one-line stub.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `proposal_text: <PRD or proposal text>`, `design_description: <proposed architecture description>`

Example: `proposal_text: "Add a notifications service..."`, `design_description: "Single Postgres-backed
worker polling every 5s, fanning out to email/SMS providers..."`

## A correct minimal output contains

1. **Inputs resolved** — `proposal_text` and `design_description` both present (no HARD STOP), any
   supplied `diagram_description`/`repo_context` noted as available or explicitly absent.
2. **Every required check run** — architecture decision, risks, scale limits, failure modes, security,
   operability, alternatives considered — each present in the analysis even when clean.
3. **`ARCHITECTURE_REVIEW_REPORT.md` produced**, per [reference/report-format.md](report-format.md),
   with all seven `##` sections in fixed order, none silently dropped.
4. **A verdict line** — `**Decision: <one of the four enum states>**` — matching the derivation rule in
   [report-format.md § Rules](report-format.md#rules), with a one-line contributing-finding summary
   whenever the verdict is not `Approved`.
5. **Confirmation of the deliverable path** — `ARCHITECTURE_REVIEW_REPORT.md` named as the output, no
   ticket/chat write-back attempted (read-only, markdown-report-only skill).

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `design_description` is too sparse to evaluate failure modes (e.g. one sentence, no component detail) | Failure modes section records `Unknown` with the reason named, not a silently-clean "none found"; verdict driven to at least `Needs rework` per [report-format.md § Rules](report-format.md#rules) |
| No `diagram_description` supplied and the design has multiple services/trust boundaries | Security section's trust-boundary row is `Unknown — no diagram supplied`; if no other gap exists, this alone lands as a named condition under `Approved with conditions`, not a silent pass |
| No `repo_context` supplied | Any current-state cross-reference check is recorded `Unknown — no repo_context supplied`, not silently skipped |
| `proposal_text` or `design_description` absent | Inputs HARD STOP — ask, no Analyze |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
