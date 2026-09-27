# System Design Spec — F1 Condition 1: lock-safety static classifier

**Readiness: Ready with open questions.**

**Source:** [2026-09-24-f1-review-evidence-gate-design.md](2026-09-24-f1-review-evidence-gate-design.md) (Track B, merged as [PR #298](https://github.com/luckyrjain/software-builder/pull/298)+[#299](https://github.com/luckyrjain/software-builder/pull/299)), [2026-09-24-f1-review-evidence-gate-architecture-review.md](2026-09-24-f1-review-evidence-gate-architecture-review.md) (Approved with conditions, Condition 1). Owner decision (2026-09-25): resolve Condition 1 with option (a), a narrow non-LLM purpose-built check — this spec is that check.

## Problem

`scripts/check_review_evidence.py`'s `build_verdict` (on `main` since PR #298) always returns
`verdict: "block"` for a sensitive PR — a `TODO(condition-1)` placeholder, since no real
classification logic exists. This spec designs that logic: a static, non-LLM classifier that
lets `review-evidence-post` auto-approve a sensitive-path PR when the diff shows no evidence of
the specific bug class F1 exists to catch (PR #289's lock-concurrency regression), and blocks
(defers to a human) otherwise. Conservative by construction: it never proves correctness, it
only rules out a bounded set of known-bad patterns; anything it can't confidently clear stays
blocked.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `scripts/lock_safety_patterns.py` (new) | Given a PR's changed Python files' *full source* (not diff hunks) and the diff's changed-line ranges, run four independent static checks and return a list of violations, each scoped to the exact file:line that triggered it | Pure function of (file contents, changed line ranges) → violation list; no I/O of its own beyond what its caller passes in | New module, mirrors `sensitive_path_match.py`'s shape: one pure classification function, no side effects |
| `fetch_pr_file_contents` (new function in `check_review_evidence.py`) | For each Python file the diff touches, fetch its full content at the PR's current head SHA via `gh api repos/<repo>/contents/<path>?ref=<sha>` (base64-decoded) | Read-only GitHub Contents API call, same no-checkout posture as the rest of this mechanism | `gh pr diff`'s hunks give limited context (a few lines around each change) — not enough to determine "is this flock call inside a try/finally," which requires seeing the whole enclosing function. Fetching full file content via the API (not `git checkout`) preserves the design's existing no-checkout invariant |
| `build_verdict` (modified, `check_review_evidence.py`) | Replace the `TODO(condition-1)` placeholder: for a sensitive PR, fetch changed Python files' content + changed-line ranges, run `lock_safety_patterns.check`, and produce `verdict: "approve"` only when zero violations are found; `verdict: "block"` with the violation list as `reason` otherwise | Orchestrates the new classifier; still writes the same verdict artifact shape `review-evidence-post.yml` already consumes | No change to the artifact schema — `verdict`/`pr_number`/`matched_globs`/`matched_content_patterns`/`reason` stay the same fields; `reason` becomes a real (possibly multi-line) explanation instead of the current fixed placeholder string |

## APIs

| Endpoint / method | Contract | Consumer(s) | Notes |
|--------------------|----------|-------------|-------|
| `lock_safety_patterns.check(files: dict[str, str], changed_lines: dict[str, set[int]]) -> list[Violation]` | Pure function. `files` maps changed-file path → full file content string (Python files only; non-`.py` files are skipped, not flagged). `changed_lines` maps the same paths → the set of line numbers the diff actually added/modified (from parsing `@@ -a,b +c,d @@` hunk headers). Returns one `Violation(file, line, rule, message)` per finding, empty list = clean | `build_verdict` | Each of the 4 rules below is independent; a violation from any one rule blocks the whole PR (conservative OR, not a weighted score) |
| `gh api repos/<repo>/contents/<path>?ref=<sha>` | GitHub Contents API, read-only, returns base64-encoded blob + metadata | `fetch_pr_file_contents` | Already implicitly authorized — `check_review_evidence.py` already holds `contents: read` for the base-pinned checkout step; this is the same permission, just used for one more read path instead of a `git checkout` |

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `Violation` | `file: str`, `line: int`, `rule: str` (one of the 4 rule ids below), `message: str` | Produced by `lock_safety_patterns.check`, consumed by `build_verdict` to build the verdict artifact's `reason` | `lock_safety_patterns.py` |

## The four rules (v1 scope)

Grounded directly in this repo's own existing, correct patterns — `scripts/install_engine.py`'s
`held_lock()` (a `@contextmanager` wrapping `try: ... yield ... finally: _unlock(fd); os.close(fd)`)
and `_defer_interrupts()`'s `_on_stop` handler, and `skills/pr-gatekeeper/scripts/idempotency_store.py`'s
`run_if_new` (`should_process` called before `subprocess.run`, `mark_processed` called only after a
zero exit) — so the rules describe what "looking like this codebase's own correct code" means, not an
invented standard.

| Rule id | Trigger (on an *added* line only — never flags pre-existing code the PR didn't touch) | Rationale |
|---------|-------------------------------------------------------------------------------------------|-----------|
| `lock-without-tryfinally` | A newly-added call to `fcntl.flock(`, `msvcrt.locking(`, or any function whose name matches `*lock*` and is called with a file descriptor/handle argument, where the AST's nearest enclosing statement is **not** inside a `try` block that has a non-empty `finally` | `held_lock()`'s own acquire (`_try_lock`) is called inside exactly this shape; a lock acquired without a guaranteed-release path is the direct bug class of PR #289 |
| `bare-except-added` | A newly-added `except:` with no exception type, or `except BaseException:` with an empty/`pass`-only body | Swallows `KeyboardInterrupt`/`SystemExit` along with real errors; this codebase's own lock/signal code uses typed `except OSError:`/`except Exception as exc:` throughout — zero bare `except:` found anywhere in `install_engine.py` today |
| `unsafe-signal-handler` | A newly-added `signal.signal(...)` call whose handler is a locally-defined function containing any statement other than: assignment (`Assign`/`AugAssign`/`AnnAssign`), `nonlocal`/`global`, `if`/`return`/`pass`, `raise`, or a call to `sys.exit`/`os._exit` | Matches `_on_stop`'s actual shape exactly (assign, if/return, if/raise, `sys.exit`) — a handler doing file I/O, acquiring a lock, or calling `subprocess` is the textbook async-signal-safety violation class |
| `idempotency-check-after-effect` | Within one function, a call matching `*mark_*`/`*save_*`/a write-type call (`subprocess.run`, `.write(`, `os.replace(`) whose line number is **less than** the line number of a call matching `*should_*`/`*check*`/`.get(` pattern that the same function also contains — i.e. the "mark done" call appears before the "is it already done" call in source order | `idempotency_store.run_if_new`'s own order — `should_process` (line ~103) strictly precedes `subprocess.run` (line ~105) which strictly precedes `mark_processed` (line ~107) — inverted order is the specific "idempotency key written before the guarded action ran" class of bug |

A file that adds none of these four patterns produces zero violations regardless of anything else
in the diff — this is deliberately narrow (structural patterns only), not a semantic correctness
prover. A PR that legitimately needs to touch locking/signal code in a way that trips one of these
rules still merges — it just needs a human reviewer once, same as every sensitive PR does today.

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| `build_verdict`'s classification | `sensitive → fetching_files → checking_patterns → verdict_approve (0 violations)` \| `sensitive → fetching_files → checking_patterns → verdict_block (>=1 violation)` \| `sensitive → fetching_files → verdict_error (contents API failure or unparseable Python — a `SyntaxError` from `ast.parse` fails closed to `block`, never skips the file silently)` \| `not_sensitive → (unchanged, no verdict artifact)` | `checking_patterns` always fully evaluates all 4 rules on every changed Python file before deciding, even after the first violation is found (so the verdict's `reason` lists every violation, not just the first) | A non-Python changed file (e.g. `docs/sensitive-paths.yaml` itself) is never fetched/parsed by this module — it stays sensitive via `sensitive_path_match`, but this classifier only ever evaluates `.py` files within the sensitive set, and blocks (never silently approves) a sensitive PR whose only changes are non-Python, since there's nothing for a structural Python check to clear |

## Consistency

| Boundary | Model | Why |
|----------|-------|-----|
| Verdict computation | Strong, single-writer | `review-evidence-post` computes the verdict itself, once per triggering run, from a base-pinned checkout + a `gh api` read at the PR's own head SHA — no shared mutable state, no cross-run coordination needed (existing design property, unchanged by this spec) |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `fetch_pr_file_contents` (new) | Yes — pure read of an immutable git blob at a fixed SHA | None needed; a transient `gh api` failure is a `GhApiError`, caught the same way `fetch_pr_diff`/`fetch_pr_reviews` already are, and fails the whole `analyze` run closed (existing pattern, no new retry logic introduced) |
| `lock_safety_patterns.check` | Yes — pure function, same inputs always produce the same violation list | N/A, no I/O |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Additional `gh api` calls per sensitive PR | One `contents` fetch per changed Python file in the sensitive set | Bounded by how many `.py` files a single PR touches under the sensitive glob list — open question how large that gets in practice; existing design's own Capacity section already notes PR volume against the seed list is unmeasured (Architecture Review Condition 3) |
| False-positive rate (legitimate lock/signal/idempotency changes blocked unnecessarily) | **Closed by Phase 0.5, 2026-09-25**: 3/9 historical PRs blocked (#289, #292, #296), 6/9 approved (#285, #288, #290, #293, #295, #297). See Rollout Phase 0.5 for the full result and its honest caveats — the historical #289/#292 bug (a TOCTOU race in the old directory-based stale-lock reclaim logic) is **not modeled by any of the 4 rules** and would not have been caught directly; that whole bug class was eliminated by #296's rewrite to OS-native `flock`, which this classifier's rules are actually grounded in | Ran `build_verdict` against each PR's real diff/head SHA via `gh api`, 2026-09-25 |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| `gh api .../contents/...` errors (rate limit, file too large, network) | `fetch_pr_file_contents` raises `GhApiError`, `build_verdict` catches it and produces `verdict: "block"` with the error as `reason` — never silently skips the file or defaults to approve |
| A changed Python file fails to parse (`ast.parse` raises `SyntaxError`) | Treated as a violation of its own (`rule: "unparseable"`) — a file the classifier cannot analyze is never treated as clean; fails closed the same direction as every other gap in this mechanism |
| A rule's AST walk hits an unexpected node shape (e.g. a lock call inside a lambda, a decorator this classifier's walker doesn't specifically handle) | The walker's default behavior for any construct it doesn't specifically recognize as "safe" is to **not** clear it — absence of a recognized-safe shape is not evidence of safety; only a rule actively firing produces a violation, so an unrecognized construct simply produces no violation for the rules that don't apply to it, while remaining subject to whichever rules do apply (e.g. a lock call inside a lambda still trips `lock-without-tryfinally` if there's no enclosing try/finally, lambda or not) |
| The classifier itself has a bug and produces a false `verdict: "approve"` on genuinely unsafe code | No different in kind from any other software defect in this gate's own enforcement code — `lock_safety_patterns.py` is itself added to `docs/sensitive-paths.yaml`'s self-protecting globs (see Rollout), so any future change to it requires the same review evidence, and per Architecture Review Condition 1's own framing this is exactly why the check starts narrow (small, auditable, testable) rather than broad |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `build_verdict`'s printed `reason` (already logged by the existing `run_analyze` print statement) | Now carries the actual rule id(s) and file:line(s) that blocked a PR, instead of the fixed Condition-1 placeholder string — directly actionable for whoever reviews a blocked sensitive PR |
| Recommended, not yet designed: a count of `verdict_approve` vs `verdict_block` outcomes over time | Would let the owner see the false-positive/false-negative balance in practice; not scoped into this spec — could reuse `check_sensitive_path_bypass.py`'s existing weekly-scan cadence if wanted later |

## Rollout plan

| Phase | Scope | Notes |
|-------|-------|-------|
| 0 | Implement `scripts/lock_safety_patterns.py` + `fetch_pr_file_contents` + updated `build_verdict`, with unit tests covering all 4 rules against both a clean case and a violating case, using this repo's own `held_lock`/`_on_stop`/`run_if_new` as the clean fixtures (they must produce zero violations) | Add `scripts/lock_safety_patterns.py` to `docs/sensitive-paths.yaml`'s self-protecting globs, same as every other enforcement file |
| 0.5 (done 2026-09-25) | Dry-ran `build_verdict` against the real diff + head SHA of all 9 PRs (#285/#288-297). Result: 6/9 `approve` (#285, #288, #290, #293, #295, #297), 3/9 `block` (#289, #292, #296). **Honest caveat, not a clean "it works" result**: #289/#292's blocks are *coincidental* — both hit `idempotency-check-after-effect` in `scripts/tests/test_install_rollback.py`, a test-file ordering pattern unrelated to those PRs' actual fix (a TOCTOU race in the old directory-based stale-lock-reclaim logic — a bug class none of the 4 rules model at all, since that whole design was later replaced). #296 (the flock-based rewrite this classifier's rules are actually grounded in) blocks for a **real false positive**: `_try_lock`'s raw `flock()`/`msvcrt.locking()` calls have no *own-function* try/finally — the real release guarantee comes from the caller, `held_lock()`, one function up. Same shape as the `mr_lock()` false positive found during PR #300's own review. Net: zero observed false *approvals* of unsafe code in this sample; the one real false positive is the accepted degradation (costs a human review, never an unsafe auto-approve); the classifier does not, and was never designed to, catch #289's own specific historical bug class — its actual target is regressions in the current `held_lock`/`idempotency_store` patterns going forward | Closed the Capacity "false-positive rate" open question with real data instead of shipping blind |
| 1 | Same as the existing F1 design's Rollout Phase 1 — smoke-test the full async chain live, now with a real (non-placeholder) verdict path. Still blocked on `REVIEW_EVIDENCE_BOT_TOKEN` provisioning (owner-only step, unchanged by this spec) | No change to Phase 1's own smoke-test requirements from the original design doc |

## Open questions

- **Accepted residual risk, PR #300 round 3**: `_has_ancestor_try_finally`'s scope-boundary fix (rounds 1-2) closes the "AST-proximate but not execution-time-covered by a try/finally" bug class for `FunctionDef`/`AsyncFunctionDef`/`Lambda`/`GeneratorExp`, but not for a construct-now/execute-later coroutine pattern (`coro = some_async_lock_fn(fd)` inside a try/finally, `await coro` — or `asyncio.create_task(...)` — outside it). Empirically confirmed as a real escape, but judged below the plausibility bar for this repo today: zero `async def`/`asyncio` usage exists anywhere in first-party code (all real lock code is synchronous `fcntl`-based). Revisit if this repo adopts asyncio for anything lock-adjacent.
- **Pre-existing, orthogonal limitation, PR #300 round 3**: a lock-acquiring call referenced without being its own `Call` node — e.g. `functools.partial(fcntl.flock, fd, fcntl.LOCK_EX)` built inside a try/finally and invoked later, or a bare `acquire_lock` name passed to `map(...)`/stored in a variable — is invisible to the classifier entirely (the rule only ever inspects `Call` nodes whose own name contains a lock token). This predates and is independent of the ancestor-walk scope-boundary fixes; not a regression, just the rule's detection surface only covering direct call sites.
- False-positive rate against this repo's real history (Phase 0.5 above is the recommended way to close this before Phase 1).
- Whether `lock-without-tryfinally` should also recognize a `with`-statement-based custom context manager as safe even when it isn't literally `held_lock` (v1 scope only checks for a `try/finally` shape directly enclosing the call; a future revision could special-case known-safe wrapper names) — left narrow deliberately for v1, noted as a possible false-positive source Phase 0.5 would surface.
- Whether a non-Python sensitive-path change (e.g. an edit to `docs/sensitive-paths.yaml` itself) should ever be auto-approvable by some other narrow check, or should always require a human — this spec takes the conservative position (always block) since it's out of scope for a "lock safety" classifier by name; a separate decision if the owner wants a fast-path here.
