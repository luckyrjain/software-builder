# Smoke test — expected minimal output

Run after `make install-mysql-to-postgres-sql`, Cursor restart, and **after any edit** to `SKILL.md`, `workflow/`, or `reference/`.

## Fixture

Use scan fixtures (no org-specific paths required):

`mysql-to-postgres-sql/tests/fixtures/mysql-dialect/hits/` (must fail) and `clean/` (must pass).

Optional: any service directory with native SQL on your machine. Domain packs (see
[domain-packs/README.md](domain-packs/README.md)) list org-specific paths when loaded.

## Invocation

> Scan `mysql-to-postgres-sql/tests/fixtures/mysql-dialect/hits` for MySQL-only SQL before PG cutover.

## A correct minimal output contains

1. **Scope** — service path and scan command invoked
2. **Scan result** — exit code + hit file:line list (or OK)
3. **Tier mapping** — P0/P1 from domain pack or function-translations when hits exist
4. **Rewrite sample** — at least one before/after SQL block from function-translations
5. **Gate status** — explicit pass/fail vs merge gate (scan exit 0)
6. **Next step** — config checklist, shadow compare, or pr-review handoff

## Expected first output (healthy)

```
Scanning for MySQL-only SQL under: mysql-to-postgres-sql/tests/fixtures/mysql-dialect/hits
```

Followed by FAIL with `TIMESTAMPDIFF` / `DATE_ADD` lines, or OK if path is clean. The scan matches
lowercase SQL too (`select timestampdiff(...)`) via a case-insensitive pattern group — see
[pressure-tests.md](pressure-tests.md) #18. `DIV`/`IF`/`YEAR`/`MONTH`/`WEEK`/`LIMIT` stay
case-sensitive-uppercase-only by design (see #16) to avoid false-positiving on ordinary code.

## Platform paths

| Stack | Invocation |
|-------|------------|
| Scan gate | Scan `tests/fixtures/mysql-dialect/hits` for MySQL-only SQL |
| Node | Migrate this service from mysql2 to pg — Sequelize config |
| Python | Cut over SQLAlchemy to postgresql+psycopg2 with pool_recycle |
| Domain pack | Load org-specific domain pack — P0 SMS cooling file list |
| Escalation | Review MR !123 for MySQL to PostgreSQL migration → **pr-review** |

## Script self-test

From repo root:

```bash
make lint-mysql-to-postgres-sql
```

Pressure harness only:

```bash
bash mysql-to-postgres-sql/tests/run_pressure_tests.sh
```

From skill directory:

```bash
scripts/scan-mysql-dialect.sh tests/fixtures/mysql-dialect/hits    # expect exit 1
scripts/scan-mysql-dialect.sh tests/fixtures/mysql-dialect/clean   # expect exit 0
bash tests/run_pressure_tests.sh
```

## Failure diagnosis

| Symptom | Likely cause |
|---------|--------------|
| Scan exits 0 unexpectedly | `rg` missing — script errors, not clean |
| Agent skips scan | skill-contract §2 — re-run gate |
| Wrong skill invoked | Check [skill-routing.md](../../docs/skill-framework/shared/skill-routing.md) |
| Broken rewrites | Load function-translations + migration-edge-cases |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
