# Domain Comprehension — PROPOSAL_CHECK delivery mode (Architecture Decision Assistant)

**Date:** 2026-08-05
**Skill:** `domain-comprehension`
**Source:** Item #6 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P1, "Architecture Decision Assistant — domain-comprehension only, but used differently from its normal
full-map mode: check a proposed feature/service against existing bounded contexts and flag conflicts...
closer to a domain-comprehension feature request than a new agent."

---

## Problem statement

A team proposing a new service, or a new bounded context inside an existing one, wants to know *before
building it* whether the proposal collides with an already-mapped domain — a data table another repo
already claims authoritative ownership of, an API path another service already produces, a bounded
context whose definition the proposal contradicts. Today the only way to get that answer is to run
`ADD_REPO` against a *real* repo already containing the proposed code — there's no way to check a
proposal that doesn't have code yet.

## What's already there vs. genuinely new

`ADD_REPO` mode (`workflow/inputs.md` § ADD_REPO mode — procedure, lines 116–160) already implements
almost exactly this conflict-detection shape, just triggered by a different event (a real new repo being
onboarded) and against different evidence (that repo's actual P0/P1 analysis output). Its **Merge gate**
(lines 134–147) is the reusable core:

> "Before writing any P0/P1 row into a shared deliverable (`BOUNDED_CONTEXTS.md`, `DATA_OWNERSHIP.md`,
> `API_CATALOG.md`, `EVENT_CATALOG.md`), check the new repo's claim against existing rows for the same
> entity/context/path: **No overlap** → append normally. **Overlap** (two repos both claim authoritative
> ownership of a table; a bounded context gains a repo that contradicts its existing definition; an API
> path has a different producer than already recorded) → do not merge that row..."

`PROPOSAL_CHECK` reuses this exact overlap taxonomy, substituting "the proposal" for "the new repo," but
diverges from `ADD_REPO` in three load-bearing ways:

| | `ADD_REPO` | `PROPOSAL_CHECK` |
|---|---|---|
| Evidence source | Real repo, analyzed at P0/P1 rigor | The proposal text itself — not evidence, just a claim to check |
| On no conflict | Merges the row into `BOUNDED_CONTEXTS.md` etc. — the repo is now part of the engagement | **Never merges anything** — nothing was actually built; existing deliverables are untouched |
| `manifest.yaml` | Gets a new `repos[]` entry, phase statuses updated | **Not touched at all** — read-only comparison, no engagement-state change |

Because nothing is merged and `manifest.yaml` is never written, `PROPOSAL_CHECK` needs no new entry in the
"Allowed writes" list beyond what's already there ("Markdown deliverables") — its one output,
`PROPOSAL_CHECK_REPORT.md`, is a markdown deliverable like any other.

## Scope

**In:**
- New `PROPOSAL_CHECK` delivery mode: 1 new required input (`proposal`), 1 new precondition (existing
  `manifest.yaml`, engagement-wide status bar, and per-repo `inventory`/`deep_dive` complete-or-skipped
  for the repos the proposal would touch), reuse of `ADD_REPO`'s
  overlap taxonomy against the *existing* `BOUNDED_CONTEXTS.md` / `DATA_OWNERSHIP.md` / `API_CATALOG.md`
  / `EVENT_CATALOG.md` (read-only), one new deliverable template `PROPOSAL_CHECK_REPORT.md`.
- SKILL.md footprint kept to the minimum the 180-line cap allows (174/180 used today, 6 lines of
  headroom): one row in the existing delivery-mode table, one word added to the `Begin` section's mode
  list — no new section.
- `workflow/inputs.md`: new `### PROPOSAL_CHECK — procedure` subsection, same shape as the existing three
  procedure subsections; `workflow_version` bump; `reference/workflow-changelog.md` row;
  `reference/deliverable-templates.md` row; `templates/PROPOSAL_CHECK_REPORT.md` template;
  `examples.md` invocation row; root `CHANGELOG.md` entry.

