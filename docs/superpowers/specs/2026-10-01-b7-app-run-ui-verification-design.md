# System Design Spec — B7: app-run/UI verification tier for the Builder

**Readiness: Ready with open questions**

## Revision history

**Revision 1** (initial): flat `implementation_task.app_run` object (5 fields), one capability row, a
Builder-only `finally`-equivalent teardown, no per-repo policy-discovery surface, "sequential
dispatches" framing for port allocation, no process-liveness check in the readiness poll, no explicit
host-validation algorithm, no tie-back to `orchestrator.md` §3's response-wait budget.

Round 1 adversarial review (Security Architect, SRE, Software Architect — all three, fresh, in parallel)
found real, code-grounded defects, converging on several of the same underlying gaps from different
angles (teardown/process-group handling flagged independently by both Security Architect and SRE; the
budget tie-back flagged independently by both SRE and Software Architect). Fixed in **revision 2** (this
revision):

- **Capability-row contradiction** (Software Architect): the design described two independently-gated
  behaviors (whole-tier skip vs. screenshot-only skip) while registering only one `mcp-capabilities.md`
  row — Failure strategy already promised a distinction Rollout Phase 2 didn't deliver. **Fixed**: two
  capability rows, and the data model now nests `screenshot` separately from the process-lifecycle
  fields it doesn't depend on, matching the capability split structurally.
- **Missing per-repo policy-discovery surface** (Software Architect): the architecture review's own
  Architecture-decision component (1) — "a narrow policy-discovery surface declaring whether the
  capability is enabled... for the repo" — was silently dropped; revision 1 only had a per-task field,
  re-authored on every single task with no single source of truth and no mechanism catching a
  typo'd mismatch across tasks for the same repo. **Fixed**: a new per-repo policy file
  (`.claude/app_run.policy.yaml` in the target repo), read once by the Orchestrator's existing §1
  policy-discovery step, which populates each dispatched task's `implementation_task.app_run` fields —
  closing both the missing-component gap and the authorship-burden gap (Software Architect's finding #5)
  in one mechanism.
- **State machine missing a 4th terminal state** (Software Architect): "capability absent → skip the
  tier" is semantically distinct from `REJECTED` (a validation failure) but had no state of its own.
  **Fixed**: added `NOT_STARTED -> SKIPPED`, and the check ordering is now one explicit numbered
  procedure instead of three scattered single-sentence claims across different tables.
- **Smoke test is near-tautological as scoped** (Software Architect): the smoke test and the readiness
  check share the same URL — revision 1 implied two independently meaningful verifications. **Fixed**:
  stated explicitly that this is an intentional, narrow re-confirmation after the Builder's own change
  lands, not a second distinct check, consistent with the architecture review's own rejection of a
  richer interaction script.
- **`readiness_url` host-check underspecified, redirect-following unaddressed** (Security Architect): a
  prose rule ("must resolve to exactly localhost/127.0.0.1/[::1]") with no parsing algorithm is a
  textbook SSRF-allowlist-bypass surface (`localhost.evil.com`, userinfo tricks, IPv4-in-IPv6), and
  nothing addressed the readiness/smoke-test HTTP client following a redirect to an arbitrary host.
  **Fixed**: exact algorithm specified (URL-parse, lowercase, exact hostname match, reject userinfo),
  redirect-following disabled entirely on this request.
- **`start_command` residual disclosure named local mutation but not exfiltration** (Security
  Architect): "local-only" bounds where the *readiness probe* points, not network egress from the
  *started process itself*. **Fixed**: exfiltration added explicitly alongside local-mutation as a named,
  unclosed residual.
- **Invocation mechanism unspecified** (Security Architect): whether `start_command` runs via argv or a
  shell string matters for injection risk if any other field is ever concatenated into the same
  invocation. **Fixed**: argv-first via `shlex.split`, with an explicit rule that if shell features are
  unavoidable for a given stack, no other task-derived field is ever concatenated into that same shell
  string.
- **Screenshot retention had no mechanical backing** (Security Architect): "never auto-committed / never
  auto-attached" were prose promises with nothing stopping a `git add -A` sweep or a downstream
  completion-notes consumer from auto-rendering the path. **Fixed**: the scratch directory is explicitly
  excluded from the git worktree's tracked tree, and the completion-notes field carrying the path is
  flagged the same way other render-targets are flagged in `prompt-injection.md`'s per-skill table.
- **`app_run.start_command` absent from `prompt-injection.md`'s per-skill table** (Security Architect):
  unlike every other field that table lists (read as data), this one is *executed*. **Fixed**: added as
  a new row, explicitly distinguished from the read-as-data rows.
- **No process-liveness check in the readiness poll** (SRE): a process that crashes on boot polls a dead
  URL for the full timeout, indistinguishable from a slow-but-healthy boot. **Fixed**: each poll tick now
  also checks process liveness; an exited process fails fast with its exit code rather than waiting out
  the timeout.
- **"Sequential dispatches" framing was factually wrong** (SRE): `orchestrator.md`'s own lease
  mechanism (`try_acquire`, "a peer is already working this task on this machine") proves multiple
  Orchestrator processes can run concurrently on the same host — making the port pre-check a real TOCTOU
  race, not a non-issue. **Fixed**: Consistency section corrected; the race is disclosed as an accepted
  residual (Open Questions), not claimed foreclosed.
- **Teardown was single-PID, single-layer, with no orphan-detection** (Security Architect + SRE,
  independently): a `finally`-equivalent inside the Builder's own turn is not a guarantee given this
  skill's own real TOKEN_BUDGET/TIME_BUDGET circuit breaker that can stop a dispatch before its own next
  instruction runs; and even when teardown does run, killing only the tracked PID commonly leaves a
  forked child (the actual server) alive and holding the port. **Fixed**: process-group-scoped start
  (new session/process group), PGID-tracked SIGTERM→wait→SIGKILL teardown, a stated second layer tying
  cleanup to the task's own worktree teardown (a host-level guarantee independent of the Builder's own
  continued execution), and "teardown reported success but an orphan survives" named as its own explicit
  failure mode with a post-kill liveness recheck as its detection step.
