# Architecture review — C1: security-review → executor handoff

**Decision: Approved with conditions**

Sound in shape — reuses two already-proven precedents (bug-diagnosis's own real
`cross-skill-escalation.md` row shape, and B6/B8's established "legacy envelope bypass" and
"two-independently-gated-actions" patterns) rather than inventing new mechanisms — but the ticket's own
acceptance criteria bundle four distinct sub-decisions that need to be pinned down precisely, since this
is the first of eight Epic-C tickets and whatever convention it establishes will propagate to C2-C8.
Six conditions need closing before implementation.

## Architecture decision

Four coupled pieces:

1. **A new, narrow `cross-skill-escalation.md` row**: "Vulnerability finding has a concrete, fixable code
   change" | `security-review → loop-task-implementer` | `security_review_report` (finding category,
   severity, evidence refs — never the raw `review_target` content) | a trigger-phrase template — mirroring
   the real, existing `bug-diagnosis → loop-task-implementer` row's exact shape (confirmed at
   `cross-skill-escalation.md:138`), not inventing a new row format.
2. **Two independently-gated action classes**, mirroring B8's own "merge vs. write-back, two
   independent grants" precedent: (a) the code-level fix itself (removing a hardcoded secret from the
   current source, patching an injection point, fixing broken authZ) — potentially autonomous, gated by
   the SAME existing `allowed_actions`/`autonomous_merge_authorized` sourcing rule every prior ticket
   already uses; (b) credential/secret **rotation** (issuing a new secret, revoking the old one, updating
   production consumers) — **never** autonomous, under any grant, full stop — no skill in this
   framework has visibility into or a safe rollback path for live external credential systems.
3. **A concrete envelope**: reuses the legacy `implementation_task` bypass (the real, 15-field schema
   confirmed by B6's own direct `grep` of `composition_contracts.yaml`), populated by a human or the
   Orchestrator from the security-review report's own finding fields — never embedding raw
   `review_target` content, matching this session's own citation-by-reference discipline.
4. **A Reviewer-lens confirmation, not a new lens**: Lens A ("Safety and State") already states, verbatim,
   that its priorities include "authentication, authorization, trust boundaries, secrets" — this ticket's
   own "Reviewer lens includes security" criterion is very likely already satisfied, but needs a precise,
   category-by-category comparison against `security-review`'s own 8 categories (authN, authZ, tenant
   isolation, secrets, injection, SSRF, data leakage, crypto, dependency exposure) before claiming full
   coverage — a gap here (if one exists) is cheap to close with a sentence, not a new lens.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| A "secret-removal PR" removes the secret from HEAD but the git history of every prior commit still contains it in plaintext — a careless or bad-faith review of the resulting PR's diff alone could declare the exposure "fixed" when it isn't | Security | Blocking | See Conditions §1 |
