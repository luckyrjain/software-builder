# Domain Comprehension — `ADD_REPO` Onboarding Mode

**Date:** 2026-07-29
**Skill:** `domain-comprehension`

---

## Problem statement

`domain-comprehension` today has two ways to run: `FULL` (analyze every repo in scope from scratch) and
`DELTA` (re-run phases for repos already in `manifest.repos[]` whose HEAD SHA changed). Neither covers a
common real workflow, exemplified by the org's `Extract Service Knowledge Base` prompt: analyze **one new
repo at a time** and fold it into an **already-established** shared domain map, growing coverage
incrementally across many sessions instead of one big multi-repo pass.

`DELTA` cannot do this — it diffs SHAs for repos already listed in `manifest.repos[]`; a repo that was
never in scope has nothing to diff against. Running `FULL` re-scopes the whole engagement and re-touches
every repo, which is wrong when the goal is "just add this one service."

There is also no conflict-detection step for merging a new repo's claims (bounded context, data
ownership, API ownership) into deliverables that already contain claims from other repos.

---

## Scope

**In:** new `ADD_REPO` delivery_mode — inputs, entry gate, phase scoping, merge/conflict procedure, reuse
of `DELTA`'s affected-phases table for downstream re-synthesis, template addition for conflict records.

**Out:** changes to manifest schema (v2 `repos[]` already supports this), changes to `understand-anything`
tooling itself, a standalone (non-merging) single-repo mode — explicitly rejected in favor of the
incremental-onboarding model (see decision below).

---

## Decision: incremental onboarding, not standalone single-repo mode

Considered and rejected:

- **Standalone single-repo mode** (no merge) — closer to the extraction prompt's one-shot behavior, but
  throws away the point of running domain-comprehension repeatedly: knowledge doesn't compound.
- **Generalize `DELTA`** to treat "not in `manifest.repos[]`" as "changed" — rejected. `DELTA` computes the
  changed set from `git rev-parse HEAD` vs a stored `sha`; a never-seen repo has no stored SHA to diff, and
  conflating "SHA changed" with "repo is brand new" would obscure the changed-set procedure with a special
  case that behaves completely differently (new repo needs full P0–P1, not just re-run of already-known
  phases).
- **New session type outside `delivery_mode`** — rejected as unnecessarily disruptive; `delivery_mode`
  already has the resume/manifest/validator plumbing this needs.

**Chosen:** new `ADD_REPO` delivery_mode, structured like `DELTA`'s and `COMPLIANCE_RETROFIT`'s inline
procedure blocks in `workflow/inputs.md`, reusing `DELTA`'s affected-phases table verbatim for downstream
re-synthesis once the new repo's own phases are done.

---

## Section 1 — `workflow/inputs.md`

### 1a. New required input

Add to the input table:

| Field | Required | Default |
|-------|----------|---------|
| `new_repo_path` | Only for `ADD_REPO` | Ask if ambiguous |

`workspace_root` in `ADD_REPO` mode means the **existing shared engagement root** (must already contain a
valid `manifest.yaml`, schema v2) — not the new repo. This is a deliberate naming reuse: every other mode
already treats `workspace_root` as "where the manifest lives," so `ADD_REPO` doesn't need a separate
`shared_workspace_root` field, it just requires the entry gate below instead of allowing bootstrap.

### 1b. Delivery mode table — new row

| Mode | Behavior |
|------|----------|
| `ADD_REPO` | Onboard one repo not currently in `manifest.repos[]` into an existing engagement; full-rigor P0–P1 for that repo, then re-run downstream phases per the changed-set rules, with a conflict gate before merging into shared deliverables |

### 1c. `ADD_REPO` — procedure (new section, same level as DELTA's)

**Entry criteria (all required):**

- `manifest.yaml` exists at `workspace_root`, `schema_version: 2`, `engagement.status` is
  `IN_PROGRESS` or `FIRST_PASS_COMPLETE`
- `new_repo_path` resolves to a repo **not** present in `manifest.repos[]` (by name) — if it is present,
  stop and tell the user to use `DELTA` instead

**Steps:**

