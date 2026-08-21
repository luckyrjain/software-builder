# Smoke test — expected minimal output

Run after install **and** after any edit to this skill (SKILL.md, workflow/*.md,
reference/state-schema.yaml, or `scripts/validate_loop_lifecycle.py`). Use a small repo with at least one
open, well-scoped task and repository write access.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> Use loop-task-implementer to implement `<task>` and open a PR.

Example: `Use loop-task-implementer to implement issue 42, review it deeply, fix findings, and open a PR.`

## A correct minimal run contains

1. **Policy discovery** — Orchestrator states default/protected branch, required checks, required approvals, and whether autonomous merge is authorized (default `false` unless explicitly granted).
2. **Fresh Builder dispatch** — a new/updated branch and pull request exist; Builder report includes `head_commit` and `changed_files`.
3. **Current change identity** — Orchestrator independently rebuilds/validates the shared `change_identity`; a legacy fingerprint alone is insufficient.
4. **Current requirements + branch state** — `task.requirements_ref` is object or explicit `null`; third-party state is an explicit boolean checked at the exact current head.
5. **Two Reviewer generations** — each returned lens result increments that lens's positive integer `review_generation` exactly once and clears prior isolation-exception fields. Do **not** advance `review_evidence_generation` yet; any prior evidence is intentionally stale while adjudication is incomplete.
6. **Adjudication before portable evidence** — adjudicate the returned result, normalize/validate its portable `review_evidence`, then persist `review_evidence_generation = review_generation` only with that newly validated evidence. Lifecycle `CLEAN` requires equality, complete inspection, no unavailable surfaces, and zero portable defects.
7. **Freshness reruns** — content/requirements/conflict/accepted-third-party changes invalidate affected evidence. Same-head reviewer reruns also increment `review_generation`; until their new evidence is validated, old `review_evidence_generation` must remain stale. A degraded-isolation exception is bound to the exact current identity and generation.
8. **Crash/resume fail-closed check** — simulate stopping after `review_generation` increments but before new evidence persists. The old CLEAN evidence must not satisfy readiness because `review_evidence_generation != review_generation`.
9. **Authoritative current-head CI** — required CI is green and `ci.commit` equals `workspace.current_head_commit`.
10. **Executable lifecycle gate** — resolve actual skill root, use Python 3 (`python3` on Unix/macOS), and run `python3 "<skill_root>/scripts/validate_loop_lifecycle.py" --state "<state.json>"`. Only exit `0` establishes readiness; missing interpreter/validator or runtime/input inability blocks.
11. **Completion response** — report current identity, both lens review/evidence-generation states, isolation state, third-party check, current-head CI, lifecycle result, merge authority, and exact human action.
12. **No unauthorized merge** — without explicit merge authority, stop at verified readiness.

## Degraded path

When the host has no true isolation primitive, sequential context resets are a fallback. Preserve actual `isolation_status`; a `NOT_ISOLATED` lens needs explicit human acceptance with provenance bound to exact `reviewed_change_identity` and current `review_generation`.

## Deep edge cases

See [pressure-tests.md](pressure-tests.md) for same-head reruns, crash/resume between reviewer return and evidence persistence, stale-head CI, stale third-party checks, exception reuse, validator fail-closed behavior, conflict transitions, and rendering attacks.

## Pass criteria

- `change_identity`, requirements, both lens evidence envelopes, branch-change evidence, and CI describe the same current change/head.
- Every CLEAN lens has positive integer `review_generation` and `review_evidence_generation == review_generation`.
- A reviewer generation advanced without current-generation evidence remains lifecycle-blocked.
- Any degraded-isolation exception matches the exact `reviewed_change_identity` and current `review_generation`.
- The lifecycle validator was actually executed from resolved skill root with Python 3 and returned exit `0` immediately before readiness/completion.
- No merge occurred without explicit authorization; reviewers performed no repository writes; accepted findings have evidence-backed resolution.
