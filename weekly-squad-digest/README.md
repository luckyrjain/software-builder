# weekly-squad-digest

**Combined squad status digest.** Reads **migration-program-manager**'s `migration_program_rollup.json`
and **cost-optimization-sprint-planner**'s `cost_optimization_sprint_rollup.json` — both
already-computed, squad-grouped rollup files — and combines them into one document. Neither producing
skill is invoked live; `squad`/`status`/`priority` are surfaced exactly as each already computed them.

## What it does

1. **Reads both rollup files** (or just one, if only one path is supplied) — a missing file is a
   reported gap, never a trigger to run the producing skill itself.
2. **Groups by squad**, `UNKNOWN` squad last — the same convention both producing skills already use.
3. **Splits each squad into two sub-sections** — Migration status and Cost optimization — never merged
   into one cross-metric ranking, since a migration gate status and a dollar figure aren't comparable.
4. **Flags stale items** (older than `staleness_warning_days`, default 14) — display-only, never changes
   a computed `status`.
5. **Writes `WEEKLY_SQUAD_DIGEST.md`** — the terminal artifact; delivery to a specific channel/audience
   is an external handler's job (see [SETUP.md](SETUP.md)), the same pattern backlog-runner's morning
   summary uses.

## When to use

| Use weekly-squad-digest | Use instead |
|--------------------------|--------------|
| Scheduled combined squad-status digest | Fresh migration rollup only → **migration-program-manager** directly |
| "What does this squad's status look like across migration + cost?" | Fresh cost/waste sweep only → **cost-optimization-sprint-planner** directly |

## Invocation example

```
rollup_manifest: {migration_rollup_path: ./migration_program_rollup.json, cost_rollup_path: ./cost_optimization_sprint_rollup.json}
```

## What you get

`WEEKLY_SQUAD_DIGEST.md` — format spec: [reference/report-format.md](reference/report-format.md).

## Install

```bash
cd ai-skills
make install-weekly-squad-digest
```

Restart Cursor. Requires **migration-program-manager** and **cost-optimization-sprint-planner** installed
too (the make target chains both automatically) — this skill only reads their output, but expects it to
already exist.

## Related skills

- **migration-program-manager** — produces `migration_program_rollup.json`; this skill only reads it
- **cost-optimization-sprint-planner** — produces `cost_optimization_sprint_rollup.json`; this skill only
  reads it
- **squad-map** — the ultimate source of the `squad`/`squad_confidence` fields both rollups already
  carry; this skill never invokes squad-map itself

Agent instructions: [SKILL.md](SKILL.md).
