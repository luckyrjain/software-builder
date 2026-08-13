# Run-scoped artifact namespace

Domain-comprehension must not clutter `workspace_root` or let parallel runs clobber each other.

## Default layout

For a normal run, resolve `scope.artifact_root` to:

```text
{workspace_root}/docs/domain-comprehension/{domain_slug}/
```

Create every missing parent directory before writing. All domain-specific Markdown/config deliverables —
including `domain-config.yaml`, `EXEC_SUMMARY.md`, `PRD.md`, `{map_file}`, catalogs, graphs, risks,
unknowns/omissions, runbook, and progress — live under this directory.

`manifest.yaml` stays at `workspace_root` because it is the machine completion/resume locator. Record the
relative path (`docs/domain-comprehension/{domain_slug}`) as `engagement.artifact_root`.

`SQUAD_MAP.md` is also allowed at workspace root because it is a shared squad-map artifact used across
skills, not a domain-specific comprehension document.

## Explicit override and parallel runs

A caller may provide another **relative** `scope.artifact_root`; never accept an absolute path or `..`
segments. For parallel runs append a stable run id, for example:

```text
docs/domain-comprehension/{domain_slug}/{run_id}/
```

`run_id` may be an ISO-8601 UTC timestamp (`20260813T060000Z`) or a caller-supplied slug.

## Smaller phase packets

For `delivery_mode: QUICK` or `repos_in_scope > 50`, phase packets live under the same artifact root:

```text
{artifact_root}/packets/P0-inventory.md
{artifact_root}/packets/P1-deep-dives.md
...
```

P5 merges packets into canonical deliverables under `artifact_root`; packets are working notes, not a
second source of truth.

## Resume / DELTA

`RESUME` reads root `manifest.yaml`, then uses `engagement.artifact_root` to locate all domain-specific
artifacts. Never fall back to writing those files at workspace root when the directory is missing; create
the recorded directory instead.
