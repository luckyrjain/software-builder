# Architecture review — F1 review-evidence gate (Track B)

**Decision: Approved with conditions**

**2026-09-24.** Source design: [2026-09-24-f1-review-evidence-gate-design.md](2026-09-24-f1-review-evidence-gate-design.md)
(`SYSTEM_DESIGN_SPEC.md`, Track B only — Track A is explicitly out of scope pending owner decision #6).
Ticket: [2026-09-24-autonomous-engineer-gap-reanalysis.md](../plans/2026-09-24-autonomous-engineer-gap-reanalysis.md), F1.

Sound overall — three rounds of adversarial review (Security Architect, SRE, Software Architect) already
closed 23 real findings, including two that were structurally load-bearing (the original evidence path
was unimplementable from CI; the mechanism as specified could never actually complete on its own). Three
conditions remain before implementation starts, none of them a redesign: an explicit acceptance
criterion for the prompt-injection requirement the design already states but doesn't yet enforce, a
monitoring gap for the bot credential's own health, and a cheap sanity check on the unmeasured capacity
numbers.

## Architecture decision

A required GitHub Actions status check, `review-evidence-check`, blocks merge on any PR touching a
declared sensitive-path list (`docs/sensitive-paths.yaml`) unless the GitHub Reviews API shows the most
recent review per `user.login`, at the PR's current head SHA, as `APPROVED` from a login other than the
author. Satisfiable two ways: a genuine second human reviewer, or an automated `review-evidence-analyze`
(read-only, consumes the PR diff via the API, never a checkout) / `review-evidence-post` (write-scoped,
triggered by `workflow_run`, posts the approval) pair that lets a solo maintainer self-satisfy the
requirement without a second human account. Motivation: PRs #285, #288–290, #292, #293, #295–297 (the
install-engine lock/signal rewrite) merged with `required_approving_review_count: 0` and no independent
review evidence; #289 shipped a lock-concurrency regression caught only by later ad hoc review. This
closes that specific gap — a real regression that reached `main` unreviewed — with a mechanism that
doesn't require a second human account, since the repository has exactly one maintainer.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| The prompt-injection-resistance requirement for `review-evidence-analyze`'s review pass is stated in prose (design's Failure strategy and Open Questions) but not yet an enforced acceptance criterion — the "which check" decision is still open, and the more thorough option (`pr-review`, LLM-backed) is exactly the one exposed to this risk | Security | Conditional | See Conditions §1 |
| No monitoring signal for the bot credential's (PAT/App) own health — an expired or revoked credential degrades safely (fails closed, the human-review path still works) but silently, which for a low-PR-volume solo-maintainer repo could go unnoticed for a while | Operability | Conditional | Design's Observability section (lines 133–140) lists four signals, none covering credential health |
| Capacity (PR volume against the sensitive-path list, job runtime) is explicitly unmeasured | Scale limits | Informational | Design itself records this as an open question rather than inventing a number — correct per this review's own rules, and low-risk given the domain (see Scale limits below) |
| None found beyond the above | Failure modes | — | The design's own Failure-strategy table (12 rows) already covers fail-closed API/list/snapshot handling, self-protection of the enforcement mechanism, rename evasion, wrong-PR targeting, fork-token exposure, cancelled-run cleanup, and the alerter alerting on itself — unusually thorough for a spec this size, a direct product of three review rounds specifically hunting these |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| PRs/month touching `sensitive-path-list` | Unknown — not measured | Design's own Capacity section: "No historical PR-volume data supplied; derivable post-hoc from `git log --since=... -- <globs>` but not computed for this spec" |
| `review-evidence-check`/`-analyze`/`-post` combined runtime | Unknown — not measured | Design's own Capacity section: "Expect low seconds to low minutes... not measured" |
| GitHub Actions minutes consumed | Not a realistic constraint at this repo's scale | `review-evidence-analyze` exits immediately on a non-sensitive PR (design, Components: `sensitive_path_match` gates it) — the review pass only ever runs on the subset of PRs that touch sensitive paths, which per the repo's own recent history (a handful of PRs across the install-engine rewrite) is small |

Neither unmeasured dimension is treated by this review as a blocking gap: this is a solo-maintainer,
public-but-low-traffic repository closing a specific, already-observed regression class, not a
high-throughput system where an unmeasured load dimension risks silent failure at scale. See Conditions §3
for a cheap way to close the gap anyway before Phase 0.

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| `gh`/GitHub API errors during `check_review_evidence.py` | Exit `2` | Fail closed, required check stays red | Design, Failure strategy row 1 |
| Malformed/empty `sensitive-path-list` | Exit `2` | Fail closed, never silently "nothing is sensitive" | Design, Failure strategy row 2 |
| A PR simultaneously weakens the enforcement mechanism and introduces the code it should have caught | The enforcement files are permanent members of the list's own `globs` | Editing them is itself a sensitive-path change requiring evidence | Design, Failure strategy row 4 (round-2 fix) |
| Rename/split evades glob matching | Content-pattern supplement greps the full diff text | Mitigated, not eliminated (stated as such, not overclaimed) | Design, Failure strategy row 5 |
| Fork PR obtains a write-scoped auto-approval via `workflow_run`'s base-repo token | `head_repository.full_name == github.repository` gate | Fork-originated runs never reach the approval step | Design, Failure strategy row 6 (round-3 fix — the original spec had this backwards) |
| `review-evidence-analyze` times out, errors, or is cancelled by a newer push | `workflow_run` `conclusion != success` filtered by `review-evidence-post`'s own trigger | Clean no-op, not a failed download or default-approve | Design, Failure strategy row 9 (round-3 fix) |
| `check_sensitive_path_bypass.py` itself fails | Opens a tracking issue on its own failure | Same mechanism it uses for bypasses | Design, Failure strategy row 10 (round-2 fix — closes "who alerts on the alerter") |
| **Bot credential (PAT/App) expires or is revoked** | **Unknown — no stated signal** | Degrades safely (fails closed; a human can still review and approve manually) but the design names no way to notice this happened, beyond an Actions job failure a maintainer would have to be watching for | Real, minor gap — see Conditions §2 |
| Owner needs to merge urgently despite a red check | Ruleset bypass-actor path | Now loudly surfaced by `check_sensitive_path_bypass.py`, not just the audit log | Design, Failure strategy row 11 |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| PR diff text crosses into `review-evidence-analyze` | Untrusted (any PR author) -> a job with `pull-requests: read` only, no checkout | None — the job cannot write anywhere, cannot execute the content it reads | Round-2 fix; the design is explicit the diff is "consumed as text data," never executed |
| Write-scoped token (`pull-requests: write` + `actions: read`) in `review-evidence-post` | Base-repo-scoped, never exposed near PR-branch content (separate job, separate trigger) | Bounded to posting a PR review; no `contents: write`, cannot merge, cannot edit code | Round-2 split closed the original single-job token-exposure risk |
| Fork-originated `workflow_run` completions | Explicitly gated out (`head_repository.full_name == github.repository`) | None for forks — the repo has no external contributors today, and the gate makes that explicit rather than accidental | Round-3 fix; the original spec's claim here was backwards and the design's revision history says so plainly |
| Prompt injection into `review-evidence-analyze`'s verdict, if the chosen check is LLM-backed | Diff text -> an LLM-backed review pass (if `pr-review`/`code-review` is chosen over a narrower static check — still an open question) | A manipulated verdict could flip `approve`, defeating the gate's purpose for that one PR | **Stated as a hard requirement in the design (Failure strategy, Open Questions), but not yet an enforced or tested property** — see Conditions §1. This is the one place the design's own rigor (three rounds) hasn't yet closed the loop from "must" to "verified" |
| `review-evidence-post`'s approval mistaken for a control against the repo owner/a malicious committer | N/A — same trust boundary | N/A | Design explicitly disclaims this (Failure strategy row: "It isn't one... it and the human PR author share the same repository write access and the same trust boundary") — correct framing, not overclaiming what the mechanism defends against |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Who runs this | Repo owner (`@luckyrjain`), stated throughout the design and existing `CODEOWNERS` | New Actions job (bounded to sensitive-PR volume, see Scale limits); one new credential to provision once (Phase 0) | No named team beyond the single maintainer — appropriate for a solo-maintainer repo, not a gap |
| Bot credential lifecycle | Repo owner | **Unknown — no rotation/expiry-monitoring signal stated** | See Conditions §2; PATs expire, App installs can be revoked, and the design's four Observability signals (pass/fail rate, bypasses, bypass-alerter's own health, run-log verify output) don't cover this |
| Ruleset changes (adding `review-evidence-check` as required) | Repo owner, manual GitHub UI step | One-time, already correctly sequenced in Rollout (design's own finding from round-1/round-2 review — editing the doc alone does nothing to the live ruleset) | No gap — the design already treats this precisely |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| Track A — self-host `loop-task-implementer` on software-builder's own repository | Not rejected, but out of scope for this review: a separate owner decision (#6), with its own design (`frozen-skill-snapshot`) already produced in the same spec | Design, Scope note and Components |
| A `run_id`/`chain_head` citation to the local run log as CI-verifiable evidence | The run log lives outside any git repository by explicit design; a GitHub Actions runner structurally cannot reach it | Design, Revision history round 1, finding 1 — a genuinely fatal flaw in the first draft, caught and fixed |
| A free-text `Reviewed-by:` trailer in the PR body | Forgeable by anyone with a second account, not bound to the current commit | Design, Revision history round 1, findings 2–3 |
| A single `review-bot` job holding both the review pass and the write-scoped approval token | Exposed the write token to PR content if the review pass ever executed anything from the branch | Design, Revision history round 2, finding 1 — split into `review-evidence-analyze`/`review-evidence-post` |
| Native GitHub `required_approving_review_count >= 1` | Doesn't work on a true solo-maintainer repo — GitHub blocks self-approval, and there's no second human account | Design's Failure strategy: "this is why Track B doesn't turn on native required-review" |

## Conditions

1. **Turn the prompt-injection-resistance requirement into a verified acceptance criterion, not just a
   stated one, before `review-evidence-analyze`'s underlying check ships.** Either (a) choose the
   narrower, non-LLM, purpose-built check for v1 (the design already leans this way — "cheaper, lower
   false-positive-risk... for a v1" — which also sidesteps this risk entirely), or (b) if the
   `pr-review`/`code-review` skill is chosen instead, add an explicit test case with adversarial content
   embedded in a diff (a comment engineered to read as an instruction) and confirm the verdict isn't
   swayed, before Phase 0 is considered complete.
2. **Add a monitoring signal for the bot credential's own health** to the design's Observability section
   — at minimum, have `check_sensitive_path_bypass.py`'s weekly scan (which already alerts on its own
   failure) also check whether `review-evidence-post` has had any successful run in the scan window on a
   PR that needed one, and flag if not. Cheap to add to an already-scheduled job; closes a real, if minor,
   silent-degradation gap for a solo maintainer who won't be watching Actions logs daily.
3. **Before Phase 0, run the one-time `git log --since=... -- <globs>` the design itself already names**
   as the way to size real PR volume against the seed `sensitive-path-list`, and record the result in the
   design's Capacity section. Cheap, and closes the one evidence gap this review found material enough to
   name (though not material enough to block on) — confirms the mechanism's scope is proportionate before
   committing Actions-minutes budget to it.

None of these three block starting Phase 0 (authoring the new files, landing them un-required) — they
gate Phase 0's own completion criteria (condition 3) and the point at which `review-evidence-check`
becomes required in the ruleset (conditions 1–2, since that's when the automated path first has real
consequences for merge-ability).
