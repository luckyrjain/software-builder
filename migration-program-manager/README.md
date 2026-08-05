# migration-program-manager

**Org-wide migration rollup.** Turns many single-workspace `MIGRATION_STATUS.yaml` files (from
**mysql-to-postgres-sql**) into one squad-grouped view, joined against **squad-map**'s `SQUAD_MAP.md`.
**Pure read-only aggregator** — never invokes either wrapped skill live, only reads their existing output
files, so there's nothing to gate/confirm.

## What it does

1. **Reads `MIGRATION_STATUS.yaml`** from every workspace in `program_manifest` — a workspace with none
   yet is reported as a gap, not a crash.
2. **Reads `SQUAD_MAP.md`** (if present) to join each service to a squad — a workspace with none yet
   joins its services as `squad: UNKNOWN`, with a note to run squad-map directly; this skill never
   triggers that run itself.
3. **Tracks staleness itself** — `MIGRATION_STATUS.yaml` has no per-gate timestamp, so this skill persists
   its own state across runs (`gate_signature` + `first_observed_at` per service) to compute "unchanged
   for N days."
4. **Ranks and groups by squad** — blocked first, then stalled (past `staleness_threshold_days`), then
   in-progress, then done.
5. **Writes `MIGRATION_PROGRAM_REPORT.md`** (human-readable) and **`migration_program_rollup.json`**
   (machine-readable — a future Weekly Squad Digest reuses this directly).

## When to use

| Use migration-program-manager | Use instead |
|----------------------------------|--------------|
| "Migration status across all repos" / org-wide rollup | One workspace's own status → **mysql-to-postgres-sql** directly |
| Escalating stalled/blocked services by squad | Squad/repo ownership lookup only → **squad-map** directly |

## Invocation example

```
program_manifest: [{workspace_root: ./services/api-disbursement}, {workspace_root: ./services/api-payouts}]
staleness_threshold_days: 14
```

## What you get

`MIGRATION_PROGRAM_REPORT.md` + `migration_program_rollup.json` — format spec:
[reference/report-format.md](reference/report-format.md).

## Install

```bash
cd ai-skills
make install-migration-program-manager
```

Restart Cursor. Requires **Python 3 + PyYAML** for `scripts/aggregate_migration_status.py`. Requires
**mysql-to-postgres-sql** and **squad-map** installed too (the make target chains both automatically) —
this skill only reads their output, but expects it to already exist.

## Related skills

- **mysql-to-postgres-sql** — produces `MIGRATION_STATUS.yaml`; this skill only reads and aggregates it
- **squad-map** — produces `SQUAD_MAP.md`; this skill only reads it for the join, never invokes squad-map
- **pr-review** — reviews the migration MRs `mr_url` points to; not invoked by this skill

Agent instructions: [SKILL.md](SKILL.md).
