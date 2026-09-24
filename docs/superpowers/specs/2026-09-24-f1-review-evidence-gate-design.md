# System Design Spec — F1 review-evidence gate (two candidate tracks)

**Date:** 2026-09-24
**Status:** Proposed (revised three times after adversarial review — see "Revision history" at the end)
**Source:** [2026-09-24-autonomous-engineer-gap-reanalysis.md](../plans/2026-09-24-autonomous-engineer-gap-reanalysis.md), ticket F1

**Readiness: Ready with open questions.** Per-track: Track B's mechanism is now fully specified end to
end — including the async approval chain actually completing (an earlier revision's design could never
go green on its own) and the fork/token-scoping edge cases three adversarial rounds surfaced. Its
remaining open questions are scope/policy choices (which review check, which credential type), not
missing design; each has a stated hard constraint (Open Questions) rather than being left free-floating.
Track A's design is also complete but is entirely contingent on decision #6, which this spec does not
make.

Scope note: this design does **not** decide whether software-builder dogfoods `loop-task-implementer`
on its own repository or exempts itself with a substitute gate — that is decision #6 in
[2026-09-24-autonomous-engineer-gap-reanalysis.md](../plans/2026-09-24-autonomous-engineer-gap-reanalysis.md),
routed to `engineering-decision-discovery`. This spec designs two candidate mechanisms to an
implementation-oriented level so the owner has concrete options — but see the revision history: after
adversarial review, **Track B is no longer contingent on that decision at all**. It's a fully independent,
CI-native mechanism, shippable regardless of what the owner decides for Track A.

