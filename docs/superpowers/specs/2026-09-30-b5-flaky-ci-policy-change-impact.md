# Change impact report — B5: flaky-CI rerun budget and flake classification

**Coverage status: COMPLETE**

## Assessment target

Proposed state. Repo: `luckyrjain/software-builder`, main, head includes merged PR #315 (B4). Sources:
`docs/superpowers/specs/2026-09-30-b5-flaky-ci-policy-design.md` (revision 4, converged across 4
adversarial review rounds, 3 personas — Security Architect and Software Architect converged clean at
round 2; SRE continued alone through round 4 on a real, narrowing security/precision thread) and
`docs/superpowers/specs/2026-09-30-b5-flaky-ci-policy-architecture-review.md` (Approved with conditions,
6 conditions, all addressed).

## Criticality: High

Not code size (the touched surface is modest) but blast radius, for a reason distinct from every prior
ticket this session: this is the **first** gap-backlog ticket in this session to modify `.claude/settings.json`
since gap-backlog A6 first introduced it as this repo's own first host-*enforced* (not
instruction-level) control. That file governs what commands any Orchestrator/Builder/Reviewer session may
run without a human prompt, repo-wide — a mistake here has a materially different blast radius than a
mistake in `orchestrator.md`'s prose (which an LLM merely *follows*, versus a permission pattern that is
*mechanically enforced*).

## Change classes