**Out:**
- **No `manifest.yaml` schema change.** `PROPOSAL_CHECK` writes nothing into the manifest — avoids
  touching `reference/manifest-schema.md`'s schema version and the `lint-domain-comprehension-skill`
  Makefile target's `schema_version: 2` check.
- **No `RISK_MAP.md` write.** That file tracks the *real* engagement's open risks; a hypothetical
  proposal's conflicts are not a standing risk on the actual codebase until the proposal is actually
  built (at which point `ADD_REPO` is the right mode, and its own merge gate already writes to
  `RISK_MAP.md`). Conflating the two would make `RISK_MAP.md` need to distinguish "real, currently open"
  from "hypothetical, proposal-time" — unnecessary complexity for what the roadmap scoped as a read-only
  check.
- **No new live chat-confirmation gate.** Unlike Session 0's scope/budget checkpoint, `PROPOSAL_CHECK` is
  a single bounded read-compare-report pass with no phased/budget dimension to approve — it either has a
  usable `manifest.yaml` to check against or it doesn't (HARD STOP, see below), never a mid-flow choice.
- **No new skill directory, no Makefile install/lint target, no `.cursor/rules`/`.kiro/steering` file** —
  this is a mode addition to an existing, already-wired skill, not a new team-facing wrapper agent. This
  mirrors the roadmap's own framing exactly ("closer to a domain-comprehension feature request than a new
  agent") and is the one item of the 11 where that's true.

## Precondition — HARD STOP, not a live gate

`PROPOSAL_CHECK` requires `manifest.yaml` at `workspace_root` with `schema_version: 2` and
`engagement.status` of `IN_PROGRESS` or `FIRST_PASS_COMPLETE` (the same engagement-wide bar `ADD_REPO`
itself requires), **and**, per repo the proposal's claims would touch, `repos[].inventory: complete` and
`repos[].deep_dive` either `complete` or `skipped` — `skipped` counts, since a Tier 2/3 repo skipped per
[large-scale-execution.md](../../../domain-comprehension/reference/large-scale-execution.md) is a legitimate terminal state on a finished
engagement, not an incomplete one; requiring literal `complete` would wrongly HARD STOP on every large
multi-repo engagement the framework itself already considers done. If `manifest.yaml` is absent, or a
touched repo's `inventory` is still `pending` or its `deep_dive` is `pending`:

> **Stop.** Tell the user: "PROPOSAL_CHECK compares a proposal against existing, evidence-backed
> deliverables — it doesn't create them. Run `FULL` or `QUICK` domain comprehension for this workspace
> first, then re-run PROPOSAL_CHECK." Do not fall back to `FULL` automatically and do not attempt a
> partial check against incomplete deliverables.

This is a terminal stop-and-report, not a mid-flow question — no live confirmation to script, unlike
pr-review/incident-rca's synchronous checkpoints. (Contrast with `DELTA` mode, which *does* auto-fall-back
to `FULL` with a warning when its own precondition is unmet — `PROPOSAL_CHECK` deliberately does not,
because falling back to a full engagement run is not a reasonable substitute for "check this proposal,"
the way it is a reasonable substitute for "re-run changed phases.")

## Task A — SKILL.md (minimal footprint)

Bumps nothing structurally; two single-line edits.

Find (delivery-mode table, existing row order):
```markdown
| `COMPLIANCE_RETROFIT` | Normalize split deliverables + `manifest.yaml` from an existing first pass **without** re-analyzing code |
```
Replace with (append one row after it):
```markdown
| `COMPLIANCE_RETROFIT` | Normalize split deliverables + `manifest.yaml` from an existing first pass **without** re-analyzing code |
| `PROPOSAL_CHECK` | Compare a proposed feature/service against the existing engagement's bounded contexts / data ownership / API contracts; **read-only**, writes only `PROPOSAL_CHECK_REPORT.md`, never merges into shared deliverables or `manifest.yaml` |
```