- **No tie-back to `orchestrator.md` §3's response-wait budget** (SRE + Software Architect,
  independently): B1 and B3 both earned an explicit numbered clause on §3's budget sentence because
  their added cost threatened the 30-minute default; revision 1 cited that precedent without doing the
  same arithmetic. **Fixed**: worked arithmetic added (worst case ~3 minutes: up to 120s readiness
  timeout + smoke-test GET + screenshot round-trip), concluding the existing 30-minute default has
  sufficient headroom and needs no new clause — stated as a reasoned conclusion, not left implicit.
- **`composition_contracts.yaml`/`skills.yaml` edit-target ambiguity** (Software Architect): revision 1's
  Rollout Phase 1 described both files as edit targets, repeating a mistake B3 needed a full review round
  to correct. **Fixed**: only `skills.yaml` is hand-edited; `composition_contracts.yaml` is regenerated
  via `make generate`, stated explicitly.
- **`builder.md` integration point was vague** (Software Architect): "a new subsection" with no stated
  slot or ordering, unlike B3's own numbered-procedure precedent. **Fixed**: named concretely — nested
  immediately after the existing `regression_gate.command handling` subsection, same parent section,
  explicit ordering relative to the Builder's own existing steps (after local tests/regression_gate,
  before Inspect-final-diff/Commit-and-publish), with an explicit note that the screenshot path must be
  excluded from whatever the Commit-and-publish step stages.

Round 1 personas converged on no other disagreements; two items (process-liveness, no-new-run-log-event
claim) were independently confirmed sound/accurate as originally designed and are unchanged.

**Round 2** adversarial review (same three personas, fresh, re-reviewing revision 2 against the real
current files) found 6 of 8 round-1 fixes genuinely closed, and converged — independently, from two
different angles (Software Architect and Security Architect both found this without seeing each other's
work) — on one serious new problem that revision 2's own fix introduced, plus several smaller
overclaims/gaps. Fixed in **revision 3** (this revision):

- **`.claude/app_run.policy.yaml` violated this same codebase's own established untrusted-repo-content
  rule** (Software Architect AND Security Architect, independently convergent — the single most
  important round-2 finding): `orchestrator.md` §1 has an explicit, hard rule that `allowed_actions` and
  `autonomous_merge_authorized` must come from "a workflow configuration that is both external to the
  repository under review (not a file the Builder could have created or edited) and supplied by the
  caller invoking this skill — never from prose inside any file read from the repository, committed or
  not." Revision 2's repo-committed policy file violated this exact rule for a field that is strictly
  more dangerous than either of those two (an executed shell command, not a boolean flag) — a Builder on
  one task could edit the file and have a later task's Orchestrator blindly execute the new value.
  Security Architect additionally found that revision 2's own cited precedent (`.claude/settings.json`)
  actually argues the opposite of what it was cited for: that file's real history is two adversarial
  review rounds that found and closed "a real secret-exfiltration chain in the original allow-list,"
  specifically because a repo-influenced execution surface needs exactly this scrutiny. **Fixed**: the
  per-repo `app_run` policy is now sourced the same way `allowed_actions`/`autonomous_merge_authorized`
  already are — external to the repository under review, supplied by the caller invoking this skill —
  never a repo-committed file. This resolves the architectural inconsistency by construction, reusing an
  existing, already-trusted sourcing channel rather than inventing new sign-off/hash-pinning machinery.
