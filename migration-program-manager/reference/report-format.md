# MIGRATION_PROGRAM_REPORT.md + migration_program_rollup.json format

**Normative.** The exact structure [workflow/run-rollup.md](../workflow/run-rollup.md) § 3 must produce.

## `MIGRATION_PROGRAM_REPORT.md` structure (order fixed)

```markdown
# Migration program — <date>

**Workspaces:** <N scanned, M with gaps> · **Services:** <total> · **Blocked:** <count> · **Stalled:** <count>

## <squad name>

### Blocked

| Service | Workspace | Failing gate | MR | Notes |
|---------|-----------|--------------|-----|-------|
| <service> | <workspace_root> | scan_gate \| shadow_compare \| config_cutover | <mr_url or —> | <notes> |

### Stalled (unchanged ≥ <staleness_threshold_days> days)

| Service | Workspace | Staleness | Current gates | MR |
|---------|-----------|-----------|-----------------|-----|
| <service> | <workspace_root> | <N> days | <scan_gate>/<shadow_compare>/<config_cutover> | <mr_url or —> |

### In progress

| Service | Workspace | Gates | MR |
|---------|-----------|-------|-----|
| <service> | <workspace_root> | <scan_gate>/<shadow_compare>/<config_cutover> | <mr_url or —> |

### Done

| Service | Workspace |
|---------|-----------|
| <service> | <workspace_root> |

<Repeat per squad, in any stable order. Squads with nothing in one sub-section omit that sub-section
(never render an empty table), but a squad with at least one service always gets its own heading.>

## UNKNOWN squad

<Same four sub-sections, for every service that couldn't be joined to a squad — always rendered last,
never silently merged into a named squad.>

## Workspace gaps

| Workspace | Reason |
|-----------|--------|
| <workspace_root> | MIGRATION_STATUS.yaml not found — run mysql-to-postgres-sql first |
| <workspace_root> | No SQUAD_MAP.md at <path> — run squad-map directly |
```

## `migration_program_rollup.json` shape

A flat JSON array of `org_rollup_item` objects (per
[org-rollup-schema.md](../../docs/skill-framework/shared/org-rollup-schema.md)), each with an added
`staleness_days` field (this skill's own computed value, not part of the shared schema's base shape —
schemas can be extended per-consumer as long as the base fields stay intact). Written so
[weekly-squad-digest](../../weekly-squad-digest/SKILL.md) can read this file directly instead of
re-running the aggregator.

## Rules

- **Each service appears in exactly one of the four sub-sections (Blocked/Stalled/In progress/Done),
  chosen by its persisted `status` field from `migration_program_rollup.json` — never by independently
  re-checking `value.scan_gate`/`value.shadow_compare`/`value.config_cutover` for `fail` or
  `staleness_days` against `staleness_threshold_days` while rendering.** `status` is already mutually
  exclusive (`blocked` always wins over staleness — see [workflow/run-rollup.md](../workflow/run-rollup.md)
  § 2); a blocked service's `staleness_days` can independently exceed the threshold too (its failing gate
  just hasn't changed in a while), which would otherwise put the same service in both the Blocked and
  Stalled tables.
- **Every `program_manifest` entry appears** — either contributing services to the per-squad sections, or
  as a row in Workspace gaps (or both, if some services parsed and others in the same workspace didn't).
- **`squad: UNKNOWN` services are never dropped and never guessed into a named squad** — their own section,
  always last.
- **A blocked service always names which gate failed** — not just "blocked," the specific
  `scan_gate`/`shadow_compare`/`config_cutover` value that's `fail`.
- **Staleness is this skill's own computed value** (see [SKILL.md](../SKILL.md) § Staleness tracking in
  the design spec) — never claim `MIGRATION_STATUS.yaml` itself records a timestamp it doesn't.
