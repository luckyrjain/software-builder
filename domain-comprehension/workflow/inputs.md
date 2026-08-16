---
workflow_version: 1.19
phase: inputs
produces:
  - workspace_root
  - workspace_layout
  - domain_name
  - domain_config
  - delivery_mode
  - discovery_budget
consumes: []
---

# Inputs — parse from user message

**Read this file** before Session 0 or resume.

| Field | Required | Default |
|-------|----------|---------|
| `workspace_root` | Yes | Ask if ambiguous |
| `domain_name` | Yes | Infer from user message; confirm in Session 0 |
| `workspace_layout` | No | Auto-detect: `sibling-repos` \| `monorepo` \| `single-repo` |
| `domain_config` | No | Create/load under the resolved `artifact_root` |
| `delivery_mode` | No | `QUICK` when no `manifest.yaml` exists yet (first-time engagement) — see table below |
| `discovery_budget` | No | Profile default for QUICK/FULL/DELTA/ADD_REPO from [domain-model-contract.yaml](../reference/domain-model-contract.yaml); CUSTOM requires explicit limits |
| `domain_pack` | No | e.g. `fintech-payout` — see [domain-packs](../reference/domain-packs/README.md) |
| `memory_bank.export_mode` | No | From `{artifact_root}/domain-config.yaml`; override in user message (`never` \| `optional` \| `p5`) |
| `api_tooling.export_mode` | No | From `{artifact_root}/domain-config.yaml`; override in user message (`never` \| `optional` \| `p5`) |
| `new_repo_path` | Only for `ADD_REPO` | Ask if ambiguous |
| `proposal` | Only for `PROPOSAL_CHECK` | Ask if absent — free-text description: proposed name/domain area, claimed data entities, claimed API paths/producers |

## Discovery budget

Resolve the run budget before repository discovery. Use the selected delivery mode's `default_limits` from
[domain-model-contract.yaml](../reference/domain-model-contract.yaml), unless the caller explicitly selects
CUSTOM limits. New engagements persist profile, configured limits, and consumed counters in root
`manifest.yaml` `discovery_budget`; mirror the same counters into `PROGRESS.md` for humans.

On RESUME/DELTA/ADD_REPO, use the manifest block as machine source of truth when present and continue from its
consumed counters rather than resetting them. For a legacy schema-v2 manifest with no `discovery_budget`,
backfill the block before new source discovery: recover prior consumption from existing machine/progress state
when possible; if it cannot be recovered without guessing, disclose the limitation and set a conservative
remaining budget rather than assuming zero prior consumption.

Stop discovery when the completion/evidence gate is satisfied or any configured limit is reached. If a limit
is reached first, mark the run/phase PARTIAL, record the unresolved evidence gap in `UNKNOWNS.md`, and do not
silently exceed the budget. Persist consumed counters after every discovery-bearing phase. PROPOSAL_CHECK uses
existing artifacts and therefore does not open a new source-discovery budget.

## Artifact location resolution

`manifest.yaml` is the only domain-comprehension file stored directly at `workspace_root`. All other
canonical domain artifacts are resolved under `engagement.artifact_root`, defaulting to
`docs/domain-comprehension/<domain-slug>/`.

- **First run:** derive `domain_slug` from `domain_name`, then use
  `docs/domain-comprehension/<domain_slug>` unless the caller supplied another safe relative
  `scope.artifact_root`. Session 0 creates it when absent.
- **RESUME / DELTA / ADD_REPO / PROPOSAL_CHECK:** load root `manifest.yaml` first, then read
  `engagement.artifact_root`; do not rediscover or silently change the artifact location.
- `domain_slug` must be one path segment: lowercase letters/digits plus `-`; replace other runs of
  characters with `-`, trim leading/trailing `-`, and reject an empty result. Never allow `/`, `\\`, an
  absolute path, or `..` to enter the derived path.
- In this workflow, an unqualified canonical artifact name such as `PROGRESS.md`, `RISK_MAP.md`,
  `PRD.md`, or `API_CATALOG.md` means `{artifact_root}/<name>`. The only explicit root exception is
  `manifest.yaml`. The standalone **squad-map** skill may also maintain a shared root `SQUAD_MAP.md`, but
  domain-comprehension uses its snapshot at `{artifact_root}/SQUAD_MAP.md`.

