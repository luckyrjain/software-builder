# Evidence summary (normative)

**Human:** `EXEC_SUMMARY.md` § Evidence summary. **Machine:** `manifest.yaml` `evidence_summary`.

Updated at **end of every phase**. Provides objective completeness — not subjective progress.

## Required counters

| Counter | Definition |
|---------|------------|
| `repos_scanned` | Repos with `inventory: complete` in manifest |
| `repos_in_scope` | Repos in scope (not excluded in KNOWN_OMISSIONS) |
| `files_inspected` | Distinct source files with evidence citations |
| `runtime_edges_confirmed` | P2b `CONFIRMED` hops |
| `events_verified` | Event catalog rows with exercise ≠ `unknown` |
| `apis_verified` | API catalog rows with exercise ≠ `unknown` |
| `unknowns_count` | Rows in `UNKNOWNS.md` |
| `omissions_count` | Rows in `KNOWN_OMISSIONS.md` |

## Display template (EXEC_SUMMARY)

```markdown
## Evidence summary

| Metric | Count | Last updated |
|--------|------:|--------------|
| Repositories scanned | 18 / 22 in scope | 2026-07-01 |
| Files inspected | 241 | |
| Runtime edges confirmed | 32 / 45 total | |
| Events verified | 51 | |
| APIs verified | 29 | |
| Unknowns | 7 | |
| Known omissions | 4 | |
```

## Manifest block

```yaml
evidence_summary:
  repos_scanned: 0
  repos_in_scope: 0
  files_inspected: 0
  runtime_edges_confirmed: 0
  events_verified: 0
  apis_verified: 0
  unknowns_count: 0
  omissions_count: 0
  last_updated: ""
```

## P5 gate

All counters populated with integers ≥ 0, or `UNKNOWN` with reason in `UNKNOWNS.md` for that metric.

`files_inspected` and `repos_scanned` must be monotonic non-decreasing within an engagement.
