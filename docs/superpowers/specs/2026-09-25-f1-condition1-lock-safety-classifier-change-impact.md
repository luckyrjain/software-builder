# Change impact report — F1 Condition 1 lock-safety classifier

**title:** F1 Condition 1 resolution — lock-safety static classifier for `review-evidence-post`
**assessment_target:** [2026-09-25-f1-condition1-lock-safety-classifier-design.md](2026-09-25-f1-condition1-lock-safety-classifier-design.md) (`system_design_spec`, `proposed_state`)
**coverage_status:** COMPLETE — repository read available and used to ground every field (existing `check_review_evidence.py`/`sensitive_path_match.py`/`install_engine.py`/`idempotency_store.py` all read in full or in relevant part; `scripts/README.md` and `scripts/tests/` conventions confirmed directly)
**criticality:** High — this is the first component that lets the F1 gate produce a real `approve` verdict rather than always `block`. A false negative here (approving genuinely unsafe lock/signal/idempotency code) directly defeats the mechanism's whole purpose; a bug in this component is itself security-relevant in a way most of Phase 0's authoring work was not, since Phase 0 never actually approved anything

## material_unknowns

False-positive/false-negative rate is unmeasured (the design's own Open Questions/Capacity sections
already say so, and its Rollout Phase 0.5 proposes closing this with a dry-run against PRs
#285/#288-297 before real activation — that dry-run is not part of this change's own scope, it's a
recommended follow-up validation step).

## change_classes