Find (`## Begin`, step 1):
```markdown
1. [workflow/inputs.md](workflow/inputs.md) — set `delivery_mode` (`FULL` \| `RESUME` \| `DELTA` \| `ADD_REPO` \| `COMPLIANCE_RETROFIT`)
```
Replace with:
```markdown
1. [workflow/inputs.md](workflow/inputs.md) — set `delivery_mode` (`FULL` \| `RESUME` \| `DELTA` \| `ADD_REPO` \| `COMPLIANCE_RETROFIT` \| `PROPOSAL_CHECK`)
```

Net: +1 line (175/180). No other SKILL.md section touched.

## Task B — `workflow/inputs.md`

Bumps `workflow_version` (currently `1.14`) to `1.15`.

Add to the top-level Required/Optional table, a new row after `new_repo_path`:
```markdown
| `proposal` | Only for `PROPOSAL_CHECK` | Ask if absent — free-text description: proposed name/domain area, claimed data entities, claimed API paths/producers |
```

Add to the `## Delivery mode` table, after the `COMPLIANCE_RETROFIT` row (same row added to SKILL.md's
copy, kept in sync):
```markdown
| `PROPOSAL_CHECK` | Compare a proposal against the existing engagement's deliverables; read-only, no merge |
```

New subsection, placed after `### ADD_REPO mode — procedure` and before `## Required outputs`:

```markdown
### PROPOSAL_CHECK mode — procedure

Requires `manifest.yaml` at `workspace_root` with `schema_version: 2` and `engagement.status` of
`IN_PROGRESS` or `FIRST_PASS_COMPLETE` (same engagement-wide bar `ADD_REPO` requires — see its own
precondition above), **and**, for every repo plausibly touched by the proposal's claims (if the proposal
names specific repos, check those; if it doesn't, check every repo in `manifest.repos[]`), that repo's own
`repos[].inventory: complete` **and** `repos[].deep_dive` is `complete` **or** `skipped`. `skipped` counts
as satisfied here — per [large-scale-execution.md](../../../domain-comprehension/reference/large-scale-execution.md) ("P1 | Deep dive
tier 0/1 only unless flow-critical"), a Tier 2/3 repo with `deep_dive: skipped` is a legitimate, correctly
terminal state on a finished engagement, not an incomplete one; requiring literal `complete` would HARD
STOP on every large multi-repo engagement the framework itself considers done. If any touched repo's
`inventory` is still `pending`, or its `deep_dive` is `pending` (not yet reached, unlike a deliberate
`skipped`): **Stop.** Tell the user to run `FULL` or `QUICK` comprehension for this workspace first — do
not fall back automatically, do not check against incomplete deliverables.

1. Load `manifest.yaml`, `BOUNDED_CONTEXTS.md`, `DATA_OWNERSHIP.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`.
2. Parse the proposal's claims into the same three categories the merge gate checks: bounded-context
   membership/definition, data-entity ownership, API-path production. A proposal that doesn't state a
   claim in one category (e.g. no API paths mentioned) simply has nothing to check in that category —
   don't invent claims it didn't make.
3. **Reuses the `ADD_REPO` merge gate's overlap taxonomy** ([§ ADD_REPO mode — procedure](#add_repo-mode--procedure)
   step 4), substituting "the proposal" for "the new repo," against the *existing* rows only — nothing is
   ever appended or merged:
   - **No overlap** → record as clear for that claim.
   - **Overlap** (the proposal claims authoritative ownership of a table another repo already owns; the
     proposal's bounded context contradicts an existing bounded context's recorded definition; the
     proposal's API path already has a different producer on record) → record as a conflict, citing the
     existing deliverable's row (repo, evidence, confidence) it collides with.
4. **The proposal's own claims are not evidence** — a proposal that asserts "no conflict here" doesn't
   make it so; every verdict must cite the *existing* deliverable's evidence, never just restate the
   proposal's own text back as if verified.
5. Write `PROPOSAL_CHECK_REPORT.md` (template: [templates/PROPOSAL_CHECK_REPORT.md](../templates/PROPOSAL_CHECK_REPORT.md)) —
   one row per checked claim (Claim, Category, Verdict, Colliding existing entry + evidence + confidence
   if any), plus an overall verdict (Clear / N conflict(s) found).
6. **No writes to `manifest.yaml`, `RISK_MAP.md`, `BOUNDED_CONTEXTS.md`, `DATA_OWNERSHIP.md`,
   `API_CATALOG.md`, or `EVENT_CATALOG.md`** — this mode only ever writes `PROPOSAL_CHECK_REPORT.md`. If
   the proposal is later actually built, `ADD_REPO` (once real code exists) is the mode that merges it in.

**Do not:** treat a clear `PROPOSAL_CHECK_REPORT.md` verdict as installing the proposal into the
engagement — a second `PROPOSAL_CHECK` run against a revised proposal, or the eventual real `ADD_REPO`
run, starts from the same unmodified existing deliverables every time.

**Required outputs:**

| Output | Location | Required fields |
|--------|----------|-----------------|
| Proposal check report | `PROPOSAL_CHECK_REPORT.md` | Claim, category, verdict, colliding entry (repo/evidence/confidence) if conflict |
```

