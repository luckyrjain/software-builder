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
| 6 | A service has `scan_gate: fail` (blocked) and its gate signature has also been unchanged past `staleness_threshold_days` | Stays `status: blocked` only — never additionally rendered into Stalled (Run rollup § 2's guardrail) |
| 7 | `program_manifest` empty, or `staleness_threshold_days` absent | Inputs HARD STOP — ask, no Run rollup |
| 8 | A blocked service's `value.mr_url` is populated | Optional escalation → **pr-review**, reusing mysql-to-postgres-sql's own handoff template — offered, never auto-invoked (this skill never calls another skill live) |
| 9 | "What's the migration status for this one repo?" | **Wrong skill** → mysql-to-postgres-sql directly |
| 10 | "Who owns api-disbursement?" | **Wrong skill** → squad-map directly |

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

## `disbursement`

### Blocked

| Service | Workspace | Failing gate | MR | Notes |
|---------|-----------|--------------|-----|-------|
| `api-disbursement` | `./api-disbursement` | scan_gate | — | — |

## `payouts`

### In progress

| Service | Workspace | Gates | MR |
|---------|-----------|-------|-----|
| `api-payouts` | `./api-payouts` | pass/pending/pending | — |
```

---

### Scenario: Three-workspace manifest with an explicit `squad_map_path` override, staleness threshold reached exactly

**Caller:** `program_manifest: [{workspace_root: ./api-disbursement}, {workspace_root: ./api-payouts,
squad_map_path: ./shared-maps/PAYOUTS_SQUAD_MAP.md}, {workspace_root: ./api-refunds}]`,
`staleness_threshold_days: 14`

The `payouts` entry supplies its own `squad_map_path` — a shared map living outside that workspace root —
so [workflow/inputs.md](workflow/inputs.md)'s default (`<workspace_root>/SQUAD_MAP.md`) never applies to
it, while `disbursement` and `refunds` still resolve the default path. `api-refunds`'s `scan_gate:
pending`/`shadow_compare: pending`/`config_cutover: pending` gate signature has been unchanged since
`first_observed_at` exactly 14 days ago, per `migration_program_state.json` from the prior run.

**Agent:**

1. Inputs — three entries normalized; `payouts` keeps its explicit `squad_map_path`, the other two default
2. Run rollup § 1 — `api-refunds`'s persisted state loads; `now − first_observed_at` = 14 days, equal to
   `staleness_threshold_days`
3. Run rollup § 1 step 4 — `derive_status` says `in_progress`; staleness escalation uses `staleness_days
   >= staleness_threshold_days`, so the boundary itself (14 ≥ 14) is inclusive — this is the run where
   `api-refunds` first flips to `stalled`, not one run later
4. Run rollup § 3 — report renders `api-refunds` under Stalled, staleness shown as exactly the threshold

**Expected fragment:**

```
## `refunds`

### Stalled (unchanged ≥ 14 days)

| Service | Workspace | Staleness | Current gates | MR |
|---------|-----------|-----------|-----------------|-----|
| `api-refunds` | `./api-refunds` | 14 days | pending/pending/pending | — |
```

---

### Scenario: Mixed-status aggregation — a service both blocked and stale at once, guardrail exercised

**Caller:** Same manifest as the happy-path scenario, one workspace, squad `disbursement`, three services:
`api-gateway` (`scan_gate: fail`, gate signature unchanged 20 days), `api-ledger` (`scan_gate: pass`,
`shadow_compare: pending`, `config_cutover: pending`, gate signature also unchanged 20 days),
`api-refunds` (`scan_gate: pass`, `shadow_compare: pass`, `config_cutover: done`). `staleness_threshold_days: 14`.

**Agent:**

1. Run rollup § 1 step 4 — `derive_status` returns `blocked` for `api-gateway` (a `fail` present),
   `in_progress` for `api-ledger`, `done` for `api-refunds`; staleness is computed for **all three**
   independently of status (`api-gateway` and `api-ledger` both land on 20 days, past the 14-day
   threshold) — but the staleness escalation (`status == "in_progress" and staleness_days >=
   threshold` → `stalled`) only ever fires on an `in_progress` status, so `api-gateway`'s `status` stays
   `blocked` even though its own `staleness_days` (20) independently clears the threshold too
2. Run rollup § 2 — **groups strictly by each item's already-finalized `status` field** — `api-gateway`
   renders once, under Blocked, never re-checked against `staleness_days` at render time and never
   duplicated into Stalled; `api-ledger` renders once, under Stalled; `api-refunds` renders once, under
   Done. This is the "never re-derive status" guardrail from
   [workflow/run-rollup.md](workflow/run-rollup.md) § 2 and
   [reference/report-format.md](reference/report-format.md)'s Rules section, doing real work here — a
   render pass that instead re-checked "any gate `fail`" and "staleness ≥ threshold" as two independent
   conditions would have put `api-gateway` in both tables

**Expected fragment:**

```
## `disbursement`

### Blocked

| Service | Workspace | Failing gate | MR | Notes |
|---------|-----------|--------------|-----|-------|
| `api-gateway` | `./api-disbursement` | scan_gate | — | — |

### Stalled (unchanged ≥ 14 days)

| Service | Workspace | Staleness | Current gates | MR |
|---------|-----------|-----------|-----------------|-----|
| `api-ledger` | `./api-disbursement` | 20 days | pass/pending/pending | — |

### Done

| Service | Workspace |
|---------|-----------|
| `api-refunds` | `./api-disbursement` |
```

`api-gateway` does not appear a second time under Stalled, despite its own `staleness_days` also being 20
— its `migration_program_rollup.json` entry carries `"status": "blocked", "staleness_days": 20`
simultaneously, and the report renders it into exactly the one section its `status` names.

---

### Scenario: Missing SQUAD_MAP.md — joins as UNKNOWN, squad-map never invoked (degraded path)

**Caller:** Same manifest as the happy-path scenario, but `./api-payouts` has no `SQUAD_MAP.md`.

**Agent:** Run rollup § 1 records the gap and joins `api-payouts` as `squad: UNKNOWN` — this skill never
triggers a fresh squad-map run to fill it (see [SKILL.md](SKILL.md) § Why no gate policy).

**Expected fragment:**

```
## UNKNOWN squad

### In progress

| Service | Workspace | Gates | MR |
|---------|-----------|-------|-----|
| `api-payouts` | `./api-payouts` | pass/pending/pending | — |

## Workspace gaps

| Workspace | Reason |
|-----------|--------|
| `./api-payouts` | No SQUAD_MAP.md at ./api-payouts/SQUAD_MAP.md — run squad-map directly |
```

---

### Scenario: Cross-skill handoff — blocked MR to pr-review

**Caller:** Same manifest as the happy-path scenario; `api-disbursement`'s `MIGRATION_STATUS.yaml` row has
`scan_gate: fail` and `mr_url: https://gitlab.example.com/acme/disbursement/api-disbursement/-/merge_requests/482`.

**Agent:**

1. Run rollup § 1 — `scan_gate: fail` makes `derive_status` return `blocked`; `value.mr_url` is carried
   through verbatim into the `org_rollup_item` (never re-derived or reformatted)
2. Run rollup § 3 — the Blocked table names the failing gate and links the MR, per
   [reference/report-format.md](reference/report-format.md)
3. Per [SKILL.md](SKILL.md) § Cross-skill escalation, a blocked service's migration MR needing review is
   an optional escalation to **pr-review** — this skill reuses mysql-to-postgres-sql's own handoff
   template for the same MR/service rather than inventing a second one (see
   [cross-skill-escalation.md](../docs/skill-framework/shared/cross-skill-escalation.md) row "Migration MR
   needs review"). It is offered after the report renders, not auto-invoked — this skill never calls
   another skill live (see [SKILL.md](SKILL.md) § Why no gate policy)

**Expected fragments:**

```
## `disbursement`

### Blocked

| Service | Workspace | Failing gate | MR | Notes |
|---------|-----------|--------------|-----|-------|
| `api-disbursement` | `./api-disbursement` | scan_gate | https://gitlab.example.com/acme/disbursement/api-disbursement/-/merge_requests/482 | — |
```

```
**Handoff → pr-review**
- Service: api-disbursement
- Trigger: blocked scan_gate — migration MR needs review
- Evidence: MR !482 — https://gitlab.example.com/acme/disbursement/api-disbursement/-/merge_requests/482
- Ask: "Review MR !482 for MySQL→PostgreSQL migration in api-disbursement"
```

`squad_confidence: HIGH` for `api-disbursement` (exact `Repo` match in `SQUAD_MAP.md`) — carried in the
rollup item alongside the handoff, so the receiving pr-review invocation isn't the first place squad
context appears.

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "What's the migration status for this one repo?"

**Agent:** Routes to **mysql-to-postgres-sql** directly — this is a single-workspace question, not an
org-wide rollup (see [SKILL.md](SKILL.md) § When to use / NOT to use).
