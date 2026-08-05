---
workflow_version: 1.14
phase: inputs
produces:
  - workspace_root
  - workspace_layout
  - domain_name
  - domain_config
  - delivery_mode
consumes: []
---

# Inputs — parse from user message

**Read this file** before Session 0 or resume.

| Field | Required | Default |
|-------|----------|---------|
| `workspace_root` | Yes | Ask if ambiguous |
| `domain_name` | Yes | Infer from user message; confirm in Session 0 |
| `workspace_layout` | No | Auto-detect: `sibling-repos` \| `monorepo` \| `single-repo` |
| `domain_config` | No | Create at Session 0 from user input + optional domain pack |
| `delivery_mode` | No | `QUICK` when no `manifest.yaml` exists yet (first-time engagement) — see table below |
| `domain_pack` | No | e.g. `fintech-payout` — see [domain-packs](../reference/domain-packs/README.md) |
| `memory_bank.export_mode` | No | From `domain-config.yaml`; override in user message (`never` \| `optional` \| `p5`) |
| `api_tooling.export_mode` | No | From `domain-config.yaml`; override in user message (`never` \| `optional` \| `p5`) |
| `new_repo_path` | Only for `ADD_REPO` | Ask if ambiguous |

## Workspace layout detection

| Signal | Layout |
|--------|--------|
| Multiple sibling directories each with `.git` | `sibling-repos` |
| Single `.git` at root, multiple top-level services | `monorepo` |
| Single `.git`, one deployable unit | `single-repo` |

## Domain config

If `domain-config.yaml` exists at `workspace_root`, load it. Schema:
[reference/domain-config-schema.md](../reference/domain-config-schema.md).

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
| `RESUME` | Read `manifest.yaml` + `PROGRESS.md`; continue from Next action |
| `DELTA` | Re-run phases for repos whose HEAD SHA changed since last manifest |
| `ADD_REPO` | Onboard one repo not currently in `manifest.repos[]` into an existing engagement; full-rigor P0–P1 for that repo, then re-run downstream phases per the DELTA affected-phases rules, gated by a merge-conflict check |
| `COMPLIANCE_RETROFIT` | Normalize split deliverables + `manifest.yaml` from an existing first pass **without** re-analyzing code |

### COMPLIANCE_RETROFIT — procedure

Use when analysis is done but artifacts are consolidated, split files missing, or `manifest.yaml` absent/invalid.

**Entry criteria (all required):**

- `PROGRESS.md` exists with substantive phase notes or `FIRST_PASS_COMPLETE`
- At least one of: `{map_file}`, `EXEC_SUMMARY.md`, or `BOUNDED_CONTEXTS.md` has non-stub content
- User confirms retrofit (do not discard existing analysis)

**Steps:**

1. Load `domain-config.yaml` (or infer `map_file` from existing `{DOMAIN}_MAP.md`)
2. Copy any missing stubs from `templates/` to `workspace_root` — do **not** overwrite non-empty sections
3. Split consolidated content into required split files (`BOUNDED_CONTEXTS.md`, `RISK_MAP.md`, etc.) by moving sections, leaving stub+link in `{map_file}` where appropriate
4. Create or repair `manifest.yaml` from disk state; set `phases.*.status` from `PROGRESS.md` checkpoints
5. Run `validate_manifest_yaml.py`; fix artifact/diagram rows until exit 0
6. Set `engagement.next_action` to first incomplete phase, or P5 `--strict` if only gaps remain

**Do not:** re-run `/understand`, re-grep repos, or rewrite conclusions unless a required table is literally empty.

### DELTA mode — procedure

Requires `manifest.yaml` with at least P0 complete. If not present, fall back to `FULL` with a warning.

1. Load `manifest.yaml`; for each `repos[]` entry run:
   ```bash
   git -C <repo-path> rev-parse HEAD
   ```
   Compare to `repos[].sha`. Build the **changed set** of repos where SHA differs.

2. Determine **affected phases** from the changed set:
   - **P0, P1**: re-run for every repo in the changed set
   - **P0.25**: re-run contract rows for changed repos only; carry forward unchanged repos' rows
   - **P2**: re-run if any Tier 0/1 repo changed (flow likely affected), **or** if step P0.25 added or
     removed any contract row for a changed repo at *any* tier — a low-tier repo gaining/losing a
     producer/consumer contract changes the flow diagram even when the repo itself isn't Tier 0/1
   - **P2b**: re-run if P2 re-ran and Datadog ✅
   - **P3**: re-run if any Tier 0/1 repo changed
   - **P3b**: re-run if P3 re-ran
   - **P4, P5**: always re-run after any upstream phase re-ran

