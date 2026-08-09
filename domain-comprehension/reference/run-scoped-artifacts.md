# Run-scoped artifact namespace

Large engagements and parallel runs must not clobber each other's deliverables at `workspace_root`.

## Default layout

When `domain-config.yaml` `scope.artifact_root` is unset, use:

```text
{workspace_root}/.domain-comprehension/{run_id}/
```

- `run_id` — ISO-8601 UTC timestamp at Session 0 start (`20260809T060000Z`) or caller-supplied slug.
- **Phase deliverables** for this run (`EXEC_SUMMARY.md`, `{map_file}`, diagrams, exports) live under
  `artifact_root`.

**`manifest.yaml` stays at `workspace_root`** — it is the machine completion gate and
`validate_manifest_yaml.py` resolves artifact paths relative to `workspace_root`. Record
`engagement.artifact_root` in the manifest when deliverables are namespaced under a run directory.

## Smaller phase packets

For `delivery_mode: QUICK` or when `repos_in_scope` > 50, emit **phase packets** — one subdirectory per
completed phase instead of one monolithic `{map_file}` edit:

```text
{artifact_root}/packets/P0-inventory.md
{artifact_root}/packets/P1-deep-dives.md
...
```

Phase 5 merges packets into the canonical deliverables under `artifact_root`. Packets are working notes;
`manifest.yaml` at `workspace_root` remains the completion gate.

## Shared workspace files

`SQUAD_MAP.md` at `workspace_root` is **shared** — Session 0b still updates it per squad-map's own rules.
Never write comprehension deliverables into individual application repos unless the user explicitly sets
`scope.artifact_root` inside a repo.

## Resume / DELTA

`RESUME` mode reads `manifest.yaml` from `workspace_root` and uses `engagement.artifact_root` (when set)
to locate prior deliverables — do not assume every artifact path is always directly under `workspace_root`.
