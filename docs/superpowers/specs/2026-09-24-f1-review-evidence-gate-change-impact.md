# Change impact report — F1 review-evidence gate (Track B)

**title:** F1 review-evidence gate — Track B (review-evidence-check / -analyze / -post, sensitive_path_match, sensitive-paths.yaml)
**assessment_target:** [2026-09-24-f1-review-evidence-gate-design.md](2026-09-24-f1-review-evidence-gate-design.md) (`system_design_spec`, `proposed_state`), validated by [2026-09-24-f1-review-evidence-gate-architecture-review.md](2026-09-24-f1-review-evidence-gate-architecture-review.md) (Approved with conditions)
**coverage_status:** COMPLETE — repository read was available and used to ground every field (workflow conventions, Makefile targets, README/test-naming conventions, CODEOWNERS); the open items below are genuine unresolved questions (`material_unknowns`/`unknowns`), not gaps from missing evidence access
**criticality:** Medium — the change itself is small and additive (five new files, one doc-of-record edit, no existing production code modified), but it adds a new required merge gate that, once activated (design Rollout Phase 3), affects every future PR touching the seeded sensitive paths, including the repo's most crash-safety-critical scripts

## material_unknowns

None material enough to block Phase 0 authoring. The three items in `unknowns` below (PR volume,
`-analyze` job runtime, exact current-file match against the lock/signal/idempotency glob) are open
questions the design and architecture review already name and explicitly do not treat as blocking —
carried here for completeness, not as a new gap.

## change_classes

- **New CI workflow + scripts** (additive): `.github/workflows/review-evidence.yml`, `scripts/sensitive_path_match.py`, `scripts/check_review_evidence.py`, `scripts/check_sensitive_path_bypass.py`
- **New config/data file**: `docs/sensitive-paths.yaml`
- **Doc-of-record edit, no live-system effect on its own**: `docs/github-ruleset-main.json` (Phase 3 only, per Rollout — the live ruleset change is a separate, manual, repo-admin GitHub-UI action)
- **No existing production code is modified.** This is the change's most significant impact-limiting property: it adds a new, initially non-required, gate rather than touching `scripts/install_engine.py`, `skills/loop-task-implementer/scripts/run_log.py`, or any other file the gate will eventually protect.

## impacted_repositories

- `software-builder` only (this repo). No cross-repo impact — the design is entirely self-contained to this repository's own CI and branch-protection configuration.

## impacted_services

- N/A — this is a CI/governance mechanism, not a runtime service. The closest analog is "GitHub's required-status-checks evaluator" (external, unowned by this repo) and the repo's existing `.github/workflows/*` CI jobs, none of which this design modifies.

## impacted_contracts

- **New status-check context**: `review-evidence-check` — a new contract between this workflow and GitHub's ruleset evaluator. Consumer: `docs/github-ruleset-main.json`'s required-status-checks list (Phase 3, additive — `lint-static`/`lint-suites` remain required and unmodified).
- **GitHub Reviews API** (existing, external, read-only consumer): `gh api repos/<repo>/pulls/<n>/reviews` — no contract change on GitHub's side, this design only reads it more precisely (most-recent-per-reviewer, SHA-bound) than an ad hoc check would.
- **GitHub Artifacts API** (existing, external): `actions/download-artifact@v4` with an explicit `run-id` pin — new consumer (`review-evidence-post`), no existing consumer in this repo's `.github/workflows/` today per a search of the five existing workflow files; this is a new dependency shape for the repo's CI, not a new external dependency (the action is already a common GitHub-provided action, not a third-party one).

## impacted_data

- `docs/sensitive-paths.yaml` (new): the one config file that scopes the whole mechanism. Per the design's own self-protection rule, this file's path is a permanent member of its own `globs` list — so any future edit to it is itself gated by the mechanism it configures, once Phase 3 activates.
- No user data, no persisted application data, no database — this is repository/CI configuration only.

## impacted_dependencies

Grounded in this repo's actual existing conventions (checked directly, not inferred):

