# Architecture review — B7: app-run/UI verification tier for the Builder

**Decision: Approved with conditions**

Sound in intent and scope-narrowing (opt-in, advisory, one stack first), but introduces two genuinely
new mechanism classes this skill-framework has never had — stateful process lifecycle management, and
binary (image) artifact handling — each with its own unmitigated risk today. Seven conditions need
closing before implementation.

## Architecture decision

An opt-in, per-repository, advisory-only capability letting the Builder start the target application,
run a bounded smoke test against it, and capture a screenshot, for exactly one supported web stack
first (general multi-stack support is explicitly out of scope, deferred to the dependent ticket D3).
Four coupled pieces: (1) a narrow policy-discovery surface declaring whether the capability is enabled
and, if so, the concrete start-command/readiness-check/port for the repo; (2) a bounded process-lifecycle
contract — start, poll a declared readiness signal up to a timeout, guarantee teardown on every exit
path; (3) a smoke-test action with a fixed, narrow definition (a declared readiness URL still returns
success after the Builder's change) rather than an open-ended interaction script; (4) a screenshot
capture stored as a referenced artifact, never embedded inline, with its result status mechanically
non-blocking — "results advisory, CI stays authoritative" must hold in code, not just in prose, matching
the existing `regression_gate` (gap-backlog B3) precedent.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| A screenshot is a lossy, uncurated pixel capture of whatever is on screen at capture time — unlike every existing artifact in this framework (text/JSON, cited by reference), it cannot be redacted after the fact the way `safe-output.md`'s Rule 5 redacts text. A UI showing a logged-in session, a seeded test credential, a URL bar with a token in the query string, or accidentally-real data (a misconfigured repo pointed at a non-local environment) would be captured verbatim and persisted as a durable artifact a human or Reviewer later opens | Security | Blocking | No existing mechanism in this skill-framework handles binary/image artifacts at all — this is the first one, and the ticket's own text gives no data-minimization answer for it |
| No process-lifecycle mechanism exists anywhere in this skill today, not even in `regression_gate` (gap-backlog B3), which is a single bounded command that runs to completion and exits. A long-running server process that the Builder starts and fails to stop is a wholly new operational hazard class — nothing in Circuit breakers or Failure modes anywhere in the existing skill names "a process I started is still running after the task ends" | Failure modes | Blocking | See Conditions §1 |
| "Opt-in per repo policy" has no stated mechanism for WHO can declare the start-command for a repo, and a start-command is, by definition, an arbitrary shell command the Builder will execute — this is a materially larger capability-grant shape than `regression_gate`'s own re-run-an-existing-test-command precedent, since it's inventing and running a *new* long-lived command, not re-running one already present and reviewed in the repo | Security | Blocking | See Conditions §3 |
| This skill is deliberately host-agnostic (`platform-adapters.md`); browser-automation/screenshot capability is not available on every host (a pure-CLI, sandboxed, no-GUI host cannot do this at all). The ticket text gives no per-host feasibility answer | Operability / Architecture decision | Conditional | See Conditions §5 |
| `software-builder` itself (this repo) is not a web app with a UI to screenshot — the "one web stack first" scoping decision has no concrete target repo named anywhere in the ticket or this session's own dogfood loop | Alternatives considered | Conditional | See Conditions §6 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Screenshot artifact storage growth per task/run | Unbounded if every Builder dispatch that opts in produces a persisted image with no stated retention/cleanup policy | No existing precedent — every other artifact this skill produces is small text, cited by reference, never a binary blob; `Unknown — no retention policy stated in proposal_text/design_description` |
| Process-start + readiness-poll wall-clock cost added to every opted-in Builder dispatch | Compounds against this skill's own existing response-wait-budget circuit breaker (`orchestrator.md` §3, already extended twice by gap-backlog B1 and B3) if the readiness timeout is not itself bounded and disclosed the same way B3's regression_gate cost was (~2x test-execution time, explicitly disclosed) | `Unknown — no readiness-timeout bound stated; must be designed, not left to system-design to discover unbounded` |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| The started process never becomes ready (crashes on boot, binds a different port, hangs) | Requires a declared, polled readiness signal with a bounded timeout — not an arbitrary sleep | Treat as an inconclusive/advisory result (mirroring B3's `NEEDS_EVIDENCE` convention), never block the Builder's task, always attempt teardown of whatever did start | Must be a concrete, checkable signal, not "wait and hope" (Conditions §1) |
| The Builder's dispatch ends (success, failure, crash, or circuit-breaker escalation) while the app process is still running | Requires an explicit, mandatory teardown step on every exit path of the dispatch, not just the happy path | An orphaned process on a shared or long-lived host is a real resource leak and a potential port-conflict hazard for the *next* dispatch | This is a genuinely new failure-mode class for this skill; must be named explicitly as a Circuit-breaker-adjacent concern, not left implicit (Conditions §1) |
| The declared port is already in use by an unrelated process | Requires a pre-start port-availability check | Must fail closed (never silently kill or hijack a port holder it doesn't own) — an aggressive "free the port" behavior would itself be a destructive action against unrelated process state | Must be stated explicitly, not assumed away (Conditions §1) |
| A screenshot is captured but shows an error page, a blank/loading state, or a visually broken UI | Detection is visual/subjective — no existing mechanism in this framework evaluates image *content* | The capability must never gate on screenshot content; it is evidence for a human to look at, nothing more — matches "results advisory, CI stays authoritative" | Must be mechanically enforced as non-blocking (same shape as B3's regression_gate never becoming a lifecycle gate), not merely described as advisory in prose (Conditions §2, §4) |
| The declared start-command itself is wrong, malicious, or scope-creeps beyond "start the app" (e.g. a command that also seeds/mutates a shared database) | No mechanism today distinguishes a safe local dev-server start from an arbitrary destructive command — the capability grant is "run this declared command," which is as broad as the command itself | Must be scoped to local, non-shared environments only (matching this session's own "Testing the user's own application" safety discipline — a local dev host only, never a shared/production target) and disclosed as a real, only-partially-closable residual, not claimed as fully solved | See Conditions §3 |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Screenshot artifact may contain session tokens, credentials, or real data visible on screen at capture time | Capture: whatever the Builder's locally-running app renders, no filtering. Storage: a new, durable artifact type this framework has never persisted before. Read: Reviewer/Orchestrator/human, by reference | A durable, potentially long-lived image artifact containing sensitive on-screen content, with no redaction mechanism available (image redaction is a fundamentally different, harder problem than this framework's existing text-redaction convention) | The ticket's single most important unresolved risk (Conditions §4) |
| The declared start-command is an arbitrary, repo-declared shell command the Builder executes with no narrower scoping than "whatever the repo policy says" | New: no prior capability in this skill runs a long-lived, repo-declared command — `regression_gate` (B3) only re-runs an *existing* test command already present and (implicitly) already reviewed as part of the repo's own test suite | A malicious or merely careless repo-policy declaration could start a process that does far more than "serve the app" (seed/mutate shared state, open a network listener beyond localhost, exfiltrate) | See Conditions §3 |
| Browser-automation/screenshot tooling itself is a new capability surface for this host-agnostic skill, with no entry yet in `reference/mcp-capabilities.md` | Optional capability, per-host — some hosts cannot grant it at all | Contained if correctly gated: an absent capability must skip and disclose, never fabricate a result (matching B4/B5's own fail-closed precedents) | See Conditions §5 |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Maintaining the "one web stack first" playbook (start-command conventions, readiness-probe convention, port/timeout defaults) | Repo owner (via this session's own doctrine chain) | Real, one-time build cost for the first stack; ongoing cost only if the stack's own tooling changes | `D3` (stack playbooks: frontend/mobile/data-ML) explicitly depends on B7 and is the generalization ticket — B7's own playbook-maintenance cost should stay scoped to exactly one stack, not expand silently |
| Validating this ticket against a real, opted-in repo | Repo owner | `software-builder` itself has no UI to screenshot — validation needs either a different target repo or an explicit scoping statement that this ticket ships infrastructure for *other* repos to opt into, never dogfooded here directly | See Conditions §6 |
| Screenshot artifact storage/retention over time | Repo owner | Not addressed by the ticket; should be named, not assumed free, especially since this is the first binary artifact this framework has ever produced | See Scale limits |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| No app-run/UI-verification tier at all (current state) | Rejected: literally the gap this ticket exists to close — Builder verification today is test/check execution only, with no way to visually confirm a UI-facing change actually works | Correctly motivates building something |
| Ship this as a standalone tool/script outside `loop-task-implementer`, invoked manually by a human, rather than a Builder-integrated capability | Rejected: the ticket's own framing ("the Builder's own verification tier") and its dependency structure (D3 depends on B7 specifically as a Builder capability, not a standalone tool) both point to in-skill integration | A real alternative, but contradicts the ticket's own stated shape |
| Build full general multi-stack support now, instead of "one web stack first" | Rejected outright: directly contradicts the ticket's own explicit scope-narrowing acceptance criterion, and duplicates work the dependent ticket D3 already owns | Not a real option, correctly excluded by the ticket's own text |
| Use this session's own harness-level capability (`Claude_Browser` preview/screenshot tooling) directly, without building a host-agnostic skill-level bridge | Rejected as the *sole* mechanism: this skill is deliberately host-agnostic (Cursor, Codex, Copilot, Kiro, Claude Code) and a harness-specific tool is not available on most of those hosts — but its existence is useful evidence that "start an app and screenshot it" is a solved UX pattern at the harness layer, worth citing as a feasibility precedent for the Claude-Code-specific adapter entry in `platform-adapters.md` | Partially reusable, not a full substitute — see Conditions §5 |
| Define "smoke test" as an open-ended scripted interaction (clicks, form fills, multi-page flows) rather than a single readiness-URL check | Rejected for this ticket's scope: the ticket's own acceptance criteria name "smoke test" without specifying interaction depth, and an open-ended interaction script is a materially larger, differently-shaped capability (closer to full E2E test authoring) than "confirm the app came up and responds" — left as a candidate for a future ticket, not this one | See Conditions §2 |

## Conditions

1. **Define a concrete, bounded process-lifecycle contract.** State the actual readiness-signal
   convention (a declared, polled check — never an arbitrary sleep), a bounded start/readiness timeout,
   and a MANDATORY teardown step covering every exit path of the Builder's dispatch (success, failure,
   crash, circuit-breaker escalation) — an orphaned process must never be an accepted outcome. State the
   pre-start port-availability check and its fail-closed behavior (never kill or hijack a port holder the
   capability doesn't own).
2. **Define "smoke test" narrowly and concretely**: a declared readiness/health-check URL returns a
   success status after the Builder's own change — not an open-ended interaction script. Any broader
   interaction-scripting capability is explicitly out of scope for this ticket.
3. **Scope the declared start-command to local, non-shared, non-production environments only**,
   matching this session's own established "testing the user's own application" safety discipline — a
   local dev-server start, never a shared or production target — and disclose explicitly that a
   carelessly- or maliciously-declared start-command remains a real, only-partially-closable residual
   risk (the capability narrows *where* the command can target, not *what* the command itself can do).
4. **State a mechanical, code-enforced, non-blocking status for every result this capability produces**
   (smoke-test outcome and screenshot alike) — "results advisory, CI stays authoritative" must never
   become a Blocking-standard condition or a lifecycle gate, matching `regression_gate`'s (gap-backlog
   B3) own precedent exactly, enforced in code, not merely stated as intent.
5. **State explicit per-host feasibility handling.** A host without browser-automation/screenshot
   capability must skip this tier entirely and disclose the gap — never fabricate a smoke-test result or
   a placeholder image. Name which host(s) can support this first (this session's own harness capability,
   `Claude_Browser` tooling, is cited evidence this is solvable for Claude Code at minimum; other hosts'
   feasibility is an open question for `system-design` to resolve, not silently assumed).
6. **Name a concrete validation target.** `software-builder` itself has no UI to screenshot — state
   explicitly whether this ticket is validated against a different, named repository, or is scoped as
   infrastructure this repo ships for other repos to opt into, with no in-repo dogfood validation
   possible for the screenshot path specifically.
7. **State a data-minimization/retention rule for the screenshot artifact itself**, consistent with this
   repo's existing `safe-output.md` discipline applied to a NEW artifact shape: since image content
   cannot be redacted the way text is, the design must state how exposure is bounded instead (e.g.
   captured only against local/non-production state per Condition 3, a named retention/cleanup policy, and
   an explicit warning in the capability's own documentation that screenshot content is not redacted and
   must never be pointed at an environment containing real secrets or data).

None of these seven block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
