# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `rollup_manifest: {migration_rollup_path: ..., cost_rollup_path: ...}` | Inputs → Run digest → both rollups read, grouped by squad then metric_type → `WEEKLY_SQUAD_DIGEST.md` |
| 2 | `rollup_manifest` with only `migration_rollup_path` set | Cost rollup row appears in Rollup gaps ("Not supplied"); digest still renders from migration data alone |
| 3 | A supplied rollup path doesn't exist on disk | Recorded in Rollup gaps ("File not found... run `<producing skill>` first"); the other rollup, if readable, still renders |
| 4 | A migration item has a `staleness_days` value | Used directly for the staleness flag (per-service signal) — never a `last_updated`-derived age, which is rollup-run-level for migration items |
| 5 | A cost item's `last_updated` is older than `staleness_warning_days` | Flagged with its age in Notes — `status` itself unchanged |
| 6 | The same squad has items in both rollups | Two sub-sections under one squad heading — Migration status and Cost optimization, never merged |
| 7 | The same `service` appears in both rollups under different squads | Each row's Notes cross-references the other section/squad — never silently presented as two unrelated services |
| 8 | `rollup_manifest` has neither path set | Inputs HARD STOP — ask, no Run digest |
| 9 | "What's our migration status?" | **Wrong skill** → migration-program-manager directly |
| 10 | "Where's the cost waste?" | **Wrong skill** → cost-optimization-sprint-planner directly |

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

| Service | Status | Priority | Confidence | Notes |
|---------|--------|----------|------------|-------|
| api-disbursement | blocked | P0 | HIGH | — |

### Cost optimization

| Service | Monthly savings | Status | Priority | Confidence | Notes |
|---------|------------------|--------|----------|------------|-------|
| api-disbursement | $340.00 | READY | P1 | HIGH | — |
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

### Scenario: Same service, different squads across the two rollups

**Caller:** Both rollups supplied; `api-legacy-ledger` appears in `migration_program_rollup.json` with
`squad: payments` and in `cost_optimization_sprint_rollup.json` with `squad: collections` — a real,
expected case, since the two rollups resolve `squad` via different join mechanisms (see
[org-rollup-schema.md § 3](../docs/skill-framework/shared/org-rollup-schema.md#3-join-key-squad-map-is-the-only-authoritative-source)).

**Agent:** Run digest § 2 step 4 detects the disagreement and cross-references both rows — neither squad
is treated as "correct."

**Expected fragment:**

```
## payments

### Migration status

| Service | Status | Priority | Confidence | Notes |
|---------|--------|----------|------------|-------|
| api-legacy-ledger | done | — | MEDIUM | also in Cost optimization under `collections` |

## collections

### Cost optimization

| Service | Monthly savings | Status | Priority | Confidence | Notes |
|---------|------------------|--------|----------|------------|-------|
| api-legacy-ledger | $120.00 | READY | P2 | MEDIUM | also in Migration status under `payments` |
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "What's our migration status?"

**Agent:** Routes to **migration-program-manager** directly — this is a single-source, on-demand
question, not the combined scheduled digest (see [SKILL.md](SKILL.md) § When to use / NOT to use).