- **`scripts/README.md`** documents every `scripts/*.py` file in a table (confirmed convention: `check_github_ruleset.py`'s row exists at `scripts/README.md:115`). The three new scripts (`sensitive_path_match.py`, `check_review_evidence.py`, `check_sensitive_path_bypass.py`) need rows added here — a real, small, easily-missed follow-up if Phase 0 only writes the scripts themselves.
- **`scripts/tests/test_<script>.py` naming convention** (confirmed: `test_check_github_ruleset.py`, `test_check_golden_staleness.py`, `test_check_pinned_actions.py` all exist alongside their subjects). The three new scripts need matching test files under this convention; the design's own Rollout plan (Phase 0) doesn't explicitly name test authorship as a step — see `required_tests` below.
- **`make/core.mk`'s `lint-static` target** already runs `lint-python`, `lint-actions-pinning`, `lint-actions-security`, `generate-check`, `validate-registry`, `lint-scripts-shellcheck`, and `verify-github-ruleset` (confirmed at `make/core.mk:121-122,218`) — the three new Python scripts are automatically swept into `lint-python` with no Makefile wiring needed, but `.github/workflows/review-evidence.yml` must satisfy `lint-actions-pinning` (pinned action SHAs, confirmed as the existing convention in `secret-scan.yml`/`dependency-review.yml`, both of which pin a minimal top-level `permissions: contents: read`) and `lint-actions-security` before it can merge even un-required in Phase 0.
- **`docs/skill-framework/shared/prompt-injection.md`**: the architecture review's Condition 1 makes this doctrine's compliance an acceptance criterion for whichever review pass `review-evidence-analyze` runs — a real dependency on existing, unmodified doctrine, not a new one.
- **No dependency on `requirements.txt`/`requirements.lock`** — the design's scripts are stated as pure `gh` CLI + stdlib Python (diff-text parsing, glob/regex matching), consistent with `check_github_ruleset.py`'s own existing pattern (a `subprocess` call to `gh`, no new PyPI package).

## impacted_owners

- **Repo owner (`@luckyrjain`)**: sole owner per `CODEOWNERS`, and the only party who can perform the Phase 3 manual ruleset-apply step and provision the Phase 0 bot credential (architecture review's Condition 2 flags the latter's ongoing health as unmonitored).
- No other team or owner is implicated — consistent with this being a solo-maintainer repo throughout the design and architecture review.

## required_tests

Grounded in the repo's own existing test conventions for comparable scripts (`test_check_github_ruleset.py` as the closest analog — same shape: a script that reads GitHub state and reports a verdict):

- `scripts/tests/test_sensitive_path_match.py` — glob matching, content-pattern matching, and the specific evasion case the design exists to close (rename out of a listed path still caught by content patterns; a match against the self-protecting entries for the enforcement files themselves).
- `scripts/tests/test_check_review_evidence.py` — the three exit codes (0/1/2); the most-recent-per-`user.login` reduction (architecture review didn't flag this, but the design's round-3 revision history, finding 8, makes it a load-bearing correctness property that must be directly tested, not just documented); SHA-binding (a stale-commit review must not satisfy a newer head).
- `scripts/tests/test_check_sensitive_path_bypass.py` — the self-alerting-on-its-own-failure behavior specifically (design's Failure strategy row 10; SRE's round-2 finding), since this is the one script whose entire purpose is to fail loud, and a test that never exercises its own-failure path would leave that property unverified.
- **`.github/workflows/review-evidence.yml` itself has no unit-test equivalent** in this repo's conventions (none of the five existing workflow files have one) — the design's own Rollout Phase 1 smoke-test step is the intended verification for the workflow's async behavior (trigger wiring, `workflow_run` chaining, `concurrency` cancellation), and per architecture review's Condition 1, must additionally exercise an adversarial-diff-content case if the LLM-backed review pass is chosen.
- **Architecture review's Condition 1** (prompt-injection test case) and **Condition 3** (one-time `git log` capacity sizing) are themselves required-test-equivalent acceptance criteria for Phase 0 completion, not optional follow-ups.

## operational_impacts

- **New Actions minutes**: bounded to PRs `sensitive_path_match` flags (design, Components) — not every PR. No numeric estimate available (see `material_unknowns`).
- **New credential to provision and, per architecture review Condition 2, monitor**: a PAT or GitHub App install for `review-evidence-post`. No rotation cadence stated in the design; this report doesn't add one, since that's Condition 2's job to resolve, not this analysis's.
- **New required merge gate, once Phase 3 activates**: every future PR touching the seeded sensitive paths (`scripts/install_engine.py`, `skills/loop-task-implementer/scripts/run_log.py`, `skills/pr-gatekeeper/scripts/idempotency_store.py`, any `skills/*/scripts/*lock*|*signal*|*idempotency*`, and the enforcement mechanism's own four files) must clear it to merge. This is the change's actual operational purpose, not a side effect — flagged here for completeness, not as a risk.
- **No impact on existing required checks** (`lint-static`, `lint-suites`) — additive only, per the design's Rollout sequencing.

## review_triggers

- **`security-review`**: already substantively covered by three rounds of dedicated adversarial security review documented in the design's own Revision history (23 findings closed) and this report's parent architecture review (Security section) — no additional trigger needed before Phase 0, but Condition 1's prompt-injection test case is itself a security-relevant acceptance criterion Phase 0 must close.
- **`api-design-review`**: not triggered — the "APIs" in this design are CLI/CI-shaped (GitHub's own Reviews/Artifacts/Actions APIs, consumed read-only or narrowly-scoped), not a new API surface this repo exposes to others.
- **`database-review`**: not triggered — no database, no schema; `docs/sensitive-paths.yaml`'s two-key YAML shape is already fully specified in the design's Data model section.
- **`observability-review`**: **recommended**, informally rather than as a hard trigger — architecture review's Condition 2 (bot-credential health monitoring) is exactly this skill's domain, and a short `observability-review` pass on the design's Observability section (four signals, one gap) could close Condition 2 with more rigor than this report's own suggested fix.

## unknowns

- **PR volume against `sensitive-path-list`** — architecture review's Scale-limits finding; not computed by this report either (repository read was used for convention-grounding, not for the `git log --since=...` count both the design and the architecture review already name as the way to close this — that command wasn't run as part of this analysis, since sizing the number is Condition 3's job, assigned to Phase 0, not to this pre-implementation report).
- **Job runtime for `review-evidence-analyze`'s review pass** — depends on which check is chosen (design's Open Questions), not yet decided.
- **Exact scope of "any `skills/*/scripts/*lock*|*signal*|*idempotency*`"** — the design names this as a glob pattern for the Phase 0 seed list; this report did not enumerate the actual current matching files (a quick, cheap check Phase 0's author should do once, to seed the list accurately rather than leave it as a live pattern needing re-derivation at every list edit — flagged here as a `material_unknown`, not blocking).

## evidence_refs

- `docs/superpowers/specs/2026-09-24-f1-review-evidence-gate-design.md` (system design spec, full document)
- `docs/superpowers/specs/2026-09-24-f1-review-evidence-gate-architecture-review.md` (architecture review, Approved with conditions)
- `docs/github-ruleset-main.json`, `scripts/check_github_ruleset.py`, `CONTRIBUTING.md` (branch-protection-drift section) — grounding for the Phase 3 doc-of-record vs. live-ruleset distinction
- `.github/workflows/secret-scan.yml`, `.github/workflows/dependency-review.yml` — grounding for this repo's existing workflow-file convention (pinned actions, minimal top-level `permissions: contents: read`)
- `make/core.mk:121-122,218,239` — grounding for `lint-static`/`lint-suites`/`verify-github-ruleset` wiring
- `scripts/README.md:115`, `scripts/tests/test_check_github_ruleset.py` (directory listing) — grounding for the documentation-row and test-naming conventions new scripts must follow
- `CODEOWNERS` — grounding for single-owner confirmation