Problem this closes: PRs #285, #288–290, #292, #293, #295–297 (the install-engine `flock`/signal-handling
rewrite) merged with `required_approving_review_count: 0` and no independent review evidence; #289 shipped
a lock-concurrency regression caught only by later ad hoc review (fixed in #292).

Existing system context used below: `docs/github-ruleset-main.json` (required checks: `lint-static`,
`lint-suites`; `required_approving_review_count: 0`, `require_code_owner_review: false`; this file is a
**verify-only mirror** of the live ruleset, never machine-applied — see Rollout) and
`scripts/check_github_ruleset.py` (confirms the live ruleset can only be *read* via `gh api
repos/.../rulesets/<id>`, which needs Administration:Read that the default Actions `GITHUB_TOKEN` cannot
hold — so ruleset changes are a maintainer-run, local-only, manual-UI action, by design, per
`CONTRIBUTING.md`); `CODEOWNERS` (exists, single owner `@luckyrjain`, already covers `/scripts/`,
`/skills.yaml`, `/.github/`, `/Makefile` — but toothless today since code-owner review isn't required);
`run_log.py`'s append-only, `--expect-head`-anchored record format (reused by Track A only — **not**
by Track B, see revision history); `.github/workflows/` (existing jobs: `codeql`, `dependency-review`,
`lint`, `live-eval`, `release`, `scorecard`, `secret-scan` — none does this; `review-evidence.yml` would be
new, following their convention of pinned action SHAs and a minimal top-level `permissions: contents:
read` with job-level additive scopes, e.g. `dependency-review.yml`/`secret-scan.yml`); the repository is
public (`isPrivate: false`); `isolation_primitive_used` enum already defined in
`skills/loop-task-implementer/workflow/orchestrator.md:322` (`SUBAGENT | FRESH_SESSION | WORKTREE |
SEQUENTIAL_SIMULATION`, Track A only).

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `frozen-skill-snapshot` (Track A) | A pinned, read-only checkout of `orchestrator.md`/`builder.md`/`reviewer.md`/the scripts they invoke, resolved fresh at the start of each self-hosted run (never re-read mid-run) and used by the Orchestrator and Reviewer roles | Instruction consistency for one run; does not own the target repo's working tree | Solves the self-hosting bootstrap problem: a Builder editing `skills/loop-task-implementer/workflow/reviewer.md` mid-run must never change what the Reviewer role reads for that same run. Same pattern the install engine already uses for `cli/sb/_registry_snapshot/`. Requires a POSIX runner — `run_log.py` refuses to run outside POSIX by design (gap-reanalysis finding F2), so a self-hosted run cannot execute on native Windows |
| `self-host-target-worktree` (Track A) | The actual worktree the Builder edits — this repo's own source, checked out per the existing `WORKTREE` isolation primitive | The change under review | No new component; reuses `loop-task-implementer`'s existing worktree-per-task convention, just pointed at this repo instead of an external one |
| `review-evidence-check` (Track B, **fully independent of Track A**) | A required CI status check, run on every push to a PR touching `sensitive-path-list` **and re-run when a qualifying review is posted**, that fails closed unless the GitHub Reviews API shows the *most recent* review per `user.login`, at the PR's current head SHA, being `APPROVED` from a login other than the author | Gate enforcement only; never edits code, never merges | New script + new workflow. Satisfiable two ways, neither requiring Track A: (i) a genuine second human reviewer, or (ii) `review-evidence-post` below, which independently re-derives its own verdict and posts an approving review under a bot identity |
| `sensitive_path_match` (Track B, new shared module) | The one place `sensitive-path-list` (globs + content patterns) is matched against a diff; called by `scripts/check_review_evidence.py`'s `check` and `analyze` subcommands alike (both live in that one script — `review-evidence-post` invokes `analyze` directly as a step, not as a separate CI job), so the two paths never independently re-derive "is this PR sensitive" and drift out of sync | A pure function/small script, no side effects | Closes a duplicated-logic gap a reviewer flagged: without a single shared matcher, `check` and `analyze` could each implement "sensitive" slightly differently over time |
| `review-evidence-post` (Track B, new) | Triggered by `workflow_run` watching the `Review Evidence` workflow's (`review-evidence.yml`) completion — necessarily from a **separate** workflow file, `review-evidence-post.yml`, since GitHub Actions rejects a `workflow_run` trigger that watches its own workflow ("Workflow ... cannot listen to itself", HTTP 422 — invalidates the whole file's jobs, not just the offending one). Gated to a same-repository PR (`github.event.workflow_run.head_repository.full_name == github.repository` — see Failure strategy for why fork-originated runs are explicitly excluded, not merely "can't without a PAT" as an earlier revision incorrectly claimed) **and, narrowly, `github.event.workflow_run.conclusion != 'cancelled'`** (LENS-B-5, PR #298 follow-up — see Failure strategy for why this is deliberately not a `conclusion == 'success'` gate). Checks out with no `ref:` override, so under `workflow_run` its checkout — and its own step definitions, which GitHub always resolves from that same place — is the repository's default-branch tip, never the triggering PR's ref; independently re-runs `scripts/check_review_evidence.py analyze`'s classification against that base-pinned checkout and its own `gh pr diff` fetch (no artifact download, no trust in anything a `pull_request`-triggered job computed). If the resulting verdict is `approve`, posts `gh pr review --approve` under a bot identity against the **PR number GitHub's `workflow_run` event itself associates with the completed run** (`github.event.workflow_run.pull_requests[0].number`), never a value read from the diff or PR body | The only component holding `pull-requests: write`; computes its own verdict and posts a review, nothing else — no `actions: read` needed, since there is no cross-job artifact to fetch | Pinning the target PR to the trigger's own event context (not attacker-influenceable data) closes the "could a compromised run act on the wrong PR" risk a reviewer flagged. Recomputing the verdict itself, rather than trusting one written by a `pull_request`-triggered job, is the PR #298 remediation for LENS-A-1 (see Revision history) — an earlier `review-evidence-analyze`/`review-evidence-post` split was itself a forgeable trust boundary, because a `pull_request`-triggered job's step definitions are resolved from the PR's own branch, not the base. This is the piece that makes Track B viable for a solo maintainer with no second human account, without the self-hosting bootstrap risk Track A carries — it reads and comments, it never edits code |
| `sensitive-path-list` (Track B, new) | A declarative, version-controlled list of concurrency/crash-recovery-sensitive path globs, **plus a content-based supplement** (see APIs) so a rename/split can't silently evade it | Scope of what Track B gates | Self-protecting: its own file path **and** the enforcement mechanism's own files (`.github/workflows/review-evidence.yml`, `scripts/check_review_evidence.py`, `scripts/check_sensitive_path_bypass.py`) are all permanent members of its own `globs` — see Failure strategy. An earlier revision protected only the data file, leaving the enforcement code itself gateable-around; that gap is closed here |

## APIs

Interfaces here are CLI/CI-shaped, not HTTP.

| Interface | Contract | Consumer(s) | Notes |
|-----------|----------|-------------|-------|
| `review-evidence.yml` (new GitHub Actions workflow, **two** jobs) | `review-evidence-check` triggers on `pull_request` (`opened`, `synchronize`, `reopened`) **and `pull_request_review` (`submitted`)** — the second trigger is what lets the check actually go green once an approval lands asynchronously; without it the check evaluates once at push time (before `review-evidence-post` has had time to run), fails, and nothing ever re-evaluates it. Runs with `contents: read` top-level, `pull-requests: read` at the job level; checks out `github.event.pull_request.base.sha` only, never the PR ref. `check-sensitive-path-bypass` (the weekly bypass scanner, see its own row below) is the file's other job, triggered by `schedule`/`workflow_dispatch`, not by any PR event. `concurrency: { group: "review-evidence-\${{ github.event.pull_request.number \|\| github.event.workflow_run.pull_requests[0].number \|\| github.event.workflow_run.id \|\| github.run_id }}", cancel-in-progress: true }` — this exact formula is duplicated verbatim in `review-evidence-post.yml`, since concurrency groups are repository-wide, not scoped per workflow file. `review-evidence-check` reports status context `review-evidence-check`, matching what gets added to the ruleset's required-checks list | GitHub's required-status-checks evaluator | There is deliberately **no** `review-evidence-analyze` job in this file — a round-1 Phase 0 revision shipped one (a `pull_request`-triggered job whose step definitions GitHub resolves from the PR's own branch, so a same-repo PR could forge its "classify" step and have `review-evidence-post` trust the forged verdict); it was removed in PR #298's remediation for LENS-A-1. See `review-evidence-post.yml`'s row below and Revision history |
| `review-evidence-post.yml` (new, **separate** GitHub Actions workflow, one job: `review-evidence-post`) | Lives in its own file — not alongside `review-evidence-check` — because GitHub Actions rejects a `workflow_run` trigger that watches its own workflow's completion outright ("Workflow ... cannot listen to itself", HTTP 422; the whole file's jobs stop registering, not just the offending one). Triggers on `workflow_run` (`workflows: ["Review Evidence"]`, `types: [completed]`), gated to `github.event.workflow_run.event == 'pull_request' && github.event.workflow_run.head_repository.full_name == github.repository` (excludes fork-originated triggering runs — see Failure strategy) **and, narrowly, `github.event.workflow_run.conclusion != 'cancelled'`** (LENS-B-5, PR #298 follow-up) — deliberately **not** gated on `conclusion == 'success'`: the triggering run's aggregate conclusion is `failure` on almost every legitimate push, because `review-evidence-check` (a sibling job in that same run) is expected to fail until a real approval lands, so a bare success gate would permanently deadlock the mechanism — exactly the bug round-3 finding 1 already fixed once (see Revision history). Scoped to `contents: read` + `pull-requests: write` only — **no** `actions: read`, since this job downloads no artifact. Checks out with no `ref:` override, so under `workflow_run` its `GITHUB_SHA` (and therefore its own step definitions, which GitHub always resolves from that same ref) is the tip of the repository's default branch, never the triggering PR's ref. It independently re-runs `scripts/check_review_evidence.py analyze --pr <n> --out review-evidence-verdict.json` against that base-pinned checkout and its own `gh pr diff` fetch; if the verdict is `approve` and the artifact's `pr_number` matches this run's own `github.event.workflow_run.pull_requests[0].number`, posts `gh pr review --approve` under a separately-provisioned bot credential (`secrets.REVIEW_EVIDENCE_BOT_TOKEN`) — the default `GITHUB_TOKEN` cannot post an approving review at all, a GitHub platform restriction, not a scoping choice. `concurrency` uses the identical group-name formula `review-evidence.yml` uses (see above) | Posts directly to the GitHub Reviews API; `review-evidence-check`'s later `pull_request_review`-triggered re-run is what then reads that review back and turns the check green | Downloads and consumes nothing computed by any `pull_request`-triggered job — this is the PR #298 remediation for LENS-A-1 (see Revision history and this file's own header comment for the full trust-boundary writeup). Provisioning `REVIEW_EVIDENCE_BOT_TOKEN` is a Phase 0 rollout step |
| `scripts/check_review_evidence.py check --pr <n>` / `analyze --pr <n> --out <path>` (Track B, new; two subcommands, one script) | `check` (also the default when only `--pr <n>` is given, matching the design's original `--pr <n>` CLI contract): fetches the PR's current head SHA (`gh pr view --json headRefOid`) and full diff text via `gh pr diff <n>` (the patch body, not `--name-only`) — the same API call the content-pattern grep runs against, so there is never a repository checkout anywhere in this path. Calls `sensitive_path_match` (see Components) against the changed-file list and diff text; if sensitive, requires `gh api repos/<repo>/pulls/<n>/reviews`'s entries, **reduced to the most recent review per `user.login`**, to include one with `state: APPROVED`, `commit_id` equal to the current head SHA, and `user.login` != the PR author's login — a stale `APPROVED` from a reviewer who later left a `CHANGES_REQUESTED` review at the same commit no longer counts, because only that reviewer's latest verdict is considered. Exit `0` clean or not-sensitive, `1` evidence missing, `2` cannot determine (API error, malformed `sensitive-path-list`). `analyze`: classifies the same way via the same shared `sensitive_path_match` call, and for a sensitive PR writes a local verdict artifact (`verdict`, `pr_number`, plus matched-pattern detail) to `--out` — invoked directly by `review-evidence-post`'s own step, never by a separate `pull_request`-triggered job (see Components and Revision history for why a round-1 version of that split was a forgeable trust boundary). Phase 0 ships no real review pass yet: `build_verdict` always returns `block` for a sensitive PR (architecture review Condition 1, Open Questions) — there is no `approve` path to manipulate today | `review-evidence-check` runs the `check` subcommand via `review-evidence.yml`; `review-evidence-post` runs the `analyze` subcommand via `review-evidence-post.yml` | Binding evidence to `commit_id == current head SHA`, and to each reviewer's *latest* verdict at that SHA, via the Reviews API closes the critical gaps earlier drafts had: a forged free-text trailer, stale evidence surviving a later malicious push or a rebase, and stale evidence surviving a same-commit re-review — all now require a real, current, most-recent, API-recorded approval |
| `run_log.py run-id` / `append` / `verify` (Track A, optional citation only) | Unchanged — reused exactly as `loop-task-implementer` already defines it. A self-hosted run may still cite its `run_id`/`chain_head` in the PR body for human context | Anyone reading the PR later | **Not** part of `review-evidence-check`'s pass/fail logic — the log lives at a local `--log-dir`, explicitly outside any git repository by the run log's own design (`run-log.md:20-23`), so a GitHub Actions runner structurally cannot reach it to call `verify`. Treating it as CI-checkable evidence was the earlier draft's central flaw (see revision history). It remains useful as an audit trail for a human, just not as something the automated gate can verify |
| `scripts/check_sensitive_path_bypass.py` (new, scheduled) | Runs weekly (`schedule` trigger, default `GITHUB_TOKEN`, `pull-requests: read` + `issues: write`): lists merged PRs since the last run that touched `sensitive-path-list`, cross-checks each against a passed `review-evidence-check` run; opens a tracking issue for any that merged without one (i.e. via the ruleset's bypass-actor path) | Repo owner, surfaced as a GitHub issue | Turns "check GitHub's bypass log later, if you remember" into a loud, automatic finding — closes the passive-detection gap an earlier draft left |

## Events

Fully synchronous — no events. `review-evidence-check` is a CI job evaluated against a PR's current head
SHA; `check_sensitive_path_bypass.py` runs on a schedule but performs a single synchronous scan per run.
Track A reuses `run_log.py`'s existing synchronous append/verify calls.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| GitHub PR Review (existing GitHub entity, reused) | `state`, `commit_id`, `user.login`, `submitted_at` | The evidence `review-evidence-check` reads; one review per (reviewer, PR) pair, GitHub-managed | GitHub, read via `gh api .../pulls/<n>/reviews` |
| `SensitivePathList` (Track B, new) | `glob` (path pattern) list **and** `content_patterns` (regex list for the rename-evasion supplement) | Read by `check_review_evidence.py` on every PR; its own file path, **and** `.github/workflows/review-evidence.yml`, `scripts/check_review_evidence.py`, `scripts/check_sensitive_path_bypass.py`, are all permanent members of its own `globs` list | Repo owner; version-controlled at `docs/sensitive-paths.yaml`. Format: a two-key YAML mapping (`globs: [...]`, `content_patterns: [...]`) — chosen over per-entry `evidence_required` typing from the earlier draft, since Track B now has exactly one evidence type (an API-verified approval), removing the need to type each entry differently |
| `Record` (Track A) | Unchanged — `loop-task-implementer`'s existing run-log record | Optionally cited by `run_id`/`chain_head` in a PR body, not machine-checked by Track B | `run_log.py` (existing, not redesigned) |
| `CODEOWNERS` (existing) | path glob → owner | Coarser, pre-existing backstop; not modified by either track | Repo owner |

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| `review-evidence-check` (Track B) | `pending -> evidence_found (pass, exit 0)` \| `pending -> evidence_missing (fail, exit 1, PR blocked)` \| `pending -> undetermined (fail closed, exit 2, PR blocked)` | Re-evaluated on **every push to the PR head, and on every submitted review** (`pull_request_review: [submitted]`) — the second trigger is required, not cosmetic: on the triggering push, `review-evidence-post` hasn't run yet, so the check correctly finds `evidence_missing` at that moment; only the review-submitted re-run can later find `evidence_found` once an approval (human or bot) actually lands. Since evidence is SHA-bound, a rebase without a fresh `APPROVED` review at the new head simply re-enters `evidence_missing` rather than incorrectly reusing stale evidence | A malformed or empty `sensitive-path-list` is `undetermined` (exit `2`, fail closed) — never silently treated as "nothing is sensitive" |
| `review-evidence-post` (Track B) | `triggered -> skipped_cancelled (github.event.workflow_run.conclusion == 'cancelled' -- clean no-op, LENS-B-5)` \| `triggered -> skipped_cross_repo (fork-originated triggering run -- no-op)` \| `triggered -> classifying (same-repo, non-cancelled -- includes the common case of the triggering run's own conclusion being 'failure')` \| `classifying -> verdict_approve (posts an APPROVED review)` \| `classifying -> verdict_block (posts nothing, exits 0)` \| `classifying -> verdict_error (script/API error fails the job; never defaults to approve on timeout/error)` | Runs as a single job, triggered by `workflow_run` on `review-evidence.yml`'s completion. **No longer** a two-job `analyze -> artifact -> workflow_run -> post` handoff — an earlier revision (round 2/3) had `review-evidence-analyze` write a verdict artifact for a separate `review-evidence-post` job to trust; that handoff was itself a forgeable trust boundary and was removed in PR #298's remediation for LENS-A-1 (see Revision history) | Only this job ever writes to GitHub (a PR review, nothing else), and only after computing its own verdict from a base-pinned checkout — it trusts nothing computed by any `pull_request`-triggered job. `review-evidence-check` stays `evidence_missing` unless and until a real `APPROVED` review lands, from this job or a human |
| Self-hosted task (Track A) | Reuses `loop-task-implementer`'s existing `NOT_STARTED -> BUILDING -> REVIEWING -> ... -> COMPLETE \| ESCALATED` lifecycle unmodified | Before `BUILDING` starts, resolve `frozen-skill-snapshot` fresh (once per run, never re-read afterward); if it can't be resolved, `ESCALATE` rather than fall back to live, possibly-Builder-edited instructions. Once `review-evidence-check` exists, snapshot eligibility should tighten to "the last `main` commit whose merging PR itself passed `review-evidence-check`," not merely lint-green — `lint-static`/`lint-suites` alone is exactly the CI class that let #289's regression through. (v1 bootstrapping note: before any commit has that history, fall back to last lint-green, marked interim) | No new task-lifecycle states — the change is entirely in *which* instructions the Orchestrator/Reviewer load |

## Consistency

| Boundary | Model | Why |
|----------|-------|-----|
| `review-evidence-check` verdict | Strong, SHA-bound | Single synchronous job; evidence is tied to `commit_id == current head SHA` via the Reviews API, so there is no window where stale evidence from an earlier commit satisfies a later, different commit |
| `frozen-skill-snapshot` vs. live target worktree (Track A) | Strong, by construction | The snapshot is pinned once at run start and never re-read; the Builder's live edits to the same paths in the target worktree are invisible to the Orchestrator/Reviewer roles for the duration of that run |
| Run-log append/verify (Track A) | Unchanged | Already documented in `run-log.md`; not redesigned here; explicitly **not** a consistency boundary Track B depends on |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `check_review_evidence.py` run | Yes — same PR head SHA + same Reviews-API state always produces the same verdict; a rerun mutates no state | None needed |
| `review-evidence-post`'s classify-then-approve/no-op (Track B) | Yes — re-running against an unchanged head and unchanged verdict produces the same review state; GitHub deduplicates identical reviews from the same actor; `concurrency: cancel-in-progress` means only the latest push's run ever completes, so there's nothing stale to deduplicate against in practice | None needed |
| `check_sensitive_path_bypass.py` | Yes — reads merged-PR history, writes an issue only on a new bypass not already tracked (dedupe by PR number in the issue title/label) | None needed |
| `run_log.py append` (Track A) | Unchanged — already idempotent via `--expect-head` and `pending` replay | Reused as-is |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| PRs/month touching `sensitive-path-list` | Measured (architecture review Condition 3): 17 commits/PRs total | `git log --since="1 year ago" --oneline -- docs/sensitive-paths.yaml scripts/install_engine.py skills/loop-task-implementer/scripts/run_log.py skills/pr-gatekeeper/scripts/idempotency_store.py` run 2026-09-24, against the seed `globs` list Phase 0 actually ships — 17 commits (PRs #216, #259, #268, #279, #280, #282, #284, #285, #287, #289, #291, #292, #293, #294, #295, #296, #297), spanning 2026-09-09 to 2026-09-24. That span is these files' entire history, not a one-year window — the repository is new enough that `--since="1 year ago"` returns everything. This is a concentrated initial-build burst (the install-engine lock/signal rewrite itself, plus run_log.py's own hardening rounds), not a steady-state rate; extrapolating it linearly (≈34 PRs/month) would overstate future volume once that rewrite settles. Confirms the mechanism's scope is proportionate to commit, not to blocking a high-throughput path — matches this review's own "not a blocking gap" framing, now with a number behind it instead of "not computed" |
| `review-evidence-check`/`review-evidence-post` combined runtime | Open question | Expect low seconds to low minutes depending on the review pass's depth; not measured. `review-evidence-post`'s classification step only does real work on same-repo, non-cancelled triggering runs (and its underlying review pass only runs on PRs `sensitive_path_match` flags) — trigger volume is bounded by push count via `concurrency: cancel-in-progress`, not total PR count |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| `gh`/GitHub API unavailable or errors during `check_review_evidence.py` | Fail closed (exit `2`, required check stays red) — same doctrine `run_log.py` already documents |
| Malformed or empty `docs/sensitive-paths.yaml` | Fail closed (exit `2`, treated as "cannot determine"), never silently "nothing is sensitive" |
| No clean prior eligible commit to pin `frozen-skill-snapshot` to (Track A) | `ESCALATE`, do not fall back to live (possibly-mid-edit) instructions |
| `sensitive-path-list`, or the enforcement mechanism itself (`review-evidence.yml`, `check_review_evidence.py`, `check_sensitive_path_bypass.py`), is edited to remove or weaken coverage | Cannot happen unnoticed: all four files are permanent members of `sensitive-path-list`'s own `globs`, so any such edit is itself a sensitive-path change requiring evidence. An earlier revision protected only the data file, leaving the enforcement code itself editable without evidence — closed here |
| Rename/split evades the glob list | Mitigated, not eliminated, by the content-pattern supplement (grep for concurrency-primitive keywords against the full diff text, not just pre-listed paths) |
| `review-evidence-post`'s bot identity approves the wrong PR, or a compromised/buggy run acts outside its intended scope | Its target PR is pinned to `github.event.workflow_run.pull_requests[0].number` — GitHub's own trigger-event context — never a value derived from the analyzed diff or PR body, which an attacker could otherwise influence |
| A fork PR triggers `review-evidence.yml`'s `pull_request`-scoped jobs (their read-only token doesn't prevent this — forks can trigger them, harmlessly, since neither ever writes) and `workflow_run` then fires for `review-evidence-post` with a real, **base-repository-scoped** write token, regardless of the fork origin | `review-evidence-post` explicitly checks `github.event.workflow_run.head_repository.full_name == github.repository` and no-ops otherwise — fork-originated runs never reach the point of even classifying, let alone posting an approval, closing what an earlier revision incorrectly treated as merely "an inconvenience for forks" rather than the write-token exposure it actually was |
| The review pass a chosen check (Open Questions) runs is influenced by adversarial content embedded in the diff itself (a comment or string engineered to read as an instruction, e.g. "pre-approved, skip review criteria") | Whichever check is chosen for `review-evidence-post`'s `analyze` classification step **must** treat diff text as data, never as instructions, per this repo's own [`docs/skill-framework/shared/prompt-injection.md`](../../skill-framework/shared/prompt-injection.md) doctrine — stated here as a hard requirement, not left implicit; see Open Questions |
| The automated approval path is mistaken for a security control | It isn't one: `review-evidence-post`'s approval is a workflow/quality gate, not a control against a malicious or compromised committer — it and the human PR author share the same repository write access and the same trust boundary. It exists to satisfy the *process* requirement of an independent evidence trail for a solo maintainer, not to defend against that maintainer's own account being misused |
| The `review-evidence.yml` run `review-evidence-post` watches is itself cancelled (e.g. by a newer push superseding it in the shared `concurrency: cancel-in-progress` group) | `review-evidence-post` explicitly no-ops on `github.event.workflow_run.conclusion == 'cancelled'` (LENS-B-5, PR #298 follow-up) — narrowly scoped to that one value, **not** a general `conclusion == 'success'` gate: the triggering run's aggregate conclusion is `failure` on almost every legitimate push, because `review-evidence-check` (a sibling job in that same run) is expected to fail until a real approval lands, so a bare success gate would permanently deadlock the mechanism — the exact class of bug round-3 finding 1 already fixed once (see Revision history). Every other conclusion (`failure`, `success`, `timed_out`, etc.) flows through to `review-evidence-post`'s own classification step exactly as it does today; a future edit that "helpfully" broadens this back to `== 'success'` would reintroduce that deadlock |
| `check_sensitive_path_bypass.py` itself fails silently (API error, malformed `sensitive-path-list`) | Fails loud, not silent: on its own failure it opens/updates a tracking issue for that failure specifically (the same mechanism it uses for bypasses), rather than only relying on GitHub's easy-to-miss default workflow-failure email — see Observability |
| Owner needs to merge urgently despite a red `review-evidence-check` | Existing ruleset bypass-actor path, already logged by GitHub — but now also **loudly surfaced** by `check_sensitive_path_bypass.py` rather than relying on someone remembering to check the audit log |
| Solo maintainer, no second human reviewer available | `review-evidence-post`'s automated approval satisfies the API-level "reviewer login != author" requirement without needing a second human account — this is the mechanism that makes Track B viable standalone |
| Fork PR (no external contributors today, but noted) | `review-evidence-post`'s write step can't run against a fork PR under the default token; accepted gap for v1, see APIs table |
| `scripts/check_review_evidence.py` does not exist at the checked-out ref (bootstrap case: a PR — including the one introducing this script — whose base commit predates the script's own introduction, or a `workflow_run` firing against a default-branch tip that likewise predates it) | Clean, intentional skip, not a crash and not a silent pass-as-if-approved: both `review-evidence-check`'s and `review-evidence-post`'s enforcement steps guard the `python3 scripts/check_review_evidence.py ...` invocation with a presence check and exit `0` with an explicit message ("does not exist at this base commit -- the review-evidence gate has not been adopted here yet; nothing to enforce") if the script is absent. Scoped narrowly to this one condition — every other failure mode (malformed sensitive-path list, `gh`/API errors, an actual non-`approve` verdict) still fails closed exactly as the rows above |

## Observability

| Signal | What's measured | Mechanism |
|--------|-------------------|-----------|
| `review-evidence-check` pass/fail rate | How often sensitive-path PRs actually carry evidence | GitHub's own PR check history — no new dashboard needed for a solo-maintainer repo |
| Sensitive-path bypasses | Merges that skipped the check via the ruleset override | `check_sensitive_path_bypass.py`'s tracking issues — this is the loud, automatic version of what was previously a passive "check the log" note |
| `check_sensitive_path_bypass.py`'s own health | Whether the weekly scan itself ran and completed | Its own failure opens a tracking issue too, not just GitHub's default workflow-failure email — the alerter alerts on itself |
| `run_log.py verify`/`summarize` output for self-hosted runs (Track A) | Reused as-is; already the audit surface for any `loop-task-implementer` run | Existing |

## Rollout plan

Sequenced precisely, because editing `docs/github-ruleset-main.json` alone does **nothing** to the live
ruleset — it's a verify-only mirror, and the live GitHub branch-protection ruleset can only be changed by
the repo admin through the GitHub Settings UI (or `gh api ... PUT`), never from CI (see Existing system
context, above). Getting the order wrong risks the classic "required check with zero runs against open
PRs" footgun, which can permanently block merge on anything already in flight at cutover.

| Phase | Scope | Steps |
|-------|-------|----------------------------------|
| 0 | Author the new pieces, land them **un-required** | Write `docs/sensitive-paths.yaml`, seeded with: `scripts/install_engine.py`, `skills/loop-task-implementer/scripts/run_log.py`, `skills/pr-gatekeeper/scripts/idempotency_store.py` (already flagged as a matching crash-safety gap in gap-reanalysis finding F4), any `skills/*/scripts/*lock*` \| `*signal*` \| `*idempotency*`, **and its own enforcement mechanism** — `docs/sensitive-paths.yaml` itself, `.github/workflows/review-evidence.yml`, `.github/workflows/review-evidence-post.yml`, `scripts/check_review_evidence.py`, `scripts/check_sensitive_path_bypass.py`. Write `scripts/check_review_evidence.py` (`check`/`analyze` subcommands), `.github/workflows/review-evidence.yml` (`review-evidence-check`, `check-sensitive-path-bypass` jobs) and the sibling `.github/workflows/review-evidence-post.yml` (`review-evidence-post` job, necessarily a separate file — GitHub rejects a `workflow_run` trigger that watches its own workflow), `scripts/check_sensitive_path_bypass.py`. **Provision `review-evidence-post`'s bot credential** (a PAT or GitHub App installation scoped to `pull-requests: write` only) — nothing upstream of this exists yet. Merge these normally, with the new workflows present but *not yet* in the ruleset's required-checks list |
| 1 | Let it run un-required on live PRs, and **smoke-test the full async chain, not just its pieces** | Open a real test PR touching a sensitive path and confirm, **without any manual re-run or extra push**, that: `review-evidence-post` independently re-derives a sensitive-PR verdict from its own base-pinned checkout and successfully posts an `APPROVED` review under the bot identity, and `review-evidence-check`'s status context **turns green on its own** via the `pull_request_review` trigger once that review lands. Two distinct failure modes to rule out here, not one: (a) an unprovisioned or misscoped bot credential, which makes every run fail the same way a broken check would; (b) `review-evidence-check` never re-evaluating after a legitimate approval, which a smoke test that relies on a manual re-run to "pass" would silently mask instead of catching |
| 2 | Require any open PRs to sync with base | So no in-flight PR is stuck with zero runs of the new check once it becomes required |
| 3 | Make it required | Edit `docs/github-ruleset-main.json`'s required-status-checks list (the doc-of-record change), then the repo admin applies the equivalent change to the *live* ruleset via GitHub Settings UI (or `gh api ... PUT`) — manual, by design, never CI. Run `make verify-github-ruleset` to confirm live matches doc |
| 4 | Ships independent of decision #6 | Phases 0–3 need no self-hosting and no Track A — this is the cheap, immediate stopgap that directly closes the gap #289 exposed |
| 5 (only if the owner later chooses Track A) | Pilot self-hosting on a **low-risk** change first (a docs-only or single-test-file PR), not on `install_engine.py`/`run_log.py` directly, on a POSIX runner (F2: native Windows can't run it) | Validates `frozen-skill-snapshot` resolution and the `WORKTREE` isolation primitive before betting a sensitive-path PR on it |
| 6 (only if Track A's pilot holds) | Extend to sensitive-path PRs; keep `review-evidence-check` permanently, even after Track A is adopted | Defense in depth — `frozen-skill-snapshot`'s eligibility can then tighten to "last commit whose PR passed `review-evidence-check`" |

## Open questions

- Decision #6 itself (adopt Track A, on what timeline) — owner decision, out of scope for this spec, routed to `engineering-decision-discovery`. Track B no longer waits on it.
- Historical PR volume against `sensitive-path-list`, to size how often the gate would actually fire (Capacity).
- What `review-evidence-post`'s `analyze` classification step's underlying review pass actually is — this repo's own `pr-review`/`code-review` skill run against the diff text, or a narrower purpose-built check scoped to concurrency/crash-safety patterns specifically. A narrower check is cheaper, lower false-positive-risk, and cheaper to re-run per push for a v1; the full skill is more thorough but heavier — and matters more now that `concurrency: cancel-in-progress` means only the latest push's run survives per PR, so cost scales with push count, not with how many runs pile up. **Hard requirement either way** (see Failure strategy): whichever is chosen must treat the diff text it reads as data, never instructions, per `docs/skill-framework/shared/prompt-injection.md` — `pr-review` is already a wired consumer of that doctrine; a narrower custom check would need to state its own compliance explicitly, since it isn't in that doctrine's existing wiring table.
- Whether a GitHub App identity (vs. a bot user PAT) is the better `review-evidence-post` credential — a PAT constitutes a "new secret" the design otherwise avoids; a GitHub App install doesn't, at the cost of more setup.
- Extra authorship scrutiny for `check_review_evidence.py`'s own `check`/`analyze` review logic at Phase 0, before the gate exists to cover them — the same 0-review bar every commit merges under today, now more consequential since a bug here silently weakens the gate being built. Not a blocking gap, worth a maintainer's own deliberate second look rather than the usual pace.

## Revision history

**2026-09-24, after three-persona adversarial review (Security Architect, SRE, Software Architect):**
seven real findings closed, none cosmetic:

1. **(Security, Architect — independently) Fatal:** the original design bound Track B's primary evidence
   path to a `run_id`/`chain_head` citation "matching a `verify`-able log," but the run log lives outside
   any git repository on the maintainer's local machine by explicit design — a GitHub Actions runner
   structurally cannot reach it. **Fixed** by moving Track B's load-bearing evidence entirely onto the
   GitHub Reviews API (verifiable, SHA-bound, needs no new infrastructure) and demoting the run-log
   citation to optional human-readable context, never something the automated gate checks.
2. **(Security) Critical:** a free-text `Reviewed-by:` trailer in the PR body was forgeable by anyone with
   a second account. **Fixed** by requiring a real `APPROVED` review via the Reviews API instead.
3. **(Security) Critical:** evidence wasn't bound to the PR's current head SHA, so stale evidence from an
   earlier commit could satisfy a later, different (possibly malicious) commit. **Fixed** by requiring the
   review's `commit_id` equal the current head SHA.
4. **(Security) High:** glob-only path matching could be evaded by renaming or splitting sensitive code.
   **Fixed** by adding a content-pattern supplement that greps all changed files for concurrency-primitive
   keywords, independent of which file they land in.
5. **(Architect) High, undercut the design's own framing:** the original "these are independent
   alternatives, ship B regardless" claim was false — Track B's only solo-maintainer-viable path silently
   required Track A's self-hosting mechanism to produce meaningful evidence. **Fixed** by the `review-bot`
   automated-approval mechanism, which needs neither a second human nor a self-hosted run, restoring true
   independence.
6. **(SRE) Blocks-rollout:** the original Rollout Phase 1 conflated "edit the doc" with "activate the
   gate," missing the workflow file itself, the manual live-ruleset-apply step, and the cold-start
   footgun of requiring a check with no prior runs. **Fixed** with an explicit six-phase sequence.
7. **(Security) Medium, and SRE's passive-bypass-detection finding — same shape:** bypasses were only
   detectable by manually checking GitHub's audit log. **Fixed** with `check_sensitive_path_bypass.py`, a
   scheduled job that files a tracking issue automatically.

Also folded in: SRE's missing-`permissions`-block finding (now specified per job), Architect's
malformed-list-should-fail-closed finding (now an explicit Failure-strategy row), Architect's
document-convention gap (this file now carries **Date**/**Status**/**Source**, matching sibling specs),
and the F2 (POSIX-only `run_log.py`)/F4 (`pr-gatekeeper`'s `idempotency_store.py`) cross-references the
Architect flagged as handled unevenly.

**2026-09-24, round 2, after a second three-persona adversarial review of the round-1 rewrite:** one
Critical, closed by a structural split; six smaller findings, all closed:

1. **(Security, Architect — independently) Critical:** the single `review-bot` job held a
   `pull-requests: write` token while its review pass ran against PR content. If that review pass ever
   checked out and executed anything from the PR branch (even ostensibly read-only tooling), the token
   was exposed to attacker-controlled code — a full gate bypass via exfiltration or direct self-approval,
   independent of what the review concluded. Separately, nothing pinned which PR the bot's write-scoped
   token acted on. **Fixed** by splitting the single job into `review-evidence-analyze` (read-only,
   `pull-requests: read`, consumes diff text via the API, never a checkout, produces a verdict artifact)
   and `review-evidence-post` (write-only, triggered by `workflow_run`, posts the review, pins its target
   PR to the trigger event's own `pull_requests[0].number` rather than any value derivable from PR
   content). No job ever holds a write token anywhere near PR-branch code.
2. **(Security, Architect — independently) High:** the self-protecting scope only covered
   `docs/sensitive-paths.yaml` itself, leaving the enforcement mechanism (`review-evidence.yml`,
   `check_review_evidence.py`, `check_sensitive_path_bypass.py`) editable without triggering its own
   gate — a single PR could weaken the check's logic while introducing the vulnerable code it should have
   caught. **Fixed** by adding all three enforcement files to the seed `globs` alongside the data file.
3. **(SRE) Degrades-reliability, blocks accurate rollout validation:** the rollout plan never provisioned
   `review-evidence-post`'s bot credential, so Phase 1's "confirm the check works on live PRs" couldn't
   distinguish a working check with no evidence yet from a structurally broken one (auth failure looks
   identical to "no APPROVED review found"). **Fixed** with an explicit Phase 0 credential-provisioning
   step and a Phase 1 smoke-test PR that exercises a real bot approval before requiring the check.
4. **(SRE) Degrades-reliability:** `check_sensitive_path_bypass.py`, which exists to loudly surface
   silent gaps, had no coverage for its own silent failure — the same "who alerts on the alerter" problem
   one layer up. **Fixed**: it now opens a tracking issue on its own failure too, and Observability gained
   a row for its health specifically.
5. **(Security) Medium, documentation gap:** the design implied automated approval was a meaningful
   independent check without stating what it explicitly is not — a control against the repository owner
   or anyone sharing that access. **Fixed** with an explicit Failure-strategy row naming the trust
   boundary the mechanism does and doesn't cross.
6. **(Architect) Real, implementation-blocking ambiguity:** "grep across all changed files" never said
   what text the grep actually ran against — diff hunks or full file content, via what call. **Fixed** by
   specifying `gh pr diff <n>`'s full patch text as the one data source for both the file-list extraction
   and the content-pattern match, which also closes finding 1 above (no checkout needed for either).
7. **(Architect) Category confusion in the document header:** `**Status:**` had been set to the same
   value as the `Readiness:` verdict, which are different fields in this repo's spec conventions (Status
   = approval/implementation state; Readiness = the `system-design` skill's own template verdict).
   **Fixed**: `Status: Proposed`, with a one-line per-track Readiness note added since Track B and Track A
   are no longer equally contingent on the open owner decision.

Also folded in: SRE's `concurrency: cancel-in-progress` finding (prevents overlapping runs from rapid
pushes, and reduces cost at PR-iteration volume without needing a separate debounce mechanism) and
Architect's `pull-requests: write` wording fix (Components/state-machine tables now say "never writes
repository contents," not the broader and slightly misleading "read-only dispatch").

**2026-09-24, round 3, after a third three-persona adversarial review focused on the round-2 split:**
one finding that meant the mechanism, as previously specified, could never actually complete on its own
(found independently by two reviewers), one real bypass reclassification, and six smaller findings — all
closed:

1. **(Security, SRE — independently) Critical, functionally breaks the mechanism:** `review-evidence-check`
   triggered only on `pull_request`, evaluating synchronously at push time — before the async
   `analyze -> artifact -> workflow_run -> post` chain had any chance to complete. It correctly found no
   approval yet, failed, and nothing ever re-evaluated it afterward. The required check would sit
   permanently red on every SHA, for both the human-review and bot-approval paths, until a manual re-run
   or a new push — defeating the design's entire purpose. **Fixed** by adding `pull_request_review:
   [submitted]` as a second trigger, so a landed approval (human or bot) actually flips the check green.
2. **(Security) High, reclassifies a documented "limitation" as an actual bypass:** the design had
   claimed fork PRs "can't get an automated approval without a PAT or App install" — this is backwards.
   `workflow_run` runs with **base-repository** token permissions regardless of whether the triggering run
   was fork-originated; the fork restriction only applies to the `pull_request`-triggered job, not the one
   that actually posts the write. Without an explicit gate, a fork PR could have obtained a real
   write-scoped auto-approval through the default token alone — combined with finding 6 below (prompt
   injection), a live bypass, not a documented inconvenience. **Fixed** by explicitly gating
   `review-evidence-post` on `github.event.workflow_run.head_repository.full_name == github.repository`.
3. **(Security) Medium-High, implementation-blocking ambiguity of the same shape round 2 already fixed
   for the content-pattern grep source, but not applied here:** the artifact handoff between the two new
   jobs was never specified precisely — no stated `run-id` pinning, risking a wrong-run's artifact being
   consumed; no stated `actions: read` permission, which cross-run artifact download actually needs (the
   design had scoped `review-evidence-post` to `pull-requests: write` only, which cannot fetch an
   artifact at all). **Fixed** by naming the exact `actions/download-artifact@v4` call with `run-id:
   github.event.workflow_run.id` and adding `actions: read` to the job's permissions.
4. **(SRE) Medium, produces noisy failed runs instead of a clean no-op:** a cancelled `review-evidence-analyze`
   run (from the same `concurrency: cancel-in-progress` group that fixed a round-2 finding) still fires a
   `workflow_run` `completed` event with `conclusion: cancelled` — nothing gated `review-evidence-post` on
   `conclusion == 'success'`, so it would attempt to download a nonexistent artifact and fail loudly
   rather than skip cleanly. **Fixed** with an explicit conclusion guard.
5. **(SRE) High, a round-2 mitigation could have hidden finding 1:** the round-2 smoke-test step only
   asked to "confirm the check reflects" the approval — satisfiable by a tester manually re-running the
   check to force it green, which would make the smoke test pass while masking the exact bug in finding 1.
   **Fixed** by requiring the smoke test to observe the check turn green from the async chain alone, with
   no manual re-run or extra push.
6. **(Security) High, genuinely new risk category not previously considered:** nothing required
   `review-evidence-analyze`'s underlying review pass to treat PR diff text as untrusted data rather than
   instructions — if the eventually-chosen check is LLM-backed (still an open question), adversarial text
   embedded in the diff (a comment reading like a system instruction) could manipulate the verdict
   directly. **Fixed** by making compliance with this repo's own `docs/skill-framework/shared/prompt-injection.md`
   doctrine an explicit hard requirement in Failure strategy and Open Questions, for whichever check is
   chosen.
7. **(Architect) Real ambiguity with two bad readings, undermining the "targeted mechanism" framing:**
   the spec never said whether `review-evidence-analyze`/`-post` ran unconditionally on every PR (noisy,
   and directly undercuts the "cheap stopgap" framing since the review pass would then run on 100% of PR
   volume) or independently re-derived sensitivity in a second place from `check_review_evidence.py`
   (a duplicated-logic drift risk). **Fixed** by introducing `sensitive_path_match` as a single shared
   module both consume, and having `-analyze` exit immediately, doing nothing further, on a non-sensitive
   PR.
8. **(Architect) Real, same-commit staleness distinct from what round 1 already fixed for cross-commit
   staleness:** the Reviews API returns every historical review, not one per reviewer — an "any entry
   matches" check would accept a stale `APPROVED` from a reviewer who later left `CHANGES_REQUESTED` at
   the *same* commit. **Fixed** by requiring the most recent review per `user.login` at the head SHA,
   not merely any matching entry.

**2026-09-24, PR #298 implementation + independent-review remediation (LENS-A-1):** the round-3 design
above shipped as three jobs (`review-evidence-check`, `review-evidence-analyze`, `review-evidence-post`)
across a single `review-evidence.yml` file, plus a `workflow_run`-triggered `review-evidence-post`. Two
isolated-lens review generations against the implementation caught one Critical: `review-evidence-analyze`
was a `pull_request`-triggered job, and GitHub Actions resolves a `pull_request`-triggered job's *step
definitions* — not just the ref a checkout step inside it happens to request — from the PR's own
head/merge ref. A same-repo PR (no fork needed) could therefore edit `review-evidence-analyze`'s steps in
the very PR being evaluated and have a forged "classify and write a verdict" step run instead of the real
one; the old `review-evidence-post` only checked that run's conclusion was `success` and that the
artifact's self-reported `pr_number` matched, neither of which requires the artifact to have come from
real analysis. Net effect: any same-repo PR could forge a real, bot-issued APPROVED review with zero
actual review. **Fixed** by deleting `review-evidence-analyze` entirely and moving its `check_review_evidence.py
analyze` logic into a step `review-evidence-post` runs itself, against its own base-pinned checkout
(`workflow_run`'s default `GITHUB_SHA` is always the default branch's tip, never a PR ref) — `review-evidence-post`
now recomputes its verdict independently instead of trusting one written by a job a PR author could
influence. This also meant `review-evidence-post` could no longer live in `review-evidence.yml` alongside
`review-evidence-check`: a `workflow_run` trigger cannot watch its own workflow's completion (GitHub
rejects this outright, HTTP 422, invalidating the whole file), so `review-evidence-post` moved to its own
sibling file, `.github/workflows/review-evidence-post.yml`. A separate follow-up commit in the same PR
fixed a bootstrap crash (the checker script doesn't exist on `main` until the PR itself lands, so a raw
file-not-found now exits cleanly). Merged to `main` at `8d6d1a9` (PR #298); Phase 0 is live, un-required.
Two non-blocking findings from that PR's own independent review were deferred rather than fixed inline:
this document's Components/APIs/Failure-strategy/Rollout tables above still described the now-deleted
`review-evidence-analyze` job (**LENS-B-4**, closed by this correction pass — see this document's diff for
PR against `main` in the `claude/f1-review-evidence-gate-followups` branch); and `review-evidence-post` had
no gate at all on `github.event.workflow_run.conclusion`, so a `cancelled` triggering run (the common case
when a rapid second push cancels the first push's `review-evidence.yml` run via the shared
`concurrency: cancel-in-progress` group) still spun up a full job instead of a clean no-op — wasted CI
minutes and log noise, no correctness or security impact (**LENS-B-5**, closed in the same follow-up by
adding a guard scoped *only* to `conclusion == 'cancelled'`, deliberately not a general
`conclusion == 'success'` gate — see the Components, APIs, and Failure-strategy rows above for why a
bare success gate would reintroduce the round-3 finding-1 deadlock).