3. Phases with no upstream changes keep their `complete` status in manifest unchanged.

4. At end: run `validate_manifest_yaml.py`; update `engagement.last_updated` and
   `engagement.next_action`.

### ADD_REPO mode — procedure

Requires `manifest.yaml` at `workspace_root` with `schema_version: 2` and `engagement.status` of
`IN_PROGRESS` or `FIRST_PASS_COMPLETE`. `new_repo_path` must resolve to a repo **not** present in
`manifest.repos[]` (match by `name`) — if it is present, stop and tell the user to use `DELTA` instead.

1. Classify the new repo ([repo-classification.md](../reference/repo-classification.md)), assign
   provisional tier.
2. Add a `manifest.repos[]` entry: `inventory: pending`, `understand: pending`, `deep_dive: pending`.
3. Run, scoped to the new repo only, at the same evidence/confidence bar as `FULL`:
   - P0 (inventory) — append repo census row, tech stack, config surface, repo relationships
   - P0.25 (contracts) — append this repo's producer/consumer rows to `API_CATALOG.md` /
     `EVENT_CATALOG.md`
   - P0.5 (mechanical) — run `/understand --full` for the new repo, merge into the existing
     `.understand-anything/domain-graph.json` via `/understand-domain` (do not regenerate other repos'
     graphs)
   - P1 (deep dive) — per-repo deep dive subsection, ownership card, initial smells
   - Session 0b squad enrichment — append one row to `SQUAD_MAP.md` for the new repo only
4. **Merge gate.** Before writing any P0/P1 row into a shared deliverable (`BOUNDED_CONTEXTS.md`,
   `DATA_OWNERSHIP.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`), check the new repo's claim against
   existing rows for the same entity/context/path:
   - **No overlap** → append normally.
   - **Overlap** (two repos both claim authoritative ownership of a table; a bounded context gains a
     repo that contradicts its existing definition; an API path has a different producer than already
     recorded) → do **not** merge that row. Instead:
     - Add a row to `RISK_MAP.md` § Merge Conflicts with both claims + evidence + confidence,
       `Status: open`
     - Add the same conflict to `UNKNOWNS.md`
     - Leave the owning phase (`p0` or `p1`) at `status: in_progress` in `manifest.yaml` — do **not**
       mark it `complete` while any `RISK_MAP.md` § Merge Conflicts row is `Status: open`
     - **Stop.** Report the conflict to the user; do not proceed to step 5 for the affected deliverable
       until it's resolved
5. Once new-repo P0–P1 merge is clean (no open conflicts, or the user explicitly accepts leaving them
   open), determine downstream re-synthesis using the **DELTA mode affected-phases rules above**,
   treating the new repo as the changed set of one:
   - P2 reruns if new repo is Tier 0/1
   - P2b reruns if P2 reran and Datadog ✅
   - P3 reruns if new repo is Tier 0/1
   - P3b reruns if P3 reran
   - P4, P5 **always** rerun
6. Run `validate_manifest_yaml.py --workspace-root <workspace_root> --check-content`; update
   `engagement.last_updated` and `engagement.next_action`.

**Do not:** re-run P0–P1 for repos already in `manifest.repos[]` (that's `DELTA`'s job if their SHA
changed); regenerate other repos' `/understand` graphs, only merge the new one in.

**Required outputs:**

| Output | Location | Required fields |
|--------|----------|-----------------|
| New repo entry | `manifest.repos[]` | name, branch, sha, tier, classification |
| Merge conflicts (if any) | `RISK_MAP.md` § Merge Conflicts | Both claims, evidence, confidence, status |
| Re-synthesized exec summary | `EXEC_SUMMARY.md` | Five questions + overall confidence recomputed including new repo |

## Required outputs

| Output | Source | If absent |
|--------|--------|-----------|
| `workspace_root` | User message or prompt | Ask user — cannot proceed |
| `workspace_layout` | Auto-detect or user-specified | Default to `sibling-repos` detection |
| `domain_name` | User message; confirm in Session 0 | Ask user |
| `delivery_mode` | User message | Default `QUICK` (no `manifest.yaml` yet) |
| `domain_pack` | User message (optional) | Skip — no pack merge |

## Environment constraints

- **Code-only** — no prod API calls, DB writes, deploys
- Analyze at **current checked-out branch HEAD** per repo — record `repo → branch → short SHA`
