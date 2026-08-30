# production-readiness-review

**Production readiness verdict** for one PR/MR/release-candidate, composed over existing skills: it
never invents its own review logic — it gathers trusted evidence (CI, code review, build provenance,
SCM policy, change-impact, deployment-risk) and dispatches only the specialist reviews the evidence
says apply (security, observability, resilience, API design, database, performance, capacity,
dependency-upgrade), then aggregates everything into one fail-closed verdict. Read-only throughout —
it never posts, merges, or deploys.

## Why fail-closed

A dimension with no trace to authoritative evidence is `UNKNOWN`, never assumed clean. A specialist is
never dispatched with a knowingly-incomplete mandatory input — that dimension is `UNKNOWN` instead of a
guessed `PASS`. No child skill is ever handed merge, deploy, or rollback authority, and pr-review is
always invoked with posting held (`posting_policy: forbidden`), never conversationally declined per
invocation — see [reference/gate-policy.md](reference/gate-policy.md).

## What it does

1. **Resolves the assessment target** — an `mr_context` (project + MR/PR iid) or a direct
   release-candidate `source_revision`, plus its criticality tier when available.
2. **Collects evidence** — CI status, SCM policy (approvals/CODEOWNERS/branch rules), build
   provenance (source revision → deployable digest, or `NOT_APPLICABLE`), and a fresh or reused
   change-impact and deployment-risk assessment.
3. **Dispatches pr-review always** (posting forbidden) and **every specialist the change-impact
   evidence says applies** — never a specialist with a known-incomplete mandatory input; that
   dimension is recorded `UNKNOWN` instead.
4. **Aggregates** every dimension through the evidence-authority ladder
   ([reference/evidence-authority-policy.md](reference/evidence-authority-policy.md)) and the four
   tier-sensitive operational gates ([reference/operational-gates.md](reference/operational-gates.md)):
   ownership, rollback/abort, post-deploy verification plan, recovery.
5. **Emits `production_readiness_report`** — one worst-first verdict
   (`READY`/`CONDITIONAL`/`NOT_READY`/`UNKNOWN`) plus every dimension's own status, blockers,
   conditions, waivers, and required actions.

## When to use

| Use production-readiness-review | Use instead |
|----------------------------------|--------------|
| "Is this PR/MR/release-candidate production ready?" for one target | Generic correctness/regression review, no readiness verdict → **pr-review** directly |
| One change's fitness to ship, across CI/review/policy/specialist evidence | Multi-repo/multi-service release-wide go/no-go → **release-readiness-checker** |
| — | A standalone change-impact or blast-radius/rollback question → **change-impact-analyzer** / **deployment-risk-review** directly |
| — | One specialist's own question, no readiness verdict needed → that specialist skill directly |

## Invocation example

```
assessment_target: {project: api-disbursement, merge_request_iid: 482}
```

## What you get

`production_readiness_report` — format spec: [reference/report-format.md](reference/report-format.md).
Overall verdict (`READY`/`CONDITIONAL`/`NOT_READY`/`UNKNOWN`), per-dimension statuses (CI, code review,
build provenance, SCM policy, change-impact, deployment-risk, every dispatched specialist), the four
operational-gate findings, blockers, conditions, waivers, and required actions before shipping.

## Install

```bash
cd software-builder
make install-production-readiness-review
```

Restart Cursor. Requires **pr-review**, **change-impact-analyzer**, **deployment-risk-review**,
**security-review**, **observability-review**, **resilience-review**, **api-design-review**,
**database-review**, **performance-review**, **capacity-planner**, and **dependency-upgrade-review**
installed too (the make target chains all eleven automatically). MCP/host setup is each composed
skill's own — see [SETUP.md](SETUP.md).

## Related skills

- **pr-review** — does the actual code review; this skill always invokes it retrospectively with
  posting forbidden and reads its severity findings, never re-scoring them
- **change-impact-analyzer** / **deployment-risk-review** — do the actual impact/risk analysis; this
  skill refreshes or reuses their reports as dispatch prerequisites
- **security-review**, **observability-review**, **resilience-review**, **api-design-review**,
  **database-review**, **performance-review**, **capacity-planner**, **dependency-upgrade-review** —
  each does its own specialist analysis; this skill only decides which apply and reads their verdicts
  as-is
- **release-readiness-checker** — a different composition, for a multi-repo/multi-service release
  sweep, not a single-target readiness verdict

Agent instructions: [SKILL.md](SKILL.md).
