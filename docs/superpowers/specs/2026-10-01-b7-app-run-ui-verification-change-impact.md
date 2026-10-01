# Change impact report — B7: app-run/UI verification tier for the Builder

**Coverage status: COMPLETE**

## Assessment target

Proposed state. Repo: `luckyrjain/software-builder`, main, head includes merged PR #317 (B6). Sources:
`docs/superpowers/specs/2026-10-01-b7-app-run-ui-verification-design.md` (revision 3, converged across
3 adversarial review rounds, 3 personas) and `docs/superpowers/specs/2026-10-01-b7-app-run-ui-verification-architecture-review.md`
(Approved with conditions, 7 conditions, all addressed in the converged design).

## Criticality: High

Not primarily code size — the largest ("L"-sized) ticket this session has handled, but most of its
weight is conceptual, not line count. Criticality is High for three independent reasons: (1) this is
the first ticket this session to touch `orchestrator.md` §1's policy-discovery step for anything beyond
its original two fields (`allowed_actions`, `autonomous_merge_authorized`) — a human reviewing the real
diff must independently confirm the new `app_run`-policy read genuinely reuses that step's existing,
hard-won external/caller-supplied sourcing rule rather than subtly widening it; (2) this is the first
ticket introducing stateful process-lifecycle management (start/poll/teardown) anywhere in this
skill-framework, with a mandatory-teardown contract whose correctness depends on concrete, security- and
reliability-sensitive code (host/userinfo URL validation, process-group signal handling) that didn't
exist before; (3) this is the first ticket introducing a binary (non-text) artifact type, with no
existing redaction mechanism available for it, relying entirely on a storage-location/git-exclusion
convention instead.

## Change classes

- `new-capability-declaration` (two new `mcp-capabilities.md` rows: process-lifecycle tier, screenshot
  tier — independently gated, the first capability declarations for execution/process-control rather
  than read access)