See [run-scoped-artifacts.md](../reference/run-scoped-artifacts.md).

## Workspace layout detection

| Signal | Layout |
|--------|--------|
| Multiple sibling directories each with `.git` | `sibling-repos` |
| Single `.git` at root, multiple top-level services | `monorepo` |
| Single `.git`, one deployable unit | `single-repo` |

## Domain config

On an existing engagement, read root `manifest.yaml` and load
`{workspace_root}/{engagement.artifact_root}/domain-config.yaml`. On a first run, Session 0 creates
`{artifact_root}/domain-config.yaml` from user input plus the optional domain pack. Schema:
[domain-config-schema.md](../reference/domain-config-schema.md).

If user names a domain pack, merge pack defaults then overlay user overrides.

**Memory Bank:** If user asks for per-repo Memory Banks or mentions `cursor-bank`, set
`memory_bank.export_mode: p5` in config unless they say export-only / never. See
[memory-bank-integration.md](../reference/memory-bank-integration.md). P5 export replaces a separate
"initialize memory bank" agent pass.

**API tooling:** If user asks for a runnable Postman collection, curl commands, or API testing tooling,
set `api_tooling.export_mode: p5` in config unless they say export-only / never. See
[api-tooling-integration.md](../reference/api-tooling-integration.md).

## Delivery mode

**Default for a first-time engagement (no `manifest.yaml` yet) is `QUICK`, not `FULL`** — a user who
just says "map the X domain" gets a fast orientation pass, not the entire multi-session pipeline
unasked. Say "full comprehension" / "full pass" / name a specific deliverable outside QUICK's scope to
opt into `FULL` explicitly.

| Mode | Behavior |
|------|----------|
| `QUICK` | **Default for first-time engagements.** Session 0 + P0 + draft five questions only — no P0.5 mechanical pass |
| `FULL` | All comprehension phases for all in-scope repos — opt in explicitly |
| `RESUME` | Read root `manifest.yaml`, resolve `artifact_root`, restore/backfill discovery budget, then continue from `{artifact_root}/PROGRESS.md` / Next action |
| `DELTA` | Re-run phases for repos whose HEAD SHA changed since last manifest |
| `ADD_REPO` | Onboard one repo not currently in `manifest.repos[]` into an existing engagement; full-rigor P0–P1 for that repo, then re-run downstream phases per the DELTA affected-phases rules, gated by a merge-conflict check |
| `COMPLIANCE_RETROFIT` | Normalize split deliverables + `manifest.yaml` from an existing first pass **without** re-analyzing code |
| `PROPOSAL_CHECK` | Compare a proposal against the existing engagement's deliverables; read-only against canonical artifacts, with one report written under `artifact_root` |

### COMPLIANCE_RETROFIT — procedure

Use when analysis is done but artifacts are consolidated, split files missing, or `manifest.yaml` absent/invalid.

**Entry criteria (all required):**

- An existing `PROGRESS.md` has substantive phase notes or `FIRST_PASS_COMPLETE`
- At least one of: `{map_file}`, `EXEC_SUMMARY.md`, or `BOUNDED_CONTEXTS.md` has non-stub content
- User confirms retrofit (do not discard existing analysis)

When root `manifest.yaml` already exists, resolve all names above under its `engagement.artifact_root`.
For a legacy pre-artifact-root engagement, discover the existing root files once, choose/create
`docs/domain-comprehension/<domain-slug>/`, and move/copy the canonical domain artifacts there as part of
the retrofit; do not leave a second canonical copy at root.

**Steps:**

1. Load the existing `domain-config.yaml` (or infer `map_file` from an existing `{DOMAIN}_MAP.md`) and
   resolve/create `artifact_root`.
2. Copy missing domain stubs from `templates/` to `artifact_root` — do **not** overwrite non-empty
   sections. Copy/create `manifest.yaml` at workspace root only.
3. Split consolidated content into required files (`BOUNDED_CONTEXTS.md`, `RISK_MAP.md`, etc.) under
   `artifact_root`, leaving stub+link in `{map_file}` where appropriate.
4. Create or repair root `manifest.yaml` from disk state, set `engagement.artifact_root`, and set
   `phases.*.status` from `{artifact_root}/PROGRESS.md` checkpoints. When no new discovery is performed,
   preserve/backfill `discovery_budget` without inventing consumed history.
