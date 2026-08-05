# mysql-to-postgres-sql

**MySQL → PostgreSQL SQL rewrite** skill for Cursor. Audits native SQL and JDBC/config for MySQL-only
dialect, rewrites incompatible fragments, and gates merges with `scripts/scan-mysql-dialect.sh`.

Auto-invokes when you ask about MySQL scrub, `jdbc:postgresql` migration, Python/Node driver cutover, or domain-pack P0/P1 SQL rewrites.

**Single-service vs. org-wide scrub:** scanning one service and rewriting what the gate flags is a
5–10 minute loop — no MCP, just `rg`. Tracking a whole org's cutover (`MIGRATION_STATUS.yaml` fleet
rollup, domain packs, shadow-migration comparisons across many services) is real project work, not a
one-shot command. Start with a single-service scan; only reach for the fleet-tracking pieces once
you're coordinating more than one service's cutover.

## What it does

1. **Scans** — `scripts/scan-mysql-dialect.sh` over `.java`, `.php`, `.sql`, `.py`, `.js`, `.ts`
2. **Classifies** — P0 compliance (SMS cooling), P1 core reads, P2 legacy PHP, portable (dialect only)
3. **Rewrites** — [function-translations.md](reference/function-translations.md) (every scan pattern documented)
4. **Config** — Java JDBC, [python-migration.md](reference/python-migration.md), [nodejs-migration.md](reference/nodejs-migration.md)
5. **App-layer** — timestamps, ENUM/boolean, case sensitivity (ARCH wiki)
6. **Gates** — scan must pass; optional shadow period per [shadow-migration.md](reference/shadow-migration.md)

### Scan surface (gate patterns)

`TIMESTAMPDIFF`, `DATE_FORMAT(`, `DATE_ADD(`, `IFNULL(`, `ISNULL(`, `ADDTIME(`, `SUBSTRING_INDEX`,
`CONVERT_TZ`, `CAST(… AS CHAR)`, `ON DUPLICATE KEY`, `INSERT IGNORE`, `GROUP_CONCAT(`, `FIND_IN_SET(`,
`UNIX_TIMESTAMP(`, `CURDATE(`, `LAST_INSERT_ID(`, `INSTR(`, `REGEXP`, `RLIKE`, `DATEDIFF(`, `STR_TO_DATE(`,
MySQL `LIMIT offset,count`, uppercase `DIV` between SQL operands.

**Not scanned** (manual audit): MySQL `` `identifier` `` backticks, `ONLY_FULL_GROUP_BY` / loose `sql_mode` queries — [migration-edge-cases.md](reference/migration-edge-cases.md).

Requires `rg` with PCRE2 (`rg --pcre2-version`). Report-only: `scripts/scan-report.sh`.

Aligned with org ARCH wiki via [domain-packs/](reference/domain-packs/README.md) — generic map in [org-migration-gaps.md](reference/org-migration-gaps.md).

## When to use

| Use mysql-to-postgres-sql | Use instead |
|---------------------------|-------------|
| "Rewrite native SQL for PG cutover" | Full domain map → **domain-comprehension** |
| "Scan service X for MySQL dialect" | MR review of rewrites → **pr-review** |
| Domain-pack P0 cooling SQL fixes | Squad ownership only → **squad-map** |
| Cutover outage / wrong results | **incident-rca** |

## Invocation examples

```
Scan tests/fixtures/mysql-dialect/hits for MySQL-only SQL before PG cutover
Load org-specific domain pack — P0 SMS cooling file list
Org-wide MySQL scrub — what native queries break on jdbc:postgresql?
Migrate Node service from mysql2 to pg — Sequelize dialect and timestamp hooks
Python SQLAlchemy cutover — postgresql+psycopg2 and pool_recycle
```

## Install

```bash
cd ai-skills
make install-mysql-to-postgres-sql
```

Restart Cursor. Setup: [SETUP.md](SETUP.md).

## Related skills

- **domain-comprehension** — `MYSQL_TO_PG_SQL_REWRITES.md`; escalates SQL implementation here
- **pr-review** — migration MR review
- **incident-rca** — post-cutover query/regression investigation
- **loop-task-implementer** — can pick up and implement the resulting rewrite tasks autonomously

Agent instructions: [SKILL.md](SKILL.md) · contract: [reference/skill-contract.md](reference/skill-contract.md) · lazy-load: [reference/lazy-load-index.md](reference/lazy-load-index.md).

## Known limitations

- Scan does not catch MySQL backticks, loose `sql_mode` / `ONLY_FULL_GROUP_BY`, or JPQL strings
- `CONVERT_TZ` semantics depend on column type — validate with per-column fixtures
- Domain pack paths are org-specific — load [domain-packs/README.md](reference/domain-packs/README.md) or scan your service tree
- Datadog MCP is optional; APM `postgresql.query` verification is recommended, not required
- Agent may bulk-load references despite lazy-load — use skill-contract §5