- **Teardown's self-daemonizing-escape case was overclaimed as closed** (Security Architect): the
  process-group kill correctly closes the common case (a direct child process), but a `start_command`
  that itself double-forks/daemonizes (common for some dev-server wrappers) escapes the tracked process
  group entirely, and the stated "worktree teardown" backstop does not actually kill any process — it
  only discards a directory. **Fixed**: named explicitly as an unclosed residual, alongside the existing
  `start_command` local-mutation/exfiltration residual, rather than implied as covered.
- **Process-group teardown mechanism had two implementability gaps** (Security Architect + SRE,
  independently): "waits briefly" between SIGTERM and SIGKILL was never quantified, and the mechanism
  (`setsid`/`killpg`/negative-PID signaling) is POSIX-only with no stated fallback for a non-POSIX host,
  inconsistent with how the design already gives the screenshot capability a per-host degraded path.
  **Fixed**: grace period set to a concrete 5 seconds; the whole process-start/teardown capability (not
  just screenshot) is now explicitly named as part of the same per-host-gated capability row, with
  non-POSIX hosts getting the same "no equivalent today" disclosure.
- **Host-check wording had two implementability nits** (Security Architect): the spec listed the
  bracketed literal `[::1]` rather than a real URL parser's normalized `.hostname` output (`::1` without
  brackets), and never stated what happens to a no-scheme/bare-IP input. **Fixed**: corrected to `::1`
  (parser-normalized form), and an explicit sentence added that a URL with no scheme or an empty parsed
  hostname is rejected, not specially handled — closing off a path where an implementer might "fix" a
  confusing rejection by reintroducing substring logic.
- **Malformed/incomplete policy input had no stated default** (SRE): every other edge case in this design
  has a fail-closed default; a malformed or incomplete policy (e.g. `port` declared with no
  `start_command`) didn't. **Fixed**: stated explicitly now — treated identically to absent, i.e.
  `SKIPPED`, logged — rather than deferred entirely to implementation-planner sizing.
- **Budget arithmetic omitted the teardown wait itself** (SRE): the worked ~3-minute estimate didn't
  include the new 5-second SIGTERM grace period (now quantified) or ground the screenshot round-trip
  estimate. **Fixed**: both folded into the arithmetic; conclusion (no new §3 clause needed) is unchanged
  — the margin remains large (still comfortably under 30 minutes) even with the fuller accounting.

