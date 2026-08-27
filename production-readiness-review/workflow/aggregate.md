---
workflow_version: 1.0
phase: aggregate
produces:
  - dimension_statuses
  - operational_evidence
  - verdict
consumes:
  - dimension_evidence
  - dispatch_log
  - criticality
  - ci_evidence
  - scm_policy_evidence
  - build_provenance_evidence
  - change_impact_evidence
  - deployment_risk_evidence
---

# Aggregate — evidence authority, operational gates, worst-first verdict

## 1. Apply the evidence-authority ladder to every dimension

For every dimension collected in Collect evidence and Dispatch, resolve its status using
[reference/evidence-authority-policy.md](../reference/evidence-authority-policy.md): decisive evidence
must trace to `repository`, `authoritative_host`, or `trusted_runtime` authority to set `PASS`. A
dimension whose only supporting evidence is `caller`-asserted or `model_knowledge`-derived is
`UNKNOWN`, never `PASS` — a trusted child producer (pr-review, a specialist) can never launder that
caller/model-knowledge-only evidence into a passing result on this skill's behalf.

## 2. Evaluate the four operational dimensions at the resolved criticality tier

Per [reference/operational-gates.md](../reference/operational-gates.md), evaluate ownership,
rollback/abort, post-deploy verification plan, and recovery against `criticality`:

- `tier0`/`tier1`/`unknown` — caller-only evidence is `UNKNOWN` for these dimensions, never `PASS`.
- `tier2`/`tier3` — caller-only evidence is at most `CONDITIONAL`, never `PASS`.
- Any tier — an authoritative "unowned" finding, or an authoritative proven-destructive-operation
  finding with no recovery path, is `FAIL`.

## 3. Derive the overall verdict — worst-first precedence

Precedence over every **required** dimension (`NOT_APPLICABLE` dimensions never count as evidence
toward `PASS` and never contribute to the verdict):

1. **`NOT_READY`** — any required dimension is `FAIL`.
2. **`UNKNOWN`** — no `FAIL`, and any required dimension is `UNKNOWN`.
3. **`CONDITIONAL`** — no `FAIL`/`UNKNOWN`, and any required dimension is `CONDITIONAL`.
4. **`READY`** — every required dimension is `PASS` or `NOT_APPLICABLE`.

Report the single highest-precedence state — never downgrade a `NOT_READY` condition because an
`UNKNOWN` one is also present, and list every contributing dimension (not just the one that set the
verdict) in the report.

## 4. Never let dispatch gaps silently pass

A specialist recorded `UNKNOWN` in Dispatch (incomplete mandatory input, `BLOCKED` child, or an
unavailable capability) counts as a required-dimension `UNKNOWN` here unless the change-impact evidence
marked it `NOT_APPLICABLE` — an unresolved dimension is never treated as passing evidence just because
no specialist ran.

## Required outputs

| Output | Required fields |
|--------|------------------|
| `dimension_statuses` | Every dimension (CI, code review, build provenance, SCM policy, change impact, deployment risk, each dispatched specialist, four operational gates) with its resolved status and evidence-authority trace |
| `operational_evidence` | Ownership, rollback/abort, post-deploy verification, recovery — status plus the authority level of the deciding evidence |
| `verdict` | `READY` / `CONDITIONAL` / `NOT_READY` / `UNKNOWN`, per the precedence above |