- `contract-change` (`implementation_task.app_run`, new nested optional field — external/exempt,
  mirrors `regression_gate`'s registration shape exactly)
- `workflow-policy-extension` (`orchestrator.md` §1's existing policy-discovery step gains one more
  externally-sourced value, reusing the identical trust rule already enforced for `allowed_actions`/
  `autonomous_merge_authorized` — not a new sourcing mechanism)
- `new-validation-logic` (the `readiness_url` host/userinfo parser; the process-group teardown
  mechanism's liveness recheck)
- `new-process-lifecycle-mechanism` (first of its kind in this skill-framework — start, readiness-poll,
  smoke-test, mandatory process-group teardown with a quantified SIGTERM/SIGKILL escalation)
- `new-artifact-type` (the screenshot — first binary artifact this framework has ever produced; no
  existing redaction mechanism applies to it, mitigated by storage-location exclusion instead)
- `documentation-only` (`platform-adapters.md`'s new Claude Code entry, `prompt-injection.md`'s new row)

## Impacted services / files

| Path | Nature of change | Risk |
|------|-------------------|------|
| **`skills/loop-task-implementer/workflow/orchestrator.md`** (§1 only) | Adds one more externally-sourced, caller-supplied value (`app_run` policy) to the existing policy-discovery step, validated with a fail-closed default on malformed/incomplete input, used to populate dispatched tasks' `implementation_task.app_run` field | **The single most important file in this change to review in isolation.** The design's own 3-round history is directly instructive here: round 2 proposed a repo-committed `.claude/app_run.policy.yaml` file, and two personas independently found this violated §1's own explicit rule — the design was corrected in round 3 to reuse the exact external/caller-supplied channel `allowed_actions`/`autonomous_merge_authorized` already use. A reviewer of the actual implementation diff must independently re-verify the shipped code enforces this (no file read from the repository under review ever sets `app_run`'s fields, under any code path), not merely trust that the design doc says so — this is exactly the kind of claim that can silently regress between design and implementation if the Builder takes a shortcut |
| **`skills/loop-task-implementer/workflow/builder.md`** (new subsection, nested after `regression_gate.command handling`) | New process-lifecycle procedure: numbered pre-checks (capability presence → host/userinfo validation → port check), process-group-scoped start, liveness-aware readiness poll, smoke test (same URL as readiness), optional screenshot (stored outside the git-tracked worktree tree), mandatory process-group teardown (SIGTERM → 5s grace → SIGKILL, post-kill liveness recheck) | High — this is where the bulk of the new, concrete, testable logic lives: the URL host/userinfo validator and the teardown mechanism are both security/reliability-sensitive code that didn't exist in this framework before this ticket |
| **`skills/loop-task-implementer/reference/mcp-capabilities.md`** | Two new rows: (a) process start + port/readiness probe + process-group teardown (one row, POSIX-only due to the teardown sub-mechanism — the design's own stated reasoning, confirmed in round 3, is that bundling is correct here since a "start without guaranteed teardown" is never an acceptable degraded mode, unlike this file's existing split rows for independently-meaningful SCM sub-capabilities); (b) screenshot capture, independently gated | Low — documentation, but must stay consistent with the actual gating logic implemented in `builder.md` |
| **`skills/loop-task-implementer/reference/platform-adapters.md`** | New Claude Code entry citing `Claude_Browser` `preview_start`/screenshot tooling concretely; other hosts get the existing "no equivalent today" phrasing already used for `gh run rerun --failed` | Low — documentation only, matches an established convention |
| **`docs/skill-framework/shared/prompt-injection.md`** | New row for `app_run.process.start_command`, distinguished from every other row as executed-not-merely-read content | Low — but worth a reviewer's attention that this row's own text should reflect the round-3 sourcing correction (caller-supplied, not repo-file) accurately, not the rejected round-2 framing |
| **`skills.yaml`** → regenerated **`scripts/registry/composition_contracts.yaml`** | `implementation_task.fields` gains `app_run` (external/exempt, no `payload_types` entry — mirrors `regression_gate`'s own confirmed registration shape at the real file's current lines ~103-119) | Low — mechanical, same pattern as B3, with the same "hand-edit `skills.yaml` only, regenerate the rest via `make generate`" discipline the design's own round-2→3 fix restates explicitly |
| **New test file(s) under `skills/loop-task-implementer/tests/`** (exact path not pinned by the design — likely a new `scripts/app_run.py`-style module plus its own `test_app_run.py`, following this session's own `convention_capture.py`/`test_convention_capture.py` precedent from B6) | Dedicated unit tests for the URL host/userinfo validator (the exact bypass shapes the design's own adversarial rounds found: `127.0.0.1.evil.com`, userinfo tricks, no-scheme/bare-IP inputs, `[::1]` vs `::1` normalization) and the process-group teardown mechanism (including the self-daemonizing-escape and POSIX-only-assumption cases, as negative/documented-limitation tests, not silently skipped) | High — these are the two pieces of genuinely new, security/reliability-sensitive logic; see Required tests below for the specific list |

**Confirmed untouched** (direct repository verification, not assumed): `scripts/validate_loop_lifecycle.py`
and `reference/state-schema.yaml` — grepped for `app_run`/`regression_gate`-shaped precedent in both;
neither file's gate logic needs any change for an advisory-only, non-blocking field, matching every
prior ticket's own discipline this session. **`workflow/reviewer.md` is untouched** — unlike B3
(regression-gate re-verification), B4 (comment-loop dispatch), and B6 (convention-capture fetch
exception), this design's entire mechanism is Builder-side and Orchestrator-policy-side only; the
Reviewer's own role, the Blocking standard's condition count, and the finding-output schema are all
unaffected. The design's own text never implies otherwise anywhere I found.

## Impacted contracts

- `implementation_task.app_run` — new, nested, optional field (`process: {...} | null`, `screenshot:
  bool`). External/exempt registration (fields-only, no `payload_types` entry), identical shape to
  `regression_gate`. No existing consumer of `implementation_task` needs to change — this is purely
  additive, null-by-default, fully backward compatible.
- No finding-output schema change, no Blocking-standard condition added (confirmed — this mirrors
  `regression_gate`'s own precedent of staying purely advisory).
- `orchestrator.md` §1's policy-discovery contract itself is extended (one more externally-sourced
  value), not restructured — the existing `allowed_actions`/`autonomous_merge_authorized` sourcing rule
  and its enforcement are unchanged; `app_run` is additive to the same rule, not a parallel or weaker
  path.

## Impacted data

None durable beyond the screenshot artifact itself (new data *type*, not a new persistent *store* —
it lives only in the task's own output/scratch directory for the duration of that task, explicitly
excluded from the git worktree's tracked tree, cleaned up with ordinary worktree teardown, never
committed unless a human explicitly attaches it afterward). No `plan_execution_state` field change, no
run-log event change (confirmed — `app_run` reports through the same `advisory_checks`/completion-notes
channel `regression_gate.command` already established, not a new `scripts/run_log.py` event).

## Impacted dependencies

New, previously-absent dependency classes for this skill: (1) a URL-parsing library capable of
authority/userinfo decomposition (standard-library-equivalent in most host languages, no new external
package expected); (2) POSIX process-group primitives (`os.setsid`/`start_new_session`, `os.killpg`) —
host-dependent, gated by the new capability row rather than assumed universally available; (3) whatever
the host's own browser-automation/screenshot tooling is for the screenshot sub-capability (for Claude
Code, the already-available `Claude_Browser` tooling cited in `platform-adapters.md` — no new dependency
installation needed for that one host).

