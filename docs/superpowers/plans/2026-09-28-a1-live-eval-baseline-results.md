# A1 — certified live-eval baseline for loop-task-implementer (results table)

Resolves gap-backlog ticket A1, per the decision record at
[2026-09-28-a1-eval-baseline-decision-record.md](../specs/2026-09-28-a1-eval-baseline-decision-record.md).
Retroactively formalizes 6 real ticket executions run through the full doctrine chain
(architecture-review → system-design → change-impact-analyzer → implementation-planner →
loop-task-implementer's isolated Builder/Reviewer loop) in this session, against
`luckyrjain/software-builder`'s real `main` branch, with real GitHub Actions CI and real merges — not
mock-tool-simulated.

**Certification status: UNCERTIFIED — awaiting owner sign-off.** Per the decision record, "certified" means
the repo owner personally reviews this table and confirms it's accurate. This document is the artifact
that sign-off is being requested against.

**Regression threshold** (applies to any ticket added to this baseline going forward): CI green for the
exact merged head, and both review lenses (Safety/State, Contracts/Operations) clean before merge. Every
row below already cleared this bar — it is a restatement of the standing bar this session already enforced
on every merge, not a new metric being introduced retroactively.

## Results table

| Ticket | Scope | Design review rounds | Implementation review | CI | PR(s) | Merge commit(s) | Outcome |
|--------|-------|----------------------|------------------------|-----|-------|------------------|---------|
| F1 | Review-evidence-gate mechanism (Track B: CI job + Condition 1 static lock-safety classifier + Condition 2 bot-health monitoring), then **fully reversed** on owner decision (solo-maintainer repo, gate structurally unsatisfiable without a bot credential) | Architecture review + change-impact only (pre-dated this session's later multi-persona design-review pattern) | Dual-lens Builder/Reviewer, 2 generations on the build (round 1 caught a PR-forgeable trust-boundary bypass + a wrong-commit-SHA bug, round 2 clean), single clean pass on the removal | Green on every PR | #298, #299 (fixes), #300 (Condition 1), #302 (removal) | `8d6d1a9`, `41ccac6`, `7e66b6a`, `f17e994` | Merged, then deliberately reversed — a genuine policy correction, not a failure; both the build and the reversal went through the same rigor |
| A5 | Durable `plan_execution_state` store (`plan_state_store.py`) + Builder checkpoint push cadence | Architecture review + change-impact only | Dual-lens, clean first pass (Lens A ran a real 8-process concurrent CAS stress test, 120/120 no lost updates) | Green | #301 | `627a0fa` | Merged, clean |
| A6 | `.claude/settings.json` permission template (repo's first host-enforced control) + `task_lease.py` mutual-exclusion primitive | **2 rounds** adversarial 3-persona review (round 1 found a real secret-exfiltration chain in the original allow-list; round 2 found 2 more exploit chains, resolved by narrowing scope rather than adding more deny rules) | Dual-lens, clean | Green; post-merge live-verified against the real host (deny rules confirmed blocking, including inside compound commands) | #303 | `22e024c` | Merged, clean, with rare post-merge live verification of the security control's real-world behavior |
| F4 | `pr-gatekeeper`'s idempotency-store hardening (lock timeout, fsync, signal forwarding) | **4 rounds** — rounds 1-2 built and found bugs in process-group reaping/kill-escalation/ordinal-reordering machinery, converged on an **owner-driven descope** to a much narrower fix; rounds 3-4 confirmed the narrower fix clean | Dual-lens, clean, 20/20 tests (11 new real-subprocess tests) | Green | #308 | `92c3da8` | Merged, clean — notable for the mid-flight scope correction, not just the final design |
| F2 | Per-skill `platforms` registry field + install-time enforcement — the highest-criticality ticket this session ran (shared registry parse-path code, all ~50 skills) | **4 rounds** — found and fixed a detection-rule bug that would've misclassified the two flagship skills, an architecture mismatch with the real fragment-merge registry, a circular-recursion trap, and a single-point-of-repo-wide-failure bug; round 4 converged CLEAN | Dual-lens, clean, both lenses independently re-ran the 4899-test suite and `make generate --check` themselves rather than trusting the Builder's report | Green (9/9) | #309 | `6a40c54` | Merged, clean — the deepest review this session ran, proportional to genuinely the highest blast radius |
| F2-followup | Small, disclosed follow-up: explicit `platforms: [posix]` override for `loop-task-implementer`, found during F2's own rollout | None needed — trivial, mechanical application of an already-reviewed mechanism to a third skill, no new design decision | Single reviewer pass (both lenses' concerns folded into one, proportional to a 9-line diff), clean | Green (9/9) | #310 | `a05feaf` | Merged, clean |

## What this table does and does not show

- **6 of the originally-targeted 5-10 runs.** Per the decision record, judged representative (spans a new
  build, a full reversal, two core-executor changes, one high-criticality shared-code change, and a small
  follow-up) and not padded to hit a round number.
- **Tokens and wall-clock time are not tracked** — A1's original acceptance criteria named these as metrics
  to record; this session did not capture them per-ticket, and fabricating numbers now would violate this
  repo's own evidence-over-prose doctrine. Disclosed as a real gap, not silently omitted. A future
  extension of this baseline should capture these if they're judged to matter — `skills/loop-task-implementer/scripts/run_log.py`'s
  own token/cost telemetry (from ticket A3) is the natural source, but no tooling currently extracts it into
  this table's format.
- **Design-review round counts vary hugely** (0 dedicated multi-persona rounds for F1/A5, up to 4 for F4/F2)
  — this is real, observed variance in how much adversarial scrutiny different classes of change actually
  needed, not an inconsistency in process. Roughly: changes confined to one skill's own file needed fewer
  rounds; changes touching shared, high-blast-radius code (F2's registry parse-path, F4's initially
  over-scoped signal-handling machinery) needed more.
- **Every single row cleared the regression threshold** (CI green, both lenses clean before merge) — 0 of 6
  merged with an unresolved review finding or failing CI at the merged head.