## Task C — `reference/deliverable-templates.md`

Add a row to the Split deliverables table (after the `E2E_FLOW.md` row, marked optional like it):
```markdown
| `PROPOSAL_CHECK_REPORT.md` | Optional — only written when `delivery_mode: PROPOSAL_CHECK` runs; never merged into any other deliverable |
```

## Task D — `templates/PROPOSAL_CHECK_REPORT.md` (new file)

```markdown
# Proposal check report

**Proposal:** <name/one-line description>
**Checked against:** manifest.yaml as of <engagement.last_updated>

## Verdict: <Clear | N conflict(s) found>

| Claim | Category | Verdict | Colliding existing entry | Evidence | Confidence |
|-------|----------|---------|---------------------------|----------|------------|
| <claim text> | Bounded context \| Data ownership \| API path | Clear \| Conflict | <repo/table/path, or —> | <repo>/path:Line, or —> | HIGH \| MEDIUM \| LOW \| UNKNOWN |

## Notes

- This report does not modify `BOUNDED_CONTEXTS.md`, `DATA_OWNERSHIP.md`, `API_CATALOG.md`,
  `EVENT_CATALOG.md`, `RISK_MAP.md`, or `manifest.yaml`. If this proposal is built, re-check it (claims
  may have changed) and, once real code exists, onboard it via `ADD_REPO`.
```

## Task E — `examples.md`, root `CHANGELOG.md`, `reference/workflow-changelog.md`

- `examples.md`: one new invocation row — "user has a proposed service, existing engagement's
  `manifest.yaml` is complete → PROPOSAL_CHECK compares proposal against `BOUNDED_CONTEXTS.md` /
  `DATA_OWNERSHIP.md` / `API_CATALOG.md`, writes `PROPOSAL_CHECK_REPORT.md`, no merge" — plus a
  HARD-STOP row for "no `manifest.yaml` yet" mirroring the precondition above.
- Root `CHANGELOG.md`: new `### PROPOSAL_CHECK delivery mode (2026-08-05)` entry at the top of the
  existing `## domain-comprehension` section (line 158), above `### ADD_REPO delivery mode (2026-07-30)`.
- `reference/workflow-changelog.md`: new row `1.15 | 2026-08-05 | inputs.md, SKILL.md,
  deliverable-templates.md, templates/PROPOSAL_CHECK_REPORT.md | New PROPOSAL_CHECK delivery mode —
  compare a proposal against existing deliverables, reusing ADD_REPO's merge-gate overlap taxonomy
  read-only` (precondition wording corrected in a follow-up `1.16` row once the real
  `engagement.status`/`inventory`/`deep_dive` schema fields were used instead of a non-existent per-repo
  "P0/P1 status" field — see round-1 review fix).

## Verification

`make lint-domain-comprehension-skill` must stay green with no target changes needed — this mode adds no
new required reference file, no manifest schema change, and stays within the 180-line SKILL.md cap
(175/180 after Task A).

## Open items for implementation plan

- None — markdown-only, no code, no new tests, no new skill directory.