1. Classify the new repo ([repo-classification.md](../../../domain-comprehension/reference/repo-classification.md)), assign provisional tier.
2. Add a `manifest.repos[]` entry: `inventory: pending`, `understand: pending`, `deep_dive: pending`.
3. Run, scoped to the new repo only, at full rigor (same evidence/confidence bar as `FULL`):
   - P0 (inventory) — append repo census row, tech stack, config surface, repo relationships
   - P0.25 (contracts) — append this repo's producer/consumer rows to `API_CATALOG.md` / `EVENT_CATALOG.md`
   - P0.5 (mechanical) — run `/understand --full` for the new repo, merge into the existing
     `.understand-anything/domain-graph.json` via `/understand-domain` (do not regenerate other repos' graphs)
   - P1 (deep dive) — per-repo deep dive subsection, ownership card, initial smells
   - Session 0b squad enrichment — append one row to `SQUAD_MAP.md` for the new repo only
4. **Merge gate** (before writing any P0/P1 row into a shared deliverable — `BOUNDED_CONTEXTS.md`,
   `DATA_OWNERSHIP.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`): check the new repo's claim against existing
   rows for the same entity/context/path.
   - **No overlap** → append normally.
   - **Overlap** (e.g. two repos both claim authoritative ownership of a table; a bounded context gains a
     repo that contradicts its existing definition; an API path has a different producer than already
     recorded) → do **not** merge that row. Instead:
     - Write a row to `RISK_MAP.md` § Merge Conflicts (new section, see 1d) with both claims + evidence +
       confidence, `Status: open`
     - Write the same conflict to `UNKNOWNS.md`
     - Leave the owning phase (`p0` or `p1`) at `status: in_progress` in `manifest.yaml` — do **not** mark
       it `complete`. No new enum value needed: this is the same rule as `phase-outputs.md`'s existing
       cross-cutting rule 3 ("empty required table → phase incomplete"), extended to "contested required
       table row → phase incomplete."
     - **Stop.** Report the conflict to the user; do not proceed to step 5 for the affected deliverable
       until it's resolved (user picks a resolution, or the run is explicitly told to proceed with
       conflicts still open — in which case the phase stays `in_progress` and the conflict stays visible
       in the next resume).
5. Once new-repo P0–P1 merge is clean (or user has explicitly accepted open conflicts), determine
   downstream re-synthesis using **`DELTA`'s existing affected-phases table** (workflow/inputs.md § DELTA
   mode — procedure, step 2), treating the new repo as the changed set of one:
   - P2 reruns if new repo is Tier 0/1
   - P2b reruns if P2 reran and Datadog ✅
   - P3 reruns if new repo is Tier 0/1
   - P3b reruns if P3 reran
   - P4, P5 **always** rerun
6. Run `validate_manifest_yaml.py`; update `engagement.last_updated` and `engagement.next_action`.

**Do not:** re-run P0–P1 for repos already in `manifest.repos[]` (that's `DELTA`'s job if their SHA
changed); re-generate other repos' `/understand` graphs, only merge the new one in.

### 1d. Required outputs table (inline before Checkpoint, matching existing convention)

| Output | Location | Required fields |
|--------|----------|-----------------|
| New repo entry | `manifest.repos[]` | name, branch, sha, tier, classification |
| Merge conflicts (if any) | `RISK_MAP.md` § Merge Conflicts | Both claims, evidence, confidence, status |
| Re-synthesized exec summary | `EXEC_SUMMARY.md` | Five questions + overall confidence recomputed including new repo |

`workflow_version: 1.5` (bump from 1.4).

---

## Section 2 — `templates/RISK_MAP.md`

Add new section, inserted after "Change risk" (last section):

```markdown
## Merge Conflicts (ADD_REPO mode)

| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Status |
|----------|-----------------|-----------|----------------------|----------------------|-----------------|--------|
```

`Status` values: `open` (blocked, awaiting resolution) \| `resolved` (note which claim won and why, in a
follow-up row or by editing in place) \| `accepted-both` (user explicitly chose to keep both, e.g.
legitimate dual-write).

---

## Section 3 — `reference/manifest-schema.md`

No schema field changes — `repos[]` already has everything `ADD_REPO` needs. Add one line under **Agent
update rules**:

> 5. **`ADD_REPO`** — add new `repos[]` entry at start; on merge conflict leave **both** `p0` and `p1` at
>    `status: in_progress` (do not mark either `complete` while `RISK_MAP.md` § Merge Conflicts has any
>    `open` row — the table has no owning-phase column, so the gate blocks both phases rather than
>    attributing a conflict to just one; coarser than "that phase's deliverables" but avoids a structural
>    table change); run validator same as end-of-phase.

---

## Section 4 — `SKILL.md`

Add `ADD_REPO` row to the "Minimum viable deliverables by delivery_mode" table:

| `delivery_mode` | Required deliverables | Optional |
|-----------------|----------------------|----------|
| `ADD_REPO` | New repo's P0–P1 outputs merged (or conflict-flagged) into existing split deliverables; re-run `EXEC_SUMMARY.md`, `RISK_MAP.md`, and any phase downstream per the affected-phases table | `E2E_FLOW.md` update only if P2 reran |

---

## Section 5 — `reference/phase-index.md`

Add one row to the "Quick paths" table:

| User asks | Phases |
|-----------|--------|
| Onboard one new repo into existing map | Inputs (`ADD_REPO`) → P0/P0.25/P0.5/P1 for new repo → merge gate → affected downstream phases per DELTA table |

---

## Open items for implementation plan

- Exact wording for the "conflict resolution" user prompt (what options do we present — pick a claim,
  keep both, defer).
- `validate_manifest_yaml.py` gets a new `--workspace-root`-mode check (same family as
  `_validate_p2b_runtime_gate`): if `RISK_MAP.md` has any § Merge Conflicts row with `Status: open`, the
  corresponding phase (`p0`/`p1`) in `manifest.yaml` must not be `status: complete`. Included in the
  implementation plan below.
