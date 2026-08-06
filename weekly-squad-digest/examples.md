# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `rollup_manifest: {migration_rollup_path: ..., cost_rollup_path: ...}` | Inputs → Run digest → both rollups read, grouped by squad then metric_type → `WEEKLY_SQUAD_DIGEST.md` |
| 2 | `rollup_manifest` with only `migration_rollup_path` set | Cost rollup row appears in Rollup gaps ("Not supplied"); digest still renders from migration data alone |
| 3 | A supplied rollup path doesn't exist on disk | Recorded in Rollup gaps ("File not found... run `<producing skill>` first"); the other rollup, if readable, still renders |
| 4 | An item's `last_updated` is older than `staleness_warning_days` | Flagged with its age in Notes — `status` itself unchanged |
| 5 | The same squad has items in both rollups | Two sub-sections under one squad heading — Migration status and Cost optimization, never merged |
| 6 | `rollup_manifest` has neither path set | Inputs HARD STOP — ask, no Run digest |
| 7 | "What's our migration status?" | **Wrong skill** → migration-program-manager directly |
| 8 | "Where's the cost waste?" | **Wrong skill** → cost-optimization-sprint-planner directly |

---

### Scenario: Both rollups present — happy path

**Caller:** `rollup_manifest: {migration_rollup_path: ./migration_program_rollup.json,
cost_rollup_path: ./cost_optimization_sprint_rollup.json}`

**Agent:**

1. Inputs — both paths parsed
2. Run digest § 1 — both files read as `org_rollup_item` arrays, `squad`/`status`/`priority` taken as-is
3. Run digest § 2 — grouped by squad, then split by `metric_type` within each squad
4. Run digest § 3 — staleness computed per item against the 14-day default
5. Run digest § 4 — digest written

**Expected fragment:**

```
# Weekly squad digest — 2026-08-05

**Rollups read:** `./migration_program_rollup.json` · `./cost_optimization_sprint_rollup.json`

## disbursement

### Migration status

| Service | Status | Priority | Notes |
|---------|--------|----------|-------|
| api-disbursement | blocked | P0 | — |

### Cost optimization

| Service | Monthly savings | Status | Priority | Notes |
|---------|------------------|--------|----------|-------|
| api-disbursement | $340.00 | READY | P1 | — |
```

---

### Scenario: Only one rollup supplied — the other is a gap, not a crash

**Caller:** `rollup_manifest: {migration_rollup_path: ./migration_program_rollup.json}`

**Agent:** Run digest § 1 reads only the migration rollup; the cost rollup is recorded in Rollup gaps as
"Not supplied in rollup_manifest." The digest still renders every migration item, grouped by squad —
never blocked on the missing cost rollup.

**Expected fragment:**

```
## Rollup gaps

| Rollup | Reason |
|--------|--------|
| cost_optimization_sprint_rollup.json | Not supplied in rollup_manifest |
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "What's our migration status?"

**Agent:** Routes to **migration-program-manager** directly — this is a single-source, on-demand
question, not the combined scheduled digest (see [SKILL.md](SKILL.md) § When to use / NOT to use).
