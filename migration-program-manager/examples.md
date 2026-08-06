# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `program_manifest: [{workspace_root: ./api-disbursement}, {workspace_root: ./api-payouts}]`, `staleness_threshold_days: 14` | Inputs → Run rollup → both workspaces parsed and joined → `MIGRATION_PROGRAM_REPORT.md` + `migration_program_rollup.json` |
| 2 | A workspace has no `MIGRATION_STATUS.yaml` yet | Recorded in Workspace gaps — not a HARD STOP, every other workspace still processed |
| 3 | A workspace has no `SQUAD_MAP.md` | Its services join as `squad: UNKNOWN` — squad-map is never invoked to fill the gap |
| 4 | A service's gate signature is unchanged across 2 runs spanning 20 days, threshold is 14 | Escalated as stalled on the second run |
| 5 | A service's gate signature changed since the last run | Staleness resets to 0 — no carryover from before the change |
| 6 | `program_manifest` empty, or `staleness_threshold_days` absent | Inputs HARD STOP — ask, no Run rollup |
| 7 | "What's the migration status for this one repo?" | **Wrong skill** → mysql-to-postgres-sql directly |
| 8 | "Who owns api-disbursement?" | **Wrong skill** → squad-map directly |

---

### Scenario: Normal program rollup — happy path

**Caller:** `program_manifest: [{workspace_root: ./api-disbursement}, {workspace_root: ./api-payouts}]`,
`staleness_threshold_days: 14`

**Agent:**

1. Inputs — manifest parsed, threshold set
2. Run rollup § 1 — `MIGRATION_STATUS.yaml` and `SQUAD_MAP.md` read from both workspaces; joined into
   `org_rollup_item`s; staleness computed against `migration_program_state.json` (first run — all start
   at 0)
3. Run rollup § 2 — grouped by squad: `disbursement` has 1 blocked (scan_gate fail), `payouts` has 1
   in-progress
4. Run rollup § 3 — report + rollup JSON written

**Expected fragment:**

```
# Migration program — 2026-08-05

**Workspaces:** 2 scanned, 0 with gaps · **Services:** 2 · **Blocked:** 1 · **Stalled:** 0

## disbursement

### Blocked

| Service | Workspace | Failing gate | MR | Notes |
|---------|-----------|--------------|-----|-------|
| api-disbursement | ./api-disbursement | scan_gate | — | — |

## payouts

### In progress

| Service | Workspace | Gates | MR |
|---------|-----------|-------|-----|
| api-payouts | ./api-payouts | pass/pending/pending | — |
```

---

### Scenario: Missing SQUAD_MAP.md — joins as UNKNOWN, squad-map never invoked

**Caller:** Same manifest, but `./api-payouts` has no `SQUAD_MAP.md`.

**Agent:** Run rollup § 1 records the gap and joins `api-payouts` as `squad: UNKNOWN` — this skill never
triggers a fresh squad-map run to fill it (see [SKILL.md](SKILL.md) § Why no gate policy).

**Expected fragment:**

```
## UNKNOWN squad

### In progress

| Service | Workspace | Gates | MR |
|---------|-----------|-------|-----|
| api-payouts | ./api-payouts | pass/pending/pending | — |

## Workspace gaps

| Workspace | Reason |
|-----------|--------|
| ./api-payouts | No SQUAD_MAP.md at ./api-payouts/SQUAD_MAP.md — run squad-map directly |
```

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "What's the migration status for this one repo?"

**Agent:** Routes to **mysql-to-postgres-sql** directly — this is a single-workspace question, not an
org-wide rollup (see [SKILL.md](SKILL.md) § When to use / NOT to use).