- **New pure module**: `scripts/lock_safety_patterns.py` (AST-based classifier, no I/O of its own)
- **New capability + modified decision logic in an existing, already-shipped file**: `scripts/check_review_evidence.py` — new `fetch_pr_file_contents` function; `build_verdict` changes from an unconditional `"block"` return to a real branch (fetch → classify → approve-or-block). This is a **behavior change to code that is already live on `main`** (merged via PR #298), even though its current behavior (always block) has never yet produced a real `approve`, since Phase 1 (bot credential, real activation) hasn't started.
- **Config edit**: `docs/sensitive-paths.yaml` — add the new module to its own self-protecting globs.
- **No workflow YAML change**: `review-evidence-post.yml` already calls `check_review_evidence.py analyze`; that call site is unchanged.
- **No change** to `docs/github-ruleset-main.json`, `CODEOWNERS`, or any file outside the four above plus new/updated tests.

## impacted_repositories

- `software-builder` only.

## impacted_services

- N/A — CI/governance mechanism, not a runtime service, same as F1 Track B's original classification.

## impacted_contracts

- **`build_verdict`'s return shape**: unchanged field names (`verdict`, `pr_number`, `matched_globs`, `matched_content_patterns`, `reason`) — only `verdict`'s possible value (`"approve"` becomes reachable for the first time) and `reason`'s content (a real multi-violation explanation instead of the fixed placeholder string) change. `review-evidence-post.yml`'s consumption of this artifact (`verdict == "approve"` → post a review) is unaffected — it was already written to handle either value, it just never observed `"approve"` before.
- **New dependency on the GitHub Contents API** (`gh api repos/<repo>/contents/<path>?ref=<sha>`) — a new external call this component makes; not a new external service dependency for the repo overall (already depends on `gh`/GitHub's API broadly), but a new specific endpoint this specific script now calls.
- **`lock_safety_patterns.check`'s function signature** — new, internal to this repo, no external consumer yet (only `build_verdict` calls it, per the design).

## impacted_data

- `docs/sensitive-paths.yaml`'s `globs` list gains one entry (`scripts/lock_safety_patterns.py`). No other data model change — no database, no persisted state beyond the existing verdict-artifact JSON file (unchanged shape).

## impacted_dependencies

- **`scripts/README.md`** — needs a new row for `scripts/lock_safety_patterns.py`, matching the existing table convention (confirmed at `scripts/README.md:120,141` for its two sibling F1 scripts).
- **`scripts/tests/test_<script>.py` naming convention** (confirmed established by PR #298: `test_check_review_evidence.py`, `test_sensitive_path_match.py`, `test_check_sensitive_path_bypass.py` all exist) — the new module needs `scripts/tests/test_lock_safety_patterns.py`; the existing `scripts/tests/test_check_review_evidence.py` needs new/updated test cases for `build_verdict`'s changed behavior (it currently only tests the always-`"block"` placeholder path, which this change removes).
- **`make lint-python`** (via `lint-static`) automatically sweeps the new module and the new test file — confirmed no Makefile wiring needed, same as PR #298's own finding for its scripts.
- **No new PyPI dependency** — `ast` is Python stdlib; `gh api` is a `subprocess` call, matching `check_review_evidence.py`'s existing pattern for every other GitHub read it already does.
- **`docs/skill-framework/shared/prompt-injection.md`** — the design's own Failure-strategy/Observability sections don't name this explicitly, but it's worth stating directly: `lock_safety_patterns.check` parses Python *source code* with `ast.parse`, which is a stronger trust requirement than the existing diff-text-as-data posture (`ast.parse` executes no code, but a maliciously crafted file that exploits a real bug in Python's own parser would be a different risk class than string/regex matching). This is a standard, low-risk trust boundary (the same one every Python linter/static-analysis tool already accepts), not a new doctrine violation, but it's a genuine dependency worth naming since it wasn't present in the original F1 design (which was diff-text-only, never full-file `ast.parse`).

## impacted_owners

- **Repo owner (`@luckyrjain`)**: sole owner, unchanged from F1 Track B. No new credential/operational owner introduced by this change specifically (the bot-credential provisioning it will eventually feed into was already owner-scoped by the original design).

## required_tests

- `scripts/tests/test_lock_safety_patterns.py` — each of the 4 rules needs at minimum: (a) a clean case that must NOT trigger the rule, (b) a violating case that must trigger it, (c) the "added-line-only" scoping property (a violation present only in *unchanged* lines of the file must not fire — this is a load-bearing correctness property named explicitly in the design's rule table, "never flags pre-existing code the PR didn't touch").
- **Golden-fixture tests using this repo's own real code**: per the design's own stated grounding, `held_lock()` and `_on_stop()` (from `scripts/install_engine.py`) and `run_if_new()` (from `skills/pr-gatekeeper/scripts/idempotency_store.py`) should each be used as literal clean fixtures — feeding their actual current source through `lock_safety_patterns.check` and asserting zero violations. This is the single most valuable test class here: if the classifier flags the codebase's own reference-correct patterns, the design's central claim ("grounded in what this codebase's own correct code looks like") is falsified before it ever reaches a real PR.
- `scripts/tests/test_check_review_evidence.py` — update/add cases for `build_verdict`'s new branches: zero violations → `verdict: "approve"`; one or more violations → `verdict: "block"` with `reason` naming them; a `gh api contents` failure → `verdict: "block"` (fail closed, per the design's Failure strategy); a Python file that fails `ast.parse` → treated as its own violation (fail closed), not silently skipped.
- `make lint-python`, `make lint-actions-pinning`, `make lint-actions-security` — same standing checks every prior F1 change ran; `lint-actions-pinning`/`-security` are unaffected here (no workflow file changes) but should still be run as a no-regression sanity check given they gate every PR in this repo already.

## operational_impacts

- **New Actions minutes**: one additional `gh api contents` call per changed Python file in a sensitive PR's diff — bounded by how many `.py` files a single sensitive PR touches, same scope-limiting property the original design already relies on (`sensitive_path_match` gates which PRs trigger analysis at all).
- **First time this mechanism can produce a real `approve`**: operationally significant even though Phase 1 (bot credential) hasn't started — once that credential exists, this is the component whose correctness directly determines what merges without human review. Worth the extra test rigor named above.
- **No impact on required checks** — `lint-static`/`lint-suites` remain the only required checks; `review-evidence-check` stays un-required (Phase 0/0.5 scope, unchanged).

## review_triggers

- **`security-review`**: **recommended**, not a hard trigger under this skill's own trigger vocabulary (no CVE/authN/authZ/injection surface changes — this is a static-analysis classifier, not a new attack surface on its own), but flagged here given the criticality note above: a classifier whose false negatives translate into unreviewed merges of exactly the bug class (concurrency/crash-safety) this repo has already been burned by once (#289) is a reasonable candidate for a focused look at the 4 rules' actual AST logic once implemented, before Phase 1 activation. Not required to start Phase 0 authoring of this component.
- **`api-design-review`**: not triggered — no external API surface.
- **`database-review`**: not triggered — no database/schema.
- **`observability-review`**: not triggered this round (the design's own Observability section already scoped its one recommendation as informal/future, unchanged from F1 Track B's original disposition).

## unknowns

- False-positive/false-negative rate against real historical PRs (design's own Open Question; Phase 0.5 dry-run is the named way to close it, not part of this change's own scope).
- Whether the `lock-without-tryfinally` rule's narrow try/finally-only recognition (not extended to arbitrary named context-manager wrappers) produces avoidable false positives in practice — same open question the design itself already names, not resolved by this report.

## evidence_refs

- `docs/superpowers/specs/2026-09-25-f1-condition1-lock-safety-classifier-design.md` (system design spec, full document)
- `scripts/check_review_evidence.py` (current `main`, full file read — `build_verdict`'s existing `TODO(condition-1)` placeholder, artifact schema)
- `scripts/sensitive_path_match.py` (current `main`, full file read — the sibling pure-classifier module this new one mirrors in shape)
- `scripts/install_engine.py` lines ~89-136, ~195-227, ~306-374 (`_try_lock`/`_unlock`, `_on_stop`, `held_lock`) — the clean-fixture source this design's rules are grounded in
- `skills/pr-gatekeeper/scripts/idempotency_store.py` (full file read — `run_if_new`'s check-before-act ordering, the clean fixture for rule 4)
- `scripts/README.md:120,141` — documentation-row convention for the two existing F1 scripts
- `scripts/tests/` directory listing — confirms `test_check_review_evidence.py`, `test_sensitive_path_match.py`, `test_check_sensitive_path_bypass.py` all exist, grounding the naming convention
- `docs/sensitive-paths.yaml` (current `main`, post-#299) — confirms the self-protection glob list this change adds one entry to
