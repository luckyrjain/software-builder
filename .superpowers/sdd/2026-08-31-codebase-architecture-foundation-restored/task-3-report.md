# Task 3 Report — codebase-architecture-review

## Status

Completed. This change implements only Task 3: the complete `codebase-architecture-review` skill tree and
the exact codebase-architecture-review contract assertion in the existing foundation test. No registry,
central routing, Make target, evaluation, generated projection, or unrelated test was changed.

## Files changed

| File | Change |
|------|--------|
| `scripts/tests/test_codebase_architecture_foundation.py` | Added the exact required `test_codebase_architecture_review_contract_is_evidence_gated_and_read_only` assertion. |
| `codebase-architecture-review/SKILL.md` | Added the ambient, read-only, report-only orchestrator (99 lines). |
| `codebase-architecture-review/README.md` | Added purpose, scope, budgets, degraded-history behavior, and pipeline summary. |
| `codebase-architecture-review/SETUP.md` | Added prerequisites, directory map, framework links, and smoke-test entrypoint. |
| `codebase-architecture-review/CHANGELOG.md` | Added the 1.0.0 initial-release entry. |
| `codebase-architecture-review/examples.md` | Added bounded, degraded-history, zero-candidate, no-refactor, and routing-boundary examples. |
| `codebase-architecture-review/workflow/scope.md` | Added explicit scope and hard limits for 200 fully read files, 3 hotspots, 200 commits, and 180 days. |
| `codebase-architecture-review/workflow/evidence.md` | Added an evidence ledger, classification rules, and degraded-history restrictions. |
| `codebase-architecture-review/workflow/candidates.md` | Added evidence-gated candidate formation and all required candidate fields. |
| `codebase-architecture-review/workflow/falsify.md` | Added the required counterevidence pass for every candidate. |
| `codebase-architecture-review/workflow/report.md` | Added report-only emission rules for `CODEBASE_ARCHITECTURE_REVIEW.md` / `codebase_architecture_report`. |
| `codebase-architecture-review/reference/phase-index.md` | Added progressive Scope → Evidence → Candidates → Falsify → Report loading. |
| `codebase-architecture-review/reference/lazy-load-index.md` | Added one-at-a-time reference loading. |
| `codebase-architecture-review/reference/report-format.md` | Added the normative report schema, candidate fields, falsification table, degraded-history behavior, and fixed `recommended_next_skill: null`. |
| `codebase-architecture-review/reference/smoke-test.md` | Added minimal and degraded-path checks. |
| `codebase-architecture-review/reference/pressure-tests.md` | Added scope, evidence, candidate, falsification, and prompt-injection pressure cases. |
| `.superpowers/sdd/2026-08-31-codebase-architecture-foundation-restored/task-3-report.md` | Added this implementation and verification record. |

## Design decisions

- Followed the existing module-design pattern: a compact root `SKILL.md`, progressive workflow phases, and
  lazily loaded references. `SKILL.md` is 99 lines, below the 180-line cap.
- Linked the existing shared `codebase-design-principles.md` as normative doctrine and did not duplicate a
  competing vocabulary.
- Made the review ambient/read-only/report-only. It never refactors automatically, changes repository state,
  registers a downstream skill, or invokes one; report metadata always sets `recommended_next_skill: null`.
- Bounded analysis to at most 200 fully read files, 3 hotspots, and optional Git history of at most 200
  commits within 180 days. When history is unavailable, the workflow omits churn/co-change claims and lowers
  confidence for conclusions that would depend on history.
- Made candidate formation evidence-gated and required every candidate's ID, scope, friction, evidence,
  contract/seam, hypothesis, locality, caller simplification, testing improvement, abstraction cost,
  migration risk, ADR interaction, and confidence.
- Required active falsification for every candidate. The valid outcome is 3–7 candidates only when supported;
  fewer or zero candidates are explicitly valid.
- Linked the shared prompt-injection, safe-output, and cross-skill-escalation guidance rather than copying
  those contracts.

## Commands and results

| Command | Status | Exact output / result |
|---------|--------|-----------------------|
| `python -m pytest -q scripts/tests/test_codebase_architecture_foundation.py` | Expected RED routing failures | `4 failed, 3 passed in 0.57s`, exit 1. The four failures are the preserved Task 0 routing assertions: existing-codebase owner, module-seam owner, architecture-review owner, and system-design owner. The shared-doctrine, module-design, and new codebase-architecture-review structural assertions passed. |
| Local Python contract/tree/link/line-count check | PASS | `contract: PASS (14 assertions)`; `tree: PASS (15 required files)`; `links: PASS (51 local file links)`; `line-count: PASS (99 <= 180)` |
| `python -m pytest -q scripts/tests/test_codebase_architecture_foundation.py -k codebase_architecture_review` | PASS | `1 passed, 6 deselected in 0.04s` |
| `git diff --cached --check` | PASS | No output; exit 0. |

## Concerns

- No Task 3 blocker remains.
- The four routing assertions remain RED by design and were not changed, per the Task 3 instruction. They
  require the later registry/routing work and are outside this task's scope.