5. Run `validate_manifest_yaml.py --workspace-root <workspace_root>`; fix artifact/diagram rows until exit 0.
6. Set `engagement.next_action` to first incomplete phase, or P5 `--strict` if only gaps remain.

**Do not:** re-run `/understand`, re-grep repos, rewrite conclusions unless a required table is literally
empty, or recreate canonical domain files at workspace root.

### DELTA mode — procedure

Requires root `manifest.yaml` with at least P0 complete. If not present, fall back to `FULL` with a warning.
Resolve all canonical domain files through `engagement.artifact_root` before reading or writing them. Restore
or backfill `discovery_budget` before any repo/search/deep-read work.

1. Load `manifest.yaml`; for each `repos[]` entry run:
   ```bash
   git -C <repo-path> rev-parse HEAD
   ```
   Compare to `repos[].sha`. Build the **changed set** of repos where SHA differs.

2. Determine **affected phases** from the changed set:
   - **P0, P1**: re-run for every repo in the changed set
   - **P0.25**: re-run contract rows for changed repos only; carry forward unchanged repos' rows
   - **P2**: re-run if any Tier 0/1 repo changed, **or** if P0.25 added/removed any contract row for a
     changed repo at any tier
   - **P2b**: re-run if P2 re-ran and Datadog ✅
   - **P3**: re-run if any Tier 0/1 repo changed
   - **P3b**: re-run if P3 re-ran
   - **P4, P5**: always re-run after any upstream phase re-ran

3. Refresh affected machine artifacts per [machine-domain-model.md](../reference/machine-domain-model.md),
   then compare previous vs refreshed source revisions, API/event contracts, data ownership, dependency
   semantics, and capability ownership/code locations using `stale_prd_detection`. If any stale condition
   fires, regenerate affected `PRD.md` requirements/traceability or explicitly mark the PRD stale in
   `PROGRESS.md` and block claims that it is current. Never silently retain a stale PRD.
4. Phases with no upstream changes keep their `complete` status unchanged.
5. At end, persist `discovery_budget.consumed`, run `validate_manifest_yaml.py --workspace-root <workspace_root>`;
   update `engagement.last_updated` and `engagement.next_action`.

### ADD_REPO mode — procedure

Requires root `manifest.yaml` with `schema_version: 2` and `engagement.status` of `IN_PROGRESS` or
`FIRST_PASS_COMPLETE`. Resolve `artifact_root` from that manifest and restore/backfill `discovery_budget`
before source discovery. `new_repo_path` must resolve to a repo **not** present in `manifest.repos[]` (match by
`name`) — if it is present, stop and tell the user to use `DELTA` instead.

1. Classify the new repo ([repo-classification.md](../reference/repo-classification.md)), assign
   provisional tier.
2. Add a `manifest.repos[]` entry: `inventory: pending`, `understand: pending`, `deep_dive: pending`.
3. Run, scoped to the new repo only, at the same evidence/confidence bar as `FULL`:
   - P0 (inventory) — append repo census row, tech stack, config surface, repo relationships
   - P0.25 (contracts) — append this repo's producer/consumer rows to
     `{artifact_root}/API_CATALOG.md` / `{artifact_root}/EVENT_CATALOG.md`
   - P0.5 (mechanical) — run `/understand --full` for the new repo and merge into
     `{artifact_root}/.understand-anything/domain-graph.json` via `/understand-domain`
   - P1 (deep dive) — append per-repo deep dive subsection, ownership card, initial smells
   - Session 0b squad enrichment — refresh/append the domain snapshot at `{artifact_root}/SQUAD_MAP.md`
4. **Merge gate.** Before writing any P0/P1 row into a canonical shared domain deliverable
   (`BOUNDED_CONTEXTS.md`, `DATA_OWNERSHIP.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`), check the new
   repo's claim against existing rows for the same entity/context/path:
   - **No overlap** → append normally.
   - **Overlap** → do **not** merge that row. Instead:
     - Add a row to `{artifact_root}/RISK_MAP.md` § Merge Conflicts with both claims + evidence +
       confidence, `Status: open`
     - Add the same conflict to `{artifact_root}/UNKNOWNS.md`
     - Leave the owning phase (`p0` or `p1`) at `status: in_progress` in root `manifest.yaml`
     - **Stop.** Report the conflict; do not proceed for the affected deliverable until resolved
