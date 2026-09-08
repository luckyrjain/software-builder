---
workflow_version: 2.1
phase: 2-3-gate
produces: {posting_decision: string}
consumes:
  required:
    findings: list
    review_metrics: object
    review_evidence: object
    change_identity: object
    inspection_plan: object
    incremental_baseline: object
    head_sha: string
    posting_mode: string
    review_boundary: object
    capability_profile: object
  optional:
    review_target: object
  conditional: {}
---

# Phase 2 → 3 gate (re-run decision)

**Read this file** immediately after Phase 2 evidence finalization, before Phase 3. Evaluate **once** and branch;
Phase 3 must not re-evaluate `head_sha`.

Before any posting decision, require the successful machine validation performed by
`phase-2-evidence.md` using `pr-review/scripts/validate_review_coverage.py`. Then perform a fresh read-only provider/Git
snapshot and rebuild the **current full `change_identity`** using the same canonical procedure as Phase 1→2 coverage:
current base/head/merge-base SHAs, normalized effective-patch fingerprint, changed/generated paths, dependency
changes, and config changes. Do not reuse the Phase 1 identity as the value labelled current. If the required
provider/Git reads cannot establish the current identity, fail closed and skip posting.

When `review_evidence.requirements_ref` is non-null, also re-read the **same authoritative requirements source**
(Jira/MR/PR requirement surface identified by that reference) at this gate and normalize the current
`requirements_ref` again. Do not reuse the Phase 1/2 requirements object as proof that requirements are still
current. If the authoritative source cannot be re-read or normalized, fail closed and skip posting. When stored
`requirements_ref` is null, pass current requirements as null unless a newly discovered authoritative requirements
surface now applies; a newly discovered/changed surface invalidates the prior evidence rather than being ignored.

Re-run `validate_review_coverage(...)` against that freshly rebuilt current identity and freshly re-established
current requirements reference. If any of `base_sha`, `head_sha`, or `merge_base_sha` differs from the stored
identity, establish conflict-resolution provenance before validation: pass
`conflict_resolution_occurred=True` when merge/rebase conflict resolution occurred and explicitly pass `False`
only when the available provider/Git history proves the SHA transition did not involve conflict resolution. If
that provenance cannot be established, do not assume `False`; the validator fails closed and posting is skipped.
Only a zero-error result may proceed. This catches base/merge-base, effective-patch, conflict-resolution, or
requirements drift even when the source-branch `head_sha` itself did not change. Phase 4 still performs its
existing per-write head-SHA revision gate to stop source changes that occur after this full-identity/requirements
gate.

**Fail closed:**

- Invalid or stale `change_identity` / `review_evidence` → `posting_decision: skip`; render Phase 5 as
  partial/unable and state that review evidence is stale or invalid.
- Current full identity cannot be rebuilt/validated → `posting_decision: skip`; never fall back to a head-only
  freshness claim at this gate.
- Identity SHAs changed but conflict-resolution provenance cannot be established → `posting_decision: skip`; an
  unknown conflict history is not equivalent to `conflict_resolution_occurred: false`.
- Current non-null requirements surface cannot be re-read/normalized, or differs from the stored requirements
  reference → `posting_decision: skip`; never post against requirements whose freshness cannot be established.
- `review_evidence.inspection_status: unable` → `posting_decision: skip`.
- **Any** `review_evidence.unable_to_inspect[]` entry with `mandatory: true` → `posting_decision: skip`,
  regardless of whether the envelope status is `partial` or `unable`. Mandatory unavailable coverage never
  reaches Phase 3/4.
- `inspection_status: complete` while any `review_evidence.unable_to_inspect[]` entry exists, or while any
  triggered `inspection_plan` surface is not `complete` → invalid coverage state; `posting_decision: skip`.
- `inspection_status: partial` may reach Phase 3 **only when every unavailable entry is non-mandatory**. Posting
  must not imply approval/readiness and always requires explicit Phase 3 confirmation even when the normal
  recommendation matrix would otherwise auto-skip a prompt. Phase 2 evidence must already have projected this
  state to `review_metrics.review_complete: false` so the existing Phase 3 incomplete-review prompt cannot be bypassed.
- A pending mandatory surface in the finalized `inspection_plan` is equivalent to unavailable evidence: do not
  treat it as clean and do not post a complete review.

When the gate **blocks posting** (invalid/stale evidence, mandatory unavailable surface, unchanged `head_sha`,
`chat-only`, user Hold/Cancel), **skip Phase 3 and Phase 4** and proceed to **Phase 5** for the chat-only
executive summary.

Compare current `diff_refs.head_sha` to the baseline `head_sha` from Phase 1 step 3 (prior
`<!-- cursor-pr-review -->` summary, if any).

| Situation | Next step |
|-----------|-----------|
| Invalid/stale `review_evidence` or `change_identity` | **Stop posting path** — Phase 5 partial/unable summary; explain evidence invalidation |
| Current full change identity cannot be rebuilt | **Stop posting path** — Phase 5 partial/unable summary; explain freshness could not be established |
| Identity changed and conflict-resolution provenance is unknown | **Stop posting path** — Phase 5 partial/unable summary; explain conflict freshness could not be established |
| Current requirements surface cannot be re-established or changed | **Stop posting path** — Phase 5 partial/unable summary; explain requirements freshness failure |
| Mandatory triggered inspection surface unavailable/pending | **Stop posting path** — Phase 5 partial/unable summary with `unable_to_inspect` |
| Partial evidence with only non-mandatory unavailable surfaces | Phase 3 confirmation required; any post must state partial coverage and must not imply approval/readiness |
| `head_sha` unchanged since prior review | **Stop posting path** — render chat summary + Phase 5 executive summary; **skip Phase 3 AND Phase 4**: *"No new commits since last review."* |
| New commits, new findings | Phase 3 → post **re-review summary**; inline threads only for new `file:line` not in prior threads/summary |
| New commits, no new findings | Phase 3 → post short re-review summary — prior issues resolved or unchanged |
| **> 30 commits since baseline** | **Warn** (*"prior review significantly outdated — N commits"*) and **offer full re-review** before incremental (see `reference/incremental-rerun.md`) |
| User chose Hold / Cancel (earlier) | Chat review only; do not post |
| `chat-only` posting mode | Skip Phase 3 and Phase 4; proceed to Phase 5 if review output not yet complete |
| Prior `head_sha` missing from history | Full re-review (squash/force-push — `reference/incremental-rerun.md`) |
| First review (no prior baseline) | Continue to Phase 3 per posting mode, subject to evidence gates above |

When incremental, load `reference/incremental-rerun.md` for dedupe rules (snippet hash, resolved
threads, squash caveat). Use the re-review template from `reference/comment-templates.md` when posting.

Record `posting_decision`:

- `posting_decision: post` — the gate allows proceeding to Phase 3/4. Read **`workflow/posting.md`**
  next. (Phase 3 may still end without anything posted — e.g. the user chooses Hold — but that's
  `posting.md`'s own internal confirmation logic, not a second gate here.)
- `posting_decision: skip` — the "Stop posting path" / invalid evidence / mandatory unavailable surface /
  `chat-only` / Hold-Cancel-earlier / draft rows above. Read **`workflow/phase-5.md`** directly; Phase 3
  and Phase 4 never run this pass.