Two round-2 findings were confirmed sound as designed and needed no change: the two-capability-row split
(verified against `mcp-capabilities.md`'s own existing multi-row-per-concern convention) and the
`builder.md` integration slot (verified against the real file's section ordering) — Software Architect
flagged the latter's "Test" parent section as a soft taxonomy quibble, not a functional defect, so it is
unchanged.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| External `app_run` policy (new, per-repo, **caller-supplied — never a file read from the repository under review**, revised in round 3) | The single source of truth for whether this tier is enabled for a repo, and its concrete `start_command`/`readiness_url`/`readiness_timeout_seconds`/`port`/`screenshot` values | Supplied by the caller invoking this skill (e.g. a session-level workflow configuration the human provides), the identical sourcing rule `orchestrator.md` §1 already requires for `allowed_actions`/`autonomous_merge_authorized` | Closes the dropped architecture-decision component (1) and the authorship-burden gap, **without** reopening the untrusted-repo-content violation round 2 found in the original `.claude/app_run.policy.yaml` design — a human supplies this once per repo via the caller channel, not once per task, and never via a file the Builder could edit |
| Orchestrator's existing §1 policy-discovery step (`workflow/orchestrator.md`) | Reads the externally-supplied `app_run` policy if present, alongside its existing `allowed_actions`/`autonomous_merge_authorized` reads — same channel, same trust rule, same step | Orchestrator only | Minimal addition: one more value read via an already-existing, already-trusted channel — not a new file format, not a new trust boundary |
| `implementation_task.app_run` (per-task field, now nested) | Carries the resolved policy values for ONE dispatched task, populated by the Orchestrator from the externally-supplied, caller-provided `app_run` policy (never hand-retyped per task, never sourced from repository content — round 3 correction) | `implementation_task`'s own envelope — external/exempt field, same registration shape as `regression_gate` | `{process: {start_command, readiness_url, readiness_timeout_seconds, port} | null, screenshot: bool}` — see Data model |
| Builder's `app_run` procedure (new `workflow/builder.md` subsection, nested immediately after `regression_gate.command handling`) | Runs the process-lifecycle contract: ordered pre-checks, process-group-scoped start, liveness-aware readiness poll, smoke test, optional screenshot, mandatory process-group teardown | Builder role only — never the Reviewer, never the Orchestrator | Mirrors `regression_gate.command` handling's structure; explicit ordering relative to existing builder.md steps (see Rollout) |
| Local-host + redirect enforcement (part of the same Builder procedure) | Rejects any `readiness_url` whose parsed hostname isn't exactly `localhost`/`127.0.0.1`/`[::1]`; disables redirect-following on the readiness/smoke-test request | Builder-side input validation, no new capability needed | Closes architecture review Condition 3 to the extent a host check and redirect policy can — does not validate `start_command`'s own behavior (disclosed residual, now including exfiltration) |
| Screenshot capture (optional, independently capability-gated) | Captures one image of the running app after readiness, saves OUTSIDE the git worktree's tracked tree | Builder, gated on its own `mcp-capabilities.md` row | Never embedded in any text artifact; cited by path only, with that completion-notes field flagged per `prompt-injection.md` |
| `reference/mcp-capabilities.md` — **two** new rows | (a) process start + port/readiness probe + process-group teardown, gated as one row because the *teardown* sub-mechanism is POSIX-only (`setsid`/`killpg`) and the state machine's own invariant requires every started process to reach a guaranteed teardown — so the whole tier is gated on its weakest link rather than split further (round-3 SRE: confirmed consistent with `mcp-capabilities.md`'s own convention of splitting only when sub-capabilities have independently meaningful degraded paths, which teardown-less process-start does not have here); a host without POSIX process-group semantics gets the same degraded path as any other absent capability, (b) screenshot capture — independently gated | Documentation only | Absent (a) → skip the entire tier; absent (b) → skip just the screenshot sub-step, everything else runs — now consistent across Components/APIs/Failure-strategy |
| `reference/platform-adapters.md` Claude Code entry | Names the concrete, already-available bridge (`Claude_Browser` `preview_start`/screenshot tooling) for this one host | Documentation only | Other hosts get the existing "no equivalent today" phrasing already used for `gh run rerun --failed` |

**Confirmed untouched** (re-verified in round 1, independently, by both SRE and the design's own
authoring pass): `workflow/lifecycle-gate.md`, `scripts/validate_loop_lifecycle.py` — zero hits for
`regression_gate` in either file, and nothing in this design's gate logic needs either file to change;
`app_run` follows the identical external/exempt registration shape. **`workflow/orchestrator.md` DOES
need a small, scoped change** (reversing revision 1's "confirmed untouched" claim, per Software
Architect's finding) — the new per-repo policy-file read inside the Orchestrator's existing §1 step. No
other orchestrator.md section changes; no Blocking-standard condition is added; no finding-output schema
field changes.

## APIs

Not a network-facing feature — "API surface" here is the (now nested) `implementation_task.app_run`
field's own shape, consumed by the Builder only:

| Field (method-equivalent) | Contract | Consumer(s) | Notes |
|--------------------------|----------|-------------|-------|
| `app_run.process.start_command` | A shell command the Builder runs to start the app (string, required if `app_run.process` is non-null). Invoked via `shlex.split` + argv where possible; if a stack genuinely needs shell features (env-var prefixing, pipes), `shell=True` is permitted for this ONE field only, with an explicit rule that no other task-derived field is ever concatenated into that same shell string | Builder | Resolved once per repo via the external, caller-supplied `app_run` policy (round 3 — never a repo-committed file), never hand-retyped per task |
| `app_run.process.readiness_url` | Must parse (via a real URL-parsing library, not substring/prefix matching) to a lowercased hostname exactly equal to `localhost`, `127.0.0.1`, or `::1` — the parser's own normalized, unbracketed form, not the literal string `[::1]` (round 3 wording fix) — with an optional `:port`/path, and no userinfo in the authority component. A URL with no scheme, or one whose parsed hostname is empty (e.g. a bare `127.0.0.1:3000` typed without a scheme), is rejected outright, not specially handled (round 3 addition, closing an implementer foot-gun) | Builder | Any other host, userinfo-bearing URL, or unparseable/schemeless input → treat exactly like `app_run` absent for this task: skip, record `app_run: rejected — readiness_url is not local` |
| `app_run.process.readiness_timeout_seconds` | Bounded poll window (default `30`, hard cap `120`) | Builder | See Capacity for the worked §3-budget arithmetic |
| `app_run.process.port` | The port the started process is expected to bind | Builder | Pre-start availability check; occupied by an unrelated process → fail closed, record `app_run: port N already in use, skipped`. TOCTOU race against a concurrent peer dispatch is a disclosed, accepted residual (Open Questions) given this skill's own real peer-concurrency model |
| `app_run.screenshot` | Boolean, whether to attempt a screenshot once ready — **independently gated**, sibling to `process`, not nested inside it | Builder | Absent screenshot capability skips only this field's effect; everything in `app_run.process` still runs regardless |

**Redirect policy**: the readiness-poll and smoke-test HTTP requests are made with redirect-following
disabled entirely. A local dev server returning a 3xx from its own readiness endpoint is not a supported
case — this closes the SSRF-via-redirect gap identified in round 1 without adding a second host-check
layer for the `Location` header.

## Events

None — unchanged from revision 1, confirmed accurate in round 1 (SRE verified `regression_gate.command`
itself reports through `advisory_checks`/completion notes, not a `run_log.py` event — this design's
"same reporting channel" claim was correct, not misremembered).

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| External `app_run` policy (new, per-repo — **caller-supplied, round 3 correction**) | `enabled` (bool), `process: {start_command, readiness_url, readiness_timeout_seconds, port}` or `null`, `screenshot` (bool) | Supplied by the caller invoking this skill, read once per dispatch by the Orchestrator's §1 step via the same channel as `allowed_actions`/`autonomous_merge_authorized` — never a file read from the target repository | Repo owner, via the caller channel (e.g. a session-level workflow configuration), not a committed dotfile |
| `implementation_task.app_run` (new, optional, nested — structurally mirrors the two-capability split) | `process: {start_command, readiness_url, readiness_timeout_seconds, port} \| null`, `screenshot: bool` | Lives inside the existing `implementation_task` envelope, registered in `skills.yaml` (hand-edited) then regenerated into `composition_contracts.yaml`'s `implementation_task.fields` list via `make generate` — never hand-edited there directly (external/exempt, same as `regression_gate`) | Orchestrator, populated from the external policy — never hand-authored per task, never sourced from repository content |
| Screenshot artifact (binary — this framework's first) | One PNG file, path `<task_output_dir>/app_run_screenshot.png`, **stored outside the git worktree's tracked tree** (a sibling scratch directory, or explicitly `.gitignore`'d if it must live inside the worktree for tooling reasons) | Referenced by path only from the Builder's completion notes; that completion-notes field is flagged per `prompt-injection.md`'s per-skill table so a downstream consumer (a notification skill, a tracker sync) never auto-renders/auto-attaches it without a human step in between | Builder, for the task's own output-directory lifetime only |

**Screenshot retention rule** (closes architecture review Condition 7, now with mechanical backing
closing round 1's finding): the file is excluded from the git worktree's own tracked tree by
construction (location choice, or `.gitignore` entry), so an operator-error `git add -A` in the
Commit-and-publish step cannot sweep it in; it is cleaned up whenever the task's own output/scratch
directory's normal teardown happens; it is never attached to the PR unless a human explicitly does so
afterward. The capability's own documentation carries this literal warning, unchanged from revision 1:

> **Screenshot content is not redacted.** Unlike every other artifact this framework produces, an image
> cannot be scanned or redacted for secrets/PII the way text is. Never point `app_run.process.readiness_url`
> at anything other than a local, disposable instance of the app under test — never a shared or
> production environment, and never one seeded with real user data or live credentials.

**`prompt-injection.md` addition** (new, closes a round-1 finding, reasoning corrected in round 3):
`app_run.process.start_command` is added as a new row in that file's per-skill untrusted-content table,
explicitly distinguished from every other row: those are untrusted content *read as data*; this one is
executed. With round 3's sourcing fix, this field's provenance now matches `allowed_actions`' own
(caller-supplied, external to the repo) rather than the round-2 repo-file design Security Architect
correctly rejected — but the row is kept regardless, since the table's job is to flag the risk *class*
(an executed field, not merely a read one) independent of how well-sourced the common case is.

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| `app_run` process lifecycle (per Builder dispatch) | `NOT_STARTED -> SKIPPED` (capability absent — the whole tier, per the new dedicated mcp-capabilities.md row); `NOT_STARTED -> REJECTED` (non-local `readiness_url`, userinfo present, or port pre-check fails); `NOT_STARTED -> STARTING -> READY -> SMOKE_TESTED -> TORN_DOWN` (happy path); `NOT_STARTED -> STARTING -> EXITED_EARLY -> TORN_DOWN` (process liveness check detects exit before readiness — new path, closes round-1 SRE finding); `NOT_STARTED -> STARTING -> TIMED_OUT -> TORN_DOWN` (readiness never reached, process still alive) | **Explicit numbered check order** (closes round-1 Software Architect finding that this was scattered across tables): (1) capability-presence check → `SKIPPED` if absent; (2) `readiness_url` host/userinfo validation → `REJECTED` if it fails; (3) port pre-start availability check → `REJECTED` if occupied; (4) only then, process start. No process is ever started before steps 1-3 all pass, so `SKIPPED` and `REJECTED` are confirmed to never require teardown | **Every state except `SKIPPED` and `REJECTED` (which never start a process) MUST reach `TORN_DOWN`** via the process-group-scoped teardown below |
| Teardown mechanism (closes round-1 Security Architect + SRE findings; precision-corrected in round 3) | Process started via `Popen(..., start_new_session=True)` (POSIX `setsid` equivalent — the child's PGID equals its own PID, set synchronously before `Popen()` returns to the parent, so tracking `proc.pid` as the PGID is not racy) → teardown sends `SIGTERM` to the negative PGID (`os.killpg(pid, SIGTERM)`), waits a concrete **5 seconds** (round 3: quantified, was "briefly"), escalates to `SIGKILL` to the negative PGID if still alive → post-kill liveness recheck (e.g. `os.killpg(pid, 0)` raising `ProcessLookupError`, round 3: mechanism now named explicitly) confirms no process remains in that group | Runs regardless of which of the above states preceded it, including an unhandled exception during the smoke test or screenshot sub-step. **Second layer**: the task's own worktree/output-directory teardown (a host-level guarantee independent of the Builder's own continued execution) is a backstop ONLY for the case where the Builder's own dispatch is stopped externally (the real `TOKEN_BUDGET`/`TIME_BUDGET` circuit breaker in `orchestrator.md` §3) before its own in-band teardown instruction runs — round 3 correction (Security Architect): this backstop does **not** cover a `start_command` that itself daemonizes/double-forks and escapes the tracked process group, since discarding a worktree directory does not kill a process that has already re-parented elsewhere; this is now named as its own disclosed, unclosed residual (see Failure strategy), not implied as covered. This whole mechanism (`setsid`/`killpg`/negative-PID signaling) is POSIX-only — a host without POSIX process-group semantics gets the capability-absent degraded path (round 3 addition, Components table) | "Teardown reported success but an orphan survives" (the common, in-group case) is named as its own explicit failure mode with the post-kill liveness recheck as its detection step; "a self-daemonized process escapes the group entirely" is a separate, distinct, and NOT detected failure mode (see Failure strategy) |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| Process lifecycle within one Builder dispatch | Strong, single-actor | Only the Builder ever starts or tears down this process; no concurrent writer, no shared state with the Reviewer or Orchestrator |
| Port allocation across **concurrent** dispatches on the same host (corrected from revision 1) | **Best-effort, not strong** — a real TOCTOU race exists | `orchestrator.md`'s own lease mechanism (`try_acquire`, "a peer is already working this task on this machine") confirms multiple Orchestrator processes can run concurrently on the same host, each potentially working a different task against the same opted-in repo and declaring the same repo-level port. The pre-start availability check narrows the window but cannot close it. Disclosed as an accepted residual (see Open Questions), not claimed foreclosed |
| Per-repo policy consistency across tasks | Strong, by construction | Since the Orchestrator now reads the external, caller-supplied `app_run` policy once (round 3 sourcing correction) and populates every dispatched task's `app_run` field from it, there is no longer a per-task retyping step that could drift — this closes the "no mechanism catching a typo'd mismatch" gap round 1 identified, without the round-2 trust-boundary regression |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| Readiness poll (`GET`/`HEAD` against `readiness_url`, redirects disabled) | Yes — a pure read, safe to repeat | Fixed-interval poll (every 1s) up to `readiness_timeout_seconds`; confirmed sound as designed in round 1 (SRE: no backoff needed for a local, low-latency check) — **now also checks process liveness each tick** (closes round-1 SRE finding), failing fast with `app_run: process exited with code <N> before becoming ready` rather than waiting out the full timeout on a crashed process |
| Process start (`start_command`) | Not idempotent in general — re-running it while the prior instance is still up is exactly the port-conflict case this design fails closed on | Never auto-retried; a failed start is a terminal `REJECTED`/`EXITED_EARLY`/`TIMED_OUT` outcome for that dispatch, reported advisory-only |
| Teardown (process-group kill) | Idempotent — killing an already-stopped process group is a no-op, never an error that blocks completion | Always attempted once per dispatch (SIGTERM→5s wait→SIGKILL escalation); a post-kill liveness recheck confirms success; failure to fully clear the group (or a self-daemonized escapee outside the group) is logged in completion notes, never silently swallowed, never escalated into a Blocking finding |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Screenshot file size | A few hundred KB to a few MB per capture | No durable accumulation — stored outside the tracked worktree tree, cleaned up with output-directory teardown, never committed |
| Added wall-clock cost per opted-in dispatch, tied explicitly to `orchestrator.md` §3's response-wait budget (closes round-1 SRE + Software Architect finding; arithmetic completed in round 3 per SRE's finding that it previously omitted the teardown wait) | Worst case ≈ 120s (readiness timeout cap) + 5s (SIGTERM grace period, round 3: now quantified and included) + a few seconds (post-kill liveness recheck) + a few seconds (smoke-test GET) + ~10-20s (screenshot capture round-trip via host tooling — launch/navigate/render/capture, a more conservative estimate than revision 2's ungrounded "a few seconds," per round-2 SRE finding) ≈ **under 3 minutes even with the fuller accounting**, against §3's existing 30-minute default response-wait budget. **Conclusion unchanged: sufficient headroom exists (>7x margin even with padded estimates); no new numbered clause on §3's budget sentence is needed** — unlike B1's clarify step or B3's regression_gate (each ~60 minutes, a 2x-or-more multiplier that genuinely threatened the 30-minute default), this tier's worst case remains roughly 1/10th of the existing budget even stacked on top of ordinary implementation work | Worked arithmetic, now complete per round-2's own finding that the round-1 fix undercounted it |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| Process-start capability absent on the current host | `SKIPPED` before any check runs; record `app_run: skipped — capability not available on this host`; never fabricate a result |
| `readiness_url` host isn't local, or carries userinfo | `REJECTED` before any process starts; record `app_run: rejected — readiness_url is not local` |
| Declared port already bound by an unrelated process | `REJECTED` before starting; never kill/hijack; record `app_run: port <N> already in use, skipped`. A concurrent-peer-dispatch TOCTOU race past this check is a disclosed residual, not claimed closed |
| Process exits before becoming ready (liveness check fires) | `EXITED_EARLY`; teardown still runs (idempotent no-op if already dead); record `app_run: process exited with code <N> before becoming ready` — distinct, faster signal than a full timeout |
| Process never reaches the readiness probe within `readiness_timeout_seconds`, but remains alive | `TIMED_OUT`; teardown runs; record `app_run: NEEDS_EVIDENCE — process never became ready within <N>s` |
| Smoke-test GET returns a non-2xx/3xx status | Advisory failure only; record `app_run: smoke test failed (status <N>)`; never blocks task completion or becomes a Reviewer-side Blocking finding. (Smoke test reuses the same `readiness_url` as the readiness check itself — a re-confirmation after the Builder's own change, not an independently meaningful second check; stated explicitly per round-1 Software Architect finding, not implied) |
| Readiness/smoke-test request receives a redirect | Redirect-following is disabled entirely; a 3xx is treated as a non-2xx smoke-test result, never followed | Closes the round-1 SSRF-via-redirect finding |
| Screenshot capability absent | Skip just the screenshot sub-step; the rest of the tier still runs; record `app_run: screenshot skipped — capability not available on this host` |
| Teardown reported success but an orphaned child (within the tracked process group) survives | Detected by the post-kill liveness recheck against the tracked PGID; if a process remains, logged explicitly (`app_run: teardown incomplete — process group <PGID> still has a live member`) |
| `start_command` daemonizes/double-forks and escapes the tracked process group entirely (new, round 3 — Security Architect, previously overclaimed as covered) | **Explicitly disclosed, NOT closed by this design**: a self-daemonizing process (common in some dev-server wrappers, e.g. ones that internally call `setsid` again or detach) is not killed by the process-group teardown, and the worktree/output-directory teardown backstop only discards a directory — it does not kill any process. Such a process would survive both layers, left running and holding the port indefinitely. No mechanism in this design closes this; a future revision could pursue a container/cgroup boundary or a host-level "find and kill anything with cwd under this worktree path" sweep, neither attempted here |
| Policy input is malformed or incomplete (e.g. YAML parse failure, or `port` declared with no `start_command`) (new, round 3 — SRE, previously deferred entirely) | Treated identically to policy absent: `SKIPPED`, logged (`app_run: skipped — policy malformed or incomplete`) — a stated fail-closed default, not deferred to implementation-planner sizing as revision 2 left it |
| Malformed policy declares `screenshot: true` with `process: null` (schema-invariant gap, round 3 — Security Architect) | Treated as a malformed-input case per the row above — `screenshot` has no effect without a running `process`, so this configuration is rejected/flagged by the same validator rather than silently accepted |
| `start_command` is locally scoped but still destructive or exfiltrates data (expanded per round-1 Security Architect finding — now names BOTH residuals explicitly) | Explicitly disclosed, NOT closed by this design: the local-host check only bounds where the *readiness probe* points, not what the started process itself does once running — it could mutate local state (e.g. a database file) or open an outbound connection to exfiltrate repo contents/secrets, independent of `readiness_url` being correctly local. This is the honest residual the architecture review's Condition 3 asked to be named rather than hidden |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `app_run: <outcome>` line in Builder completion notes | One of: skipped, rejected, ready + smoke-test pass/fail, exited-early (with exit code), timed out (NEEDS_EVIDENCE), teardown-incomplete, screenshot path (flagged per `prompt-injection.md`) or screenshot-skipped reason |
| Screenshot file path (when captured) | Cited by path only, outside the tracked worktree tree — never embedded inline |

No new run-log event (confirmed accurate in round 1) — reuses the exact `advisory_checks` + completion
notes surface `regression_gate.command` already established.

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 1 | `implementation_task.app_run` (nested shape) registered by hand-editing **`skills.yaml` only** (`implementation_task.fields`); `composition_contracts.yaml` is regenerated via `make generate`, never hand-edited (corrected per round-1 Software Architect finding, matching B3's own established, corrected convention) | No flag — null/absent is the default, fully backward compatible |
| 2 | **Two** new `mcp-capabilities.md` rows: process-start/readiness/port tier, and screenshot capture, independently gated (corrected per round-1 Software Architect finding) | Documentation only |
| 3 | A minimal addition to `workflow/orchestrator.md` §1's existing policy-discovery step: read the external, caller-supplied `app_run` policy (same channel/trust rule as `allowed_actions`/`autonomous_merge_authorized` — round 3 correction, never a repo-committed file), validate it (malformed/incomplete → treated as absent, per Failure strategy), and populate dispatched tasks' `app_run` field | Scoped, small addition to an existing step and an existing trust channel — not a new workflow phase, not a new trust boundary |
| 4 | New `workflow/builder.md` subsection, nested immediately after the existing `regression_gate.command handling` subsection (same parent section), with explicit ordering: runs after local tests/regression_gate, before Inspect-final-diff/Commit-and-publish; explicit note that the screenshot path must be excluded from whatever the Commit-and-publish step stages | Gated entirely by `app_run` being non-null on a given task — zero behavior change for any task that doesn't opt in |
| 5 | New `prompt-injection.md` row for `app_run.process.start_command` | Documentation only |
| 6 | New `reference/platform-adapters.md` Claude Code entry citing `Claude_Browser` `preview_start`/screenshot tooling concretely; other hosts get the existing "no equivalent today" phrasing | Documentation only |
| 7 | First real, end-to-end manual dry-run | **Open question** — see below; no committed validation target exists today |

## Open questions

1. **No concrete validation target exists.** `software-builder` itself (this repo) has no UI to
   screenshot — this design ships the *mechanism* only. A real end-to-end dry-run (closing
   architecture-review Condition 6) needs either a different, named repository with an actual web UI,
   or an explicit decision to treat this as unexercised infrastructure shipped for other repos to opt
   into, disclosed honestly rather than assumed proven — unchanged from revision 1.
2. **Per-host feasibility beyond Claude Code is unconfirmed.** Unchanged from revision 1 — Cursor/Codex/
   Copilot/Kiro are left with the existing "no equivalent today" disclosure.
3. **`start_command`'s own behavior remains an only-partially-closable residual.** The local-host check
   bounds where the readiness probe points and now explicitly names both local-mutation and
   exfiltration as unclosed risks of the command itself — this design does not add a command-content
   validator (a closed-vocabulary allowlist, the way B3's `validate_repro_command` works, was assessed
   in round 1 as not realistically achievable for "start any dev server in any stack," unlike B3's
   narrower "re-run an existing test command" scope). Whether this residual is acceptable as a disclosed
   trade-off, or needs a narrower mechanism in a future revision, is left for the Orchestrator/human
   approving this design to weigh in on.
4. **Port-allocation TOCTOU across concurrent peer dispatches is a disclosed, accepted residual, not
   closed.** A future revision could add per-task dynamic port allocation (e.g. let the OS pick an
   ephemeral port and report it back) to close this fully; out of scope for this revision, named
   explicitly rather than left as an incorrect "sequential dispatches" assumption (round-1 SRE finding).
5. **A `start_command` that daemonizes/double-forks and escapes the tracked process group is a named,
   unclosed residual** (round 3, replacing the now-resolved policy-sourcing question) — see Failure
   strategy. No mechanism in this design detects or tears down such a process; a future revision could
   pursue a container/cgroup boundary or a host-level cwd-scoped process sweep, neither attempted here.
   Whether this residual is acceptable alongside the already-accepted local-mutation/exfiltration
   residual (Open Question 3) is left for the Orchestrator/human approving this design to weigh in on.
6. **The external `app_run` policy's exact schema-validation implementation (what counts as
   "malformed/incomplete," the precise YAML/JSON shape) is left for `change-impact-analyzer`/
   `implementation-planner` to size** as part of the concrete task breakdown — the fail-closed *default*
   (treat as absent) is now stated at the system-design level (round 3), but the validator's own
   exhaustive rule set is an implementation-level detail, not fully specified here.
