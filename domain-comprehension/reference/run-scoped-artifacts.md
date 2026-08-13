# Run-scoped artifact namespace

Domain-comprehension must not clutter `workspace_root` or let parallel runs clobber each other.

## Default layout

For a normal run, resolve `scope.artifact_root` to:

```text
{workspace_root}/docs/domain-comprehension/{domain_slug}/
```

`domain_slug` is a single safe path segment derived from the domain name: lowercase letters/digits plus
`-`; replace other character runs with `-`, trim leading/trailing `-`, and reject an empty result. Never
allow `/`, `\\`, an absolute path, or `..` to enter the derived path.

Create every missing parent directory before writing. All domain-specific Markdown/config deliverables —
including `domain-config.yaml`, `EXEC_SUMMARY.md`, `PRD.md`, `{map_file}`, catalogs, graphs, risks,
unknowns/omissions, runbook, and progress — live under this directory.

`manifest.yaml` stays at `workspace_root` because it is the machine completion/resume locator. Record the
relative path (`docs/domain-comprehension/{domain_slug}`) as `engagement.artifact_root`.

The standalone **squad-map** skill may maintain a shared `workspace_root/SQUAD_MAP.md`. Domain-
comprehension must copy the relevant snapshot to `{artifact_root}/SQUAD_MAP.md`; the artifact-root copy is
the canonical domain-comprehension artifact and the one referenced by its manifest.

## Path boundary

`scope.artifact_root`, `engagement.artifact_root`, `engagement.map_file`, and every manifest artifact or
diagram `path` must be relative and must not contain `..`. Treat both `/` and `\\` as separators when
validating so a Windows-style traversal string cannot bypass a Linux CI check. The manifest validator
enforces this boundary.

## Explicit override and parallel runs

A caller may provide another **relative** `scope.artifact_root` that satisfies the same path boundary.
For parallel runs append a stable safe run id, for example:

```text
docs/domain-comprehension/{domain_slug}/{run_id}/
```

`run_id` may be an ISO-8601 UTC timestamp (`20260813T060000Z`) or a caller-supplied slug. A caller-supplied
run id follows the same single-segment slug rule as `domain_slug`.

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

`RESUME` reads root `manifest.yaml`, validates `engagement.artifact_root`, then uses it to locate all
domain-specific artifacts. Never fall back to writing those files at workspace root when the directory
is missing; create the recorded directory instead. `DELTA`, `ADD_REPO`, and `PROPOSAL_CHECK` use the same
manifest-first location resolution.
