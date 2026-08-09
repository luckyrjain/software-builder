# Run-scoped artifact namespace

Large engagements and parallel runs must not clobber each other's deliverables at `workspace_root`.

## Default layout

When `domain-config.yaml` `scope.artifact_root` is unset, use:

```text
{workspace_root}/.domain-comprehension/{run_id}/
```

- `run_id` — ISO-8601 UTC timestamp at Session 0 start (`20260809T060000Z`) or caller-supplied slug.
- All phase deliverables for **this run** live under `artifact_root` — `manifest.yaml`, `EXEC_SUMMARY.md`,
  `{map_file}`, diagrams, and exports.

## Smaller phase packets

For `delivery_mode: QUICK` or when `repos_in_scope` > 50, emit **phase packets** — one subdirectory per
completed phase instead of one monolithic `{map_file}` edit:

```text
{artifact_root}/packets/P0-inventory.md
{artifact_root}/packets/P1-deep-dives.md
...
```

Phase 5 merges packets into the canonical deliverables under `artifact_root`. Packets are working notes;
`manifest.yaml` remains the completion gate.

## Shared workspace files

`SQUAD_MAP.md` at `workspace_root` is **shared** — Session 0b still updates it per squad-map's own rules.
Never write comprehension deliverables into individual application repos unless the user explicitly sets
`scope.artifact_root` inside a repo.

## Resume / DELTA

`RESUME` mode reads `manifest.yaml` from the prior `artifact_root` path recorded in
`engagement.prior_artifact_root` — do not assume deliverables always live at `workspace_root`.
