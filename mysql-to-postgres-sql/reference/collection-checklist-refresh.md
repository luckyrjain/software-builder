# Refresh domain pack file checklists

Domain pack markdown is a **curated** P0/P1 list. After PRs land, refresh from scan output so the checklist does not rot.

## Regenerate hit report

From skill root (or installed `~/.cursor/skills/mysql-to-postgres-sql/`):

```bash
scripts/scan-mysql-dialect.sh /path/to/workspace/neo 2>&1 | tee /tmp/mysql-dialect-hits.txt
# exit 1 expected when hits remain — output lists file:line:match
```

Or always emit a report (even on success):

```bash
scripts/scan-report.sh /path/to/workspace
```

## Manual merge into pack

1. Group hits by service directory and priority (P0 = SMS cooling / `TIMESTAMPDIFF`; P1 = `DATE_FORMAT` / `CAST AS CHAR`).
2. Update the domain pack tables — remove rows when scan clean for that file.
3. Mirror summary in workspace `MYSQL_TO_PG_SQL_REWRITES.md` if present (domain-comprehension artifact).
4. Update `MIGRATION_STATUS.yaml` per-service `scan_gate` rows.

Do not auto-overwrite pack markdown in CI without human review — compliance tiers need judgment.