- `security-permission-surface-change` (**new class for this session** — `.claude/settings.json`)
- `new-validation-logic` (`run_log.py`'s `_validate_event_data` extension)
- `new-capability-declaration` (`mcp-capabilities.md`)
- `contract-change` (`state-schema.yaml`'s `failure_classification` enum, `budgets.max_ci_reruns`)
- `documentation-only` (`run-log.md`, `SKILL.md`, `platform-adapters.md`)
- `orchestrator-workflow-extension` (`orchestrator.md` §15/§3)

## Impacted services / files

| Path | Nature of change | Risk |
|------|-------------------|------|
| **`.claude/settings.json`** | 3 new allow-list entries: `gh run rerun --failed`, a job-level `conclusion` query, a run-level `conclusion`/`run_attempt` query | **Highest in this change, and a genuinely new risk class for this session.** Read directly: the file's existing entries are all simple literal-prefix-plus-wildcard patterns (e.g. `"Bash(gh pr view:*)"`) — there is no regex, no flag-order enforcement, no argument validation. Confirmed via `gh run rerun --help`: the command's real usage is `gh run rerun [<run-id>] [flags]` — the run-id is positional. A prefix pattern anchored on the literal string `"gh run rerun --failed"` only matches an actual invocation shaped `gh run rerun --failed <run-id>` (flag before the positional run-id) — **not** `gh run rerun <run-id> --failed` (the more natural, commonly-documented order). If an implementer writes the pattern against the wrong invocation order, the pattern silently never matches (harmless but broken — the Orchestrator can't rerun anything) or, worse, if an implementer "fixes" the mismatch by loosening the pattern to bare `"Bash(gh run rerun:*)"` to make it work, that pattern **also permits a bare `gh run rerun` with no `--failed` at all** — silently defeating the design's own explicit, adversarially-reviewed safety requirement (bare rerun re-executes the whole workflow, the exact budget-starvation risk round 1/2 found and fixed). This is precisely the class of exploitable-pattern-matching gap gap-backlog A6's own design review found and fixed in this same file (2 review rounds needed to close a real exploit chain in A6's original allow list, per the gap-reanalysis tracker) — recommend this be called out explicitly as a **required test**, not left to implementation-time discovery |
| `skills/loop-task-implementer/scripts/run_log.py` | New `_validate_event_data` branch for `ci_polled`, 4 fields, uniform "enforce only when present" rule; `CI_RERUN_EXHAUSTED` added to `REASON_CODES` | Low-moderate — additive, and the design's own Python code shape (given literally in the design doc) matches the function's existing style exactly |
| `skills/loop-task-implementer/reference/state-schema.yaml` | `ci.failure_classification`'s comment gains the 4-value enum; `budgets.max_ci_reruns: 1` added | Low — purely additive, no existing field's shape changes |
| `skills/loop-task-implementer/reference/run-log.md` | `ci_polled`'s payload row extended; `CI_RERUN_EXHAUSTED` added to the reason-code enumeration sentence | **Both edits are required, not optional** — confirmed the second one is enforced by an already-wired test, `test_reference_documents_every_event_actor_outcome_reason_and_exit_code` (`tests/test_run_log.py:2803-2810`), which asserts every `REASON_CODES` value appears in this file's text. Landing the `REASON_CODES` tuple entry without this doc edit fails CI deterministically |
| `skills/loop-task-implementer/reference/mcp-capabilities.md` | New capability row, explicitly scoped to structured job/run fields, never log content | Low — additive row, existing table format, fail-closed degraded path already specified |
| `skills/loop-task-implementer/SKILL.md` | New circuit-breaker bullet for `CI_RERUN_EXHAUSTED` | Low — this list is confirmed (by direct research across rounds) to already be non-1:1 with `REASON_CODES` (e.g. `TIME_BUDGET`/`TOKEN_BUDGET` share one bullet, `OTHER` has none) — adding one more bullet doesn't need to "restore" an invariant that never existed |
| `skills/loop-task-implementer/reference/platform-adapters.md` | New per-host permission-declaration note for non-Claude-Code hosts | Low, but genuinely necessary — this skill is explicitly host-agnostic (Cursor/Codex/Copilot/Kiro), and `.claude/settings.json` is a Claude-Code-specific mechanism; other hosts need their own equivalent statement or this feature silently doesn't work for them |
| `skills/loop-task-implementer/workflow/orchestrator.md` | §15 gains the eligibility gate (disqualifying-signal check, then job/run `conclusion` check for exactly `timed_out`/`startup_failure`), the `--failed`-specific rerun sub-flow, the resume-reconciliation rule; §3 gains the `max_ci_reruns` budget bullet | Moderate — the **7th** modification to this file this session (after A5, A6, B1, B2, B3, B4), a file the design itself and this session's own research repeatedly confirm is this repo's highest-blast-radius file. No structural insertion-point risk here comparable to B4's unnumbered-heading concern — this design's insertion is scoped entirely within the existing §15/§3, no new section boundary |
| `skills/loop-task-implementer/tests/test_run_log.py` | New pressure-test coverage, reject-then-iterate-accept convention matching `test_escalated_and_run_completed_take_a_closed_set_of_codes` exactly | Low — direct precedent already exists in this exact file |

**Confirmed untouched** (explicit, direct verification — zero mentions in the design doc for either):
`skills/loop-task-implementer/scripts/validate_loop_lifecycle.py` and
`skills/loop-task-implementer/workflow/reviewer.md`. Unlike B3/B4, this design's entire mechanism lives in
`orchestrator.md`/`run_log.py`/`state-schema.yaml`/`.claude/settings.json` — the Blocking standard (still
exactly 6 conditions, unaffected) and the finding output schema are completely untouched, matching the
design's own framing that this ticket's mechanism sits at a different layer (CI handling) than B3/B4's
Reviewer-adjudication machinery.

## Impacted contracts

- `ci.failure_classification` (v1, informal) — was permanently `null`; now a real 4-value enum, first
  actual use of a field declared since before this session began.
- `ci_polled` event payload — was undocumented/unenforced ad hoc; now has 4 optional-but-validated fields,
  following the module's own stated "codes not sentences" philosophy for the first time on this event.
- `REASON_CODES` closed set — extended by exactly one value (`CI_RERUN_EXHAUSTED`), with both cross-file
  parity obligations (`run-log.md`'s enumeration sentence; `SKILL.md`'s circuit-breaker list, confirmed
  non-1:1 already) accounted for in the design's own Rollout plan.
- `.claude/settings.json`'s permission-allow contract — extended for the first time since A6, the pattern
  matching risk above is the single most important thing for implementation to get right.

## Impacted data

`plan_execution_state` is **not** touched by this design at all (confirmed — no mention anywhere in the
design doc) — this distinguishes B5 cleanly from B3/B4, both of which required real
`scripts/implementation_plan.py` plumbing. `ci.*`/`budgets.*` are ordinary per-task workflow state, not a
durable composition artifact.

## Impacted dependencies

None new beyond the GitHub CLI (`gh`) itself, already an implicit dependency of every prior ticket that
used `gh pr`/`gh run` commands.

## Impacted owners

Single owner (CODEOWNERS root wildcard already covers every touched path) — no CODEOWNERS change needed.

## Required tests

1. **`.claude/settings.json` pattern-matching verification (the single most load-bearing new test for
   this ticket)**: confirm the literal allow-list pattern chosen for `gh run rerun --failed` actually
   matches the real invocation shape the Orchestrator will use (flag-before-positional:
   `gh run rerun --failed <run-id>`), and explicitly confirm the chosen pattern does **not** also match a
   bare `gh run rerun <run-id>` with no `--failed` — test both the positive (matches the intended,
   `--failed`-qualified invocation) and negative (rejects/doesn't match a bare rerun) cases directly against
   Claude Code's own settings-pattern matching behavior, not just by inspection.
2. **`ci_polled` seed/malformed-field tests**, per the design's own Rollout plan: reject-then-iterate-accept
   for all four new fields (`attempt`, `eligible_for_rerun`, `observed_signal`, `failure_classification`),
   confirming the "enforce only when present" rule holds for all four uniformly — the design's own code
   block should be used directly, not re-derived.
3. **`REASON_CODES`/`run-log.md` parity regression** — confirm
   `test_reference_documents_every_event_actor_outcome_reason_and_exit_code` still passes once
   `CI_RERUN_EXHAUSTED` is added to both `REASON_CODES` and `run-log.md`'s enumeration sentence (this
   existing test needs zero new code, only both edits landing together).
4. **Job-level vs. run-level query-shape distinction** — confirm the actual GitHub CLI/API calls the
   design specifies (`gh api .../actions/runs/{run_id}/jobs` or `gh run view --json jobs` for job-level
   `conclusion`; `gh run view --json conclusion,attempt` for run-level) both return the fields the design's
   Data model table claims, against a real CI run in this repo.
5. **The design's own documented pressure-test scenario** — a constructed (not historical, per the
   design's own honest disclosure) example: a required check failing with `conclusion: timed_out`, retried
   once via `--failed`, passing, classified `flaky_confirmed_transient`, with the `ci_polled` evidence trail
   showing both attempts distinctly.

## Operational impacts

1. **The permission-pattern risk (above) is the dominant operational concern of this entire ticket** —
   everything else is low-risk, additive documentation/schema work; this one item determines whether the
   feature works correctly, works not at all (safely broken), or accidentally reopens a bare-rerun budget
   risk this design spent 2 full rounds closing.
2. Real CI compute/time cost: one extra job run per eligible failure, capped at `max_ci_reruns: 1` —
   small, bounded, already disclosed in the design's own Capacity section alongside honest worst-case
   poll-budget arithmetic (40%+ of the 15-minute budget in the case where the slower required check is the
   one that flakes).
3. `platform-adapters.md`'s new per-host note is documentation-only for this ticket, but a real, disclosed
   functional gap for any non-Claude-Code host until that host's own equivalent permission grant is made —
   this feature is Claude-Code-only until then, which the design itself doesn't explicitly flag as a
   rollout-scoping decision (worth naming, not blocking).

## Review triggers

**None required.** Consistent with this session's own established precedent (B2/B3/B4): this design
underwent 4 rounds of dedicated adversarial multi-persona review (Security Architect, SRE, Software
Architect), each round independently re-verifying citations against live repository files (and, notably,
live `gh api`/`gh pr checks` data pulled from this repo's own real CI history), converging with zero
remaining `PROPOSED_BLOCKING` findings from all three personas by round 2 for two of three personas, and
by round 4 for the third. The one item flagged here as a required test (permission-pattern verification) is
an implementation-time empirical check, not an unresolved design question — the design's own text already
specifies exactly what to verify.

## Material unknowns

1. `max_ci_reruns: 1`'s correctness is genuinely unvalidated against a real required-check flake — the
   design's own Open Question 1, carried forward honestly (the only real precedent this session observed,
   `install-engine-windows` on PR #315, governs a non-required check and provides zero evidence for tuning
   this specific policy).
2. The narrowed 2-value qualifying-signal vocabulary (`TIMEOUT`/`PROVISIONING_FAILURE`) is deliberately
   incomplete — most real transient CI issues (rate limits, network blips) will fall to the existing,
   unchanged ambiguous-case judgment call rather than the new rerun path, a considered, disclosed
   trade-off (a smaller but honestly-verifiable set, not a broader but spoofable one), not a design flaw.
3. The `run_attempt` resume-reconciliation check has a disclosed out-of-band blind spot: a rerun triggered
   entirely outside this skill's own path (e.g. a human using `workflow_dispatch` directly) is invisible to
   it — the same class of gap every other budget/counter in this skill already has for direct human action,
   not a new risk this design introduces.

## Unknowns

None beyond the material unknowns above — repository read was available throughout, and both source
documents were read in full, along with direct verification of `.claude/settings.json`'s real pattern
syntax and `gh run rerun --help`'s real CLI usage.

## Evidence refs

- `docs/superpowers/specs/2026-09-30-b5-flaky-ci-policy-architecture-review.md`
- `docs/superpowers/specs/2026-09-30-b5-flaky-ci-policy-design.md` (revision 4)
- Direct repository verification: `.claude/settings.json` (confirmed literal-prefix-plus-wildcard pattern
  convention, no regex/flag-order enforcement), `gh run rerun --help` (confirmed `[<run-id>] [flags]`
  positional-then-flags usage), `skills/loop-task-implementer/scripts/run_log.py`
  (`_validate_event_data`, `REASON_CODES`, `EVENTS`), `skills/loop-task-implementer/reference/state-schema.yaml`
  (`ci:`/`budgets:` blocks), `docs/github-ruleset-main.json` (`required_check_contexts`), confirmed zero
  mentions of `reviewer.md`/`validate_loop_lifecycle.py` anywhere in the design doc.