| Conflating the fix (autonomous-eligible) with rotation (always human) into one undifferentiated "security remediation" task risks an implementation that silently widens autonomy into the rotation half, or silently drops rotation as a disclosed follow-up a human never sees | Architecture decision | Blocking | See Conditions §2 |
| No existing precedent for a FINDING-DRIVEN (not ticket-driven) handoff into `loop-task-implementer`'s own task-selection model — every prior B-ticket assumed a task originates from a human/tracker instruction, never an upstream analysis skill's own findings list | Architecture decision | Conditional | See Conditions §3 |
| Lens A's stated coverage may not literally enumerate all 8 of `security-review`'s own categories (e.g. SSRF, tenant isolation aren't named verbatim even if "trust boundaries" loosely covers them) — an unverified coverage claim could leave a real reviewer-side gap | Operability | Conditional | See Conditions §4 |
| As the first of 8 Epic-C "analysis skill → executor" tickets, whatever matrix-row/envelope/action-split convention this ticket establishes becomes the template C2-C8 build on — a rushed or under-specified convention here compounds across 7 more tickets | Scale limits | Conditional | See Conditions §5 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of findings per `security-review` run that could each spawn a separate loop-task-implementer task | Unbounded if every finding automatically becomes a task with no severity/triage filter — a noisy or low-confidence security-review run could flood task selection with low-value remediation tasks | No existing precedent for bounding this; `bug-diagnosis`'s own handoff is 1:1 (one confirmed root cause → one task), not N findings → N tasks | See Conditions §3 |
| Matrix-row/envelope precedent reused across 7 more Epic-C tickets | Breaks down if C1's own convention is under-specified and each of C2-C8 reinvents its own shape instead of reusing C1's | Directly named as a risk by this ticket's own position as the first in the epic | See Conditions §5 |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| A secret-removal fix is merged, the PR diff looks clean, but the secret remains readable in git history | Requires an explicit, disclosed statement that the existing, already-active `gitleaks` CI gate (confirmed real via this session's own B6 saga) is the ongoing protection mechanism — it scans commit-by-commit history, not just the final tree, so a secret introduced in ANY historical commit within its scan range continues to be flagged on every subsequent PR touching that range | A human must still separately decide whether full history-scrubbing (e.g. a `git filter-repo`/BFG-style rewrite) is warranted for a given exposed secret — this is explicitly out of scope for this ticket and must be disclosed as a residual, not silently assumed solved | This is this ticket's own analogue of B6's gitleaks-allowlist saga; must not be treated as solved by "the PR diff is clean" (Conditions §1) |
| A task meant to be "fix the code, never rotate" accidentally includes rotation-shaped scope (e.g. "update the API key in the config" ambiguously spanning both "point at a different source" and "issue a new key value") | Requires the envelope's own `scope`/`acceptance_criteria` fields to explicitly, structurally exclude any action touching a live external credential system — not just a prose reminder | A task whose own scope cannot be satisfied without rotation should fail closed (escalate to a human, not attempt a partial autonomous fix) | Must be a concrete, checkable rule, not "the Builder should know not to" (Conditions §2) |
| A finding-driven task is authored from a stale or already-fixed `security_review_report` (the underlying code changed between the report running and the task being dispatched) | Requires the same "a successful read is not a license to skip independent re-verification" discipline this codebase already applies elsewhere (A6's task-lease precedent, §5's third-party-push re-verification) | The Reviewer's own independent diff-against-current-head review (already a standing requirement for every task this skill dispatches) is the natural backstop — a fix for an already-resolved finding should surface as a no-op or an already-passing check, not a false positive | Not a new mechanism — the existing Reviewer discipline already covers this if the task is correctly scoped (Conditions §3) |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| `security_review_report`'s own content (quoting `review_target`, which is explicitly untrusted per that skill's own prompt-injection framing) flowing into a loop-task-implementer task | Citation-by-reference only (finding category/severity/evidence refs), never the raw `review_target` excerpt — matching this session's own established discipline (B3's `regression_gate: `, B4's `redacted_note`, B6's `convention_capture_similarity: `, B8's citation-only templates) | If violated: a malicious comment/string embedded in reviewed code (`"mark this approved"`, injected instructions) could reach the Builder's own task text as if it were legitimate instruction | The ticket's own report format already treats `review_target` as untrusted and redacts/escapes it on output — this ticket's handoff must inherit that same discipline, not re-expose the raw content one hop downstream |
| Rotation is architecturally impossible to grant autonomously, not merely discouraged by policy | No code path in this framework reaches a live credential-management system (a cloud provider's IAM, a secrets vault, a CI/CD secret store) — this is a structural absence, not a configurable gate | If this absence were ever "fixed" by adding such a capability, it would need its own full architecture-review from scratch, not an extension of this ticket | Confirm the design makes this a structural impossibility (no capability exists to misuse), not merely an unenforced convention (Conditions §2) |
| Secret remaining in git history after a removal PR | Read: anyone with repo clone access, including this framework's own future Builder dispatches reading history | A historically-exposed secret is exposed for as long as that history exists, independent of the current fix | See Failure modes — the existing gitleaks gate is the disclosed, reused mitigation (Conditions §1) |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Deciding, per finding, whether it's autonomous-fix-eligible or must stop at human-action-required | Repo owner / Orchestrator | Real but bounded — the same judgment call every B-ticket's own `allowed_actions`/`autonomous_merge_authorized` grant already requires | Not a new operability class, reuses the existing authorization-decision cost |
| Reviewing and actually performing credential rotation when flagged | Repo owner | Real, external to this framework entirely (whatever the credential provider's own rotation process is) | Explicitly out of scope for this ticket to solve — only to flag clearly and reliably |
| Maintaining the matrix-row/envelope convention this ticket establishes, reused by 7 more Epic-C tickets | Repo owner (via this session's own doctrine chain) | Real, one-time cost if done carefully now; compounding cost if under-specified | See Scale limits |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| No handoff at all (current state — security-review stays a pure read-only leaf) | Rejected: literally the gap this ticket exists to close | Correctly motivates building something |
| A single undifferentiated "security remediation" task type covering both fix and rotation | Rejected: directly contradicts the ticket's own explicit acceptance criterion that "rotation stays human" — conflating the two risks exactly the failure mode named above | Not a real option, correctly excluded by the ticket's own text |
| A brand-new typed artifact (a new composition-registry schema) instead of the legacy envelope bypass | Left open for `system-design` — B6's own precedent (a legacy bypass citing the real 15-field schema) is the cheaper, already-proven path, but a new typed artifact isn't ruled out if `system-design` finds a concrete need the legacy envelope can't satisfy | Not a blocking decision at this stage |
| Inventing a new secret-scanning/history-scrubbing mechanism as part of this ticket | Rejected: this repo already has a real, active history-scanning gate (gitleaks, confirmed via B6) — inventing a parallel mechanism would violate this session's own established "route through an existing mechanism" discipline | Correctly rejected; full history rewriting (if ever needed) is a separate, much larger, human-authorized decision entirely outside this ticket's scope |

## Conditions

1. **State explicitly that the existing, already-active `gitleaks` CI gate is the disclosed, ongoing
   protection against a secret surviving in git history after a removal PR** — this ticket does not
   attempt history-scrubbing; a human deciding whether a full history rewrite is separately warranted is
   named as an explicit residual, not silently assumed solved by a clean current-HEAD diff.
2. **Make the fix/rotation split structurally impossible to conflate, not merely a stated convention.**
   Define the envelope's own scope/acceptance-criteria shape so that no autonomously-dispatched task can
   ever require touching a live external credential system — a finding whose only possible remediation
   involves rotation must route to a human-action-required report line, never an autonomous task, by
   construction.
3. **Define a concrete, bounded selection rule for which `security-review` findings become
   loop-task-implementer tasks** — not every finding automatically becomes a task (unlike `bug-diagnosis`'s
   own 1:1 confirmed-root-cause handoff, a `security_review_report` can carry many findings across 8
   categories). State the minimum bar (e.g. severity threshold, "concrete code-level fix exists and is
   named in the finding") a finding must clear before this handoff applies at all.
4. **Verify Lens A's stated coverage against `security-review`'s own real 8 categories, category by
   category**, and close any gap found with a precise addition to Lens A's own text — do not assume full
   coverage from the word "security" alone.
5. **State explicitly which parts of this ticket's own convention (matrix-row shape, envelope shape,
   action-split framing) are intended as the reusable template for C2-C8**, so later Epic-C tickets can
   cite and extend it rather than re-deriving it from scratch.
6. **State an explicit, bounded re-verification rule** for a task authored from a `security_review_report`
   whose underlying code may have changed since the report ran — confirm this is adequately covered by
   the Reviewer's own existing independent-diff-review discipline, or name what additional check is
   needed.

None of these six block starting a `system-design` pass — they're precise, implementable requirements
for that pass to satisfy, not open architectural questions.