## Impacted owners

Single owner (CODEOWNERS root wildcard). No CODEOWNERS change needed, matching every prior ticket this
session.

## Required tests

1. **`readiness_url` host/userinfo validator — unit tests covering every bypass shape the design's own
   3 rounds of adversarial review found**: `http://127.0.0.1.evil.com` (hostname-suffix trick, must
   reject), `http://evil.com@localhost/` (userinfo trick, must reject regardless of host match),
   `[::1]` vs `::1` (parser-normalized form must be what's compared, not the bracketed literal), a
   no-scheme bare input (`127.0.0.1:3000` typed without a scheme — must reject, not special-cased), an
   empty/unparseable hostname, plus positive cases (`http://localhost:3000/health`,
   `http://127.0.0.1:8080/`, `http://[::1]:3000/` parsing correctly to the accepted `::1` form). This is
   the direct regression test for a design-identified, previously-real SSRF-allowlist-bypass class —
   not optional coverage.
2. **Redirect-disabled behavior**: a readiness/smoke-test request that receives a 3xx must be treated as
   a non-2xx result and must never be followed, even to another local address — the design's closure of
   the SSRF-via-redirect finding needs its own direct test, not just code review.
3. **Process-group teardown — unit/integration tests**: (a) the common case (a direct child process is
   correctly killed via `killpg` on `SIGTERM`, escalating to `SIGKILL` after the 5-second grace period
   if still alive, confirmed via the post-kill liveness recheck); (b) teardown is idempotent (killing an
   already-stopped group is a no-op, never an error); (c) the two *documented, accepted-as-unclosed*
   residuals get their own explicit tests proving the design's own honesty about them, not silent gaps:
   a self-daemonizing/double-forking test fixture process should be shown to survive teardown (asserting
   the known limitation, so a future change that silently "fixes" this without updating the design's own
   disclosure is caught), and the whole mechanism's capability-row gating should be tested to confirm a
   simulated non-POSIX host correctly triggers the capability-absent `SKIPPED` path rather than crashing
   or silently proceeding.
4. **Process-liveness check in the readiness poll**: a test simulating a process that exits before
   becoming ready must produce the `EXITED_EARLY` outcome with the correct exit code, distinct from and
   faster than the full `TIMED_OUT` path (a process that stays alive but never responds).
5. **Malformed/incomplete policy fail-closed default**: a YAML-parse-failure case and a
   structurally-incomplete case (`port` declared with no `start_command`; `screenshot: true` with
   `process: null`) must both resolve to the same `SKIPPED` outcome as policy-absent — this closes a
   round-3 SRE finding that was previously left undefined.
6. **Screenshot git-exclusion — a real, executed test, not just documentation**: after a full `app_run`
   dispatch with `screenshot: true` completes, assert the screenshot file is NOT present in `git status`
   / `git ls-files` output for the task's worktree, and would not be swept in by a `git add -A` — this
   is the direct regression test for the round-1 finding that "never auto-committed" was previously only
   a prose promise with no mechanical backing.
7. **Orchestrator §1 sourcing-rule regression test (the most important single test in this change)**:
   a test asserting that a value for `app_run`'s fields present ONLY in repository content (e.g. a
   `CONTRIBUTING.md` or any in-repo file claiming to set `start_command`/`port`) is never picked up —
   only a value supplied through the same external/caller-supplied channel as `allowed_actions`/
   `autonomous_merge_authorized` populates `implementation_task.app_run`. This directly encodes the
   central finding from the design's own round-2→3 correction and should exist as a durable regression
   test, not just a one-time design-review confirmation.
8. **Synthetic end-to-end lifecycle test, recommended given OQ1's disclosed gap**: since no real web-UI
   repository exists in this session to validate against, a fixture-based end-to-end test (a trivial
   local HTTP server as the "app" under test, started via the real `app_run` procedure, polled for
   readiness, smoke-tested, torn down) would prove the full process-lifecycle/teardown contract works
   end-to-end, distinct from unit-testing the validator/teardown helpers in isolation. This does not
   close OQ1 (no screenshot-against-a-real-UI validation is possible this way, and the design's own
   honest framing of OQ1 should remain), but it meaningfully de-risks the one new mechanism class
   (process lifecycle) that doesn't depend on a real UI existing. Recommended as a required test, not
   merely a nice-to-have, given this ticket's High criticality and the size of its blast radius.

## Operational impacts