5. Once new-repo P0–P1 merge is clean, determine downstream re-synthesis using the DELTA rules:
   - P2 reruns if new repo is Tier 0/1
   - P2b reruns if P2 reran and Datadog ✅
   - P3 reruns if new repo is Tier 0/1
   - P3b reruns if P3 reran
   - P4, P5 **always** rerun
6. Refresh the four machine artifacts and run the same stale-PRD comparison as DELTA. Regenerate affected
   PRD requirements/traceability or mark the PRD stale explicitly; never retain it silently after a stale
   condition fires.
7. Persist `discovery_budget.consumed`, run `validate_manifest_yaml.py --workspace-root <workspace_root>
   --check-content`; update `engagement.last_updated` and `engagement.next_action`.

**Do not:** re-run P0–P1 for repos already in `manifest.repos[]`; regenerate other repos' `/understand`
graphs; or write canonical domain artifacts at workspace root.

**Required outputs:**

| Output | Location | Required fields |
|--------|----------|-----------------|
| New repo entry | root `manifest.repos[]` | name, branch, sha, tier, classification |
| Merge conflicts (if any) | `{artifact_root}/RISK_MAP.md` § Merge Conflicts | Both claims, evidence, confidence, status |
| Re-synthesized exec summary | `{artifact_root}/EXEC_SUMMARY.md` | Five questions + overall confidence recomputed including new repo |

### PROPOSAL_CHECK mode — procedure

Requires root `manifest.yaml` with `schema_version: 2` and `engagement.status` of `IN_PROGRESS` or
`FIRST_PASS_COMPLETE`. Resolve `artifact_root` from that manifest first. For every repo plausibly touched
by the proposal's claims, `repos[].inventory` must be `complete` and `repos[].deep_dive` must be
`complete` or deliberately `skipped`. If any touched repo is still pending, **Stop** and tell the user to
run `FULL` or `QUICK` comprehension first.

1. Load root `manifest.yaml` plus `{artifact_root}/BOUNDED_CONTEXTS.md`,
   `{artifact_root}/DATA_OWNERSHIP.md`, `{artifact_root}/API_CATALOG.md`, and
   `{artifact_root}/EVENT_CATALOG.md`.
2. Parse proposal claims into bounded-context membership/definition, data-entity ownership, and API-path
   production. Do not invent a category the proposal does not state.
3. Reuse the ADD_REPO merge-gate overlap taxonomy against existing rows only; nothing is appended/merged.
4. The proposal's own claims are not evidence; verdicts cite existing deliverable evidence.
5. Write `{artifact_root}/PROPOSAL_CHECK_REPORT.md` from
   [templates/PROPOSAL_CHECK_REPORT.md](../templates/PROPOSAL_CHECK_REPORT.md), one row per checked claim
   plus overall verdict.
6. **No writes** to root `manifest.yaml` or canonical evidence artifacts (`RISK_MAP.md`,
   `BOUNDED_CONTEXTS.md`, `DATA_OWNERSHIP.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`). This mode writes
   only the report under `artifact_root`.

**Do not:** treat a clear proposal-check verdict as installing the proposal into the engagement.

**Required outputs:**

| Output | Location | Required fields |
|--------|----------|-----------------|
| Proposal check report | `{artifact_root}/PROPOSAL_CHECK_REPORT.md` | Claim, category, verdict, colliding entry (repo/evidence/confidence) if conflict |

## Required outputs

| Output | Source | If absent |
|--------|--------|-----------|
| `workspace_root` | User message or prompt | Ask user — cannot proceed |
| `workspace_layout` | Auto-detect or user-specified | Default to `sibling-repos` detection |
| `domain_name` | User message; confirm in Session 0 | Ask user |
| `delivery_mode` | User message | Default `QUICK` (no `manifest.yaml` yet) |
| `discovery_budget` | Manifest machine state or delivery profile/CUSTOM input | Initialize/backfill before discovery; CUSTOM without limits is invalid |
| `domain_pack` | User message (optional) | Skip — no pack merge |

## Environment constraints

- **Code-only** — no prod API calls, DB writes, deploys
- Analyze at **current checked-out branch HEAD** per repo — record `repo → branch → short SHA`