1. **First Reviewer-uninvolved, Builder-and-Orchestrator-only new capability this session has shipped**
   — every prior ticket touching a new capability class (B3's regression-gate, B4's comment-loop, B6's
   convention-capture) extended the Reviewer's own role; this one doesn't, which narrows its own blast
   radius in one direction (no Blocking-standard/finding-schema risk) but means its correctness rests
   entirely on the Builder's own self-discipline (the mandatory teardown contract) with no independent
   verification layer analogous to the Reviewer's dual-worktree regression-gate re-execution.
2. **Operational cost is real but small and already quantified** — the design's own worked arithmetic
   (≈2.4-2.6 minutes worst case, >11x margin against the existing 30-minute response-wait default)
   concludes no `orchestrator.md` §3 budget clause is needed, re-verified independently by SRE in round
   3 against the real §3 text. No further sizing needed here.
3. **This is genuinely new infrastructure with no real-world dry run possible in this repo** (OQ1) — the
   first few opted-in repos that actually use this tier should be treated as calibration, not a proven
   pipeline, mirroring this session's own established caution for B2's lightweight-path and B6's
   manual-intake path.
4. **Two residuals are disclosed, not closed, and will remain true in production**: a locally-scoped but
   still-destructive/exfiltrating `start_command`, and a self-daemonizing process surviving teardown.
   Neither is a defect in this design (both were explicitly assessed as not realistically closable at
   this ticket's scope) but both are real, standing operational facts an operator opting a repo into
   this tier should understand going in.

## Review triggers

**None required.** This design underwent 3 rounds of dedicated adversarial multi-persona review
(Security Architect, SRE, Software Architect), converging with the single most serious finding (the
repo-committed-policy-file trust-boundary violation) independently discovered by two personas from
different angles and verified closed, against the real current `orchestrator.md` text, by all three
personas in the final round. A standard `security-review` pass would not exceed the scrutiny this
process already applied to the one genuinely security-sensitive new surface (the policy-sourcing
channel and the URL-validation/process-execution boundary), which received dedicated attention across
all three rounds.

## Material unknowns

1. **No concrete validation target exists in this repo itself** (design's own Open Question 1) —
   `software-builder` has no UI to screenshot; this change ships the mechanism only. Recommended
   mitigation: the synthetic fixture-based end-to-end test (Required tests #8) de-risks the
   process-lifecycle half of this gap; the screenshot-against-a-real-UI half remains genuinely
   unvalidated until a real opted-in repo uses this tier.
2. **A `start_command` that daemonizes/double-forks and escapes the tracked process group is a named,
   disclosed, unclosed residual** (design's own Open Question 5) — no mechanism in this design detects
   or tears down such a process; this is a real, standing operational gap, not merely a theoretical one.
3. **`start_command`'s own behavior (local mutation, network exfiltration) remains an only-partially-
   closable residual** (design's own Open Question 3) — the local-host check bounds where the readiness
   probe points, not what the started process itself does once running.
4. **Port-allocation TOCTOU across concurrent peer Orchestrator dispatches against the same opted-in
   repo is a disclosed, accepted residual** (design's own Open Question 4) — a real race given this
   skill's own confirmed peer-concurrency model (`try_acquire`/lease mechanism), not foreclosed by the
   pre-start port-availability check.
5. **Per-host feasibility beyond Claude Code is unconfirmed** (design's own Open Question 2) —
   Cursor/Codex/Copilot/Kiro are left with the existing "no equivalent today" disclosure; whether any of
   them could support this tier at all is genuinely unknown.
6. **The external `app_run` policy's exact schema-validation implementation is deferred to
   implementation-planner sizing** (design's own Open Question 6) — the fail-closed *default* is
   design-level settled; the validator's own exhaustive rule set is not.

## Unknowns

None beyond the material unknowns above — repository read was available throughout, and all three
design documents (architecture review, design revision 3 with full revision history, and this report's
own direct verification of `orchestrator.md` §1's real current text) were read in full.

## Evidence refs

- `docs/superpowers/specs/2026-10-01-b7-app-run-ui-verification-architecture-review.md`
- `docs/superpowers/specs/2026-10-01-b7-app-run-ui-verification-design.md` (revision 3)
- Direct repository verification: `skills/loop-task-implementer/workflow/orchestrator.md` §1 (the real
  `allowed_actions`/`autonomous_merge_authorized` external/caller-supplied sourcing rule text this
  design's `app_run` policy must and does mirror); `skills/loop-task-implementer/workflow/builder.md`
  (the real `regression_gate.command handling` subsection and surrounding section ordering, confirming
  the design's claimed integration slot); `scripts/registry/composition_contracts.yaml` (the real
  `regression_gate` registration precedent, lines ~103-119); confirmed no `scripts/validate_loop_lifecycle.py`/
  `reference/state-schema.yaml`/`workflow/reviewer.md` changes anywhere in the converged design.
