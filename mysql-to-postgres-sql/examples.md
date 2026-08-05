# MySQL → PostgreSQL — Examples

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md)

## Invocation

| # | User says | Resolves to | Notes |
|---|-----------|-------------|-------|
| 1 | `Scan tests/fixtures/mysql-dialect/hits for MySQL-only SQL` | Scan → hit list → function-translations | Happy path (fixture) |
| 2 | `Load collection-mpokket pack — P0 SMS cooling files` | domain-packs/collection-mpokket + function-translations | Domain pack |
| 3 | `Migrate Node service from mysql2 to pg — Sequelize config and timestamp hooks` | nodejs-migration + timestamp-handling | Node path |
| 4 | `Cut over SQLAlchemy engine to postgresql+psycopg2 with search_path and pool_recycle` | python-migration | Python path |
| 5 | `Org-wide MySQL scrub — what native queries break on jdbc:postgresql?` | migrate-service workflow + scan per repo | Multi-service |
| 6 | `rg not installed — scan anyway` | Scan exits 1; install `rg` message | Degraded path |
| 7 | `Review MR !482 for MySQL to PostgreSQL migration` | **pr-review** | Cross-skill |
| 8 | `Map who owns collection repos` | **domain-comprehension** or **squad-map** | Wrong-skill |

## Scenario: P0 scan and rewrite

**User:** "Scan `tests/fixtures/mysql-dialect/hits` for MySQL-only SQL."

**Agent:**
1. Run `scripts/scan-mysql-dialect.sh tests/fixtures/mysql-dialect/hits`
2. Map hits to rewrite patterns in function-translations (load collection-mpokket pack if org context given)
3. Propose PG rewrites from cooling pattern when applicable

**Expected fragments:**

```
Scanning for MySQL-only SQL under: tests/fixtures/mysql-dialect/hits
FAIL: MySQL-only dialect constructs found.
```

```
P0 — TblSmsCaptureRecordRepository.findCoolingForToday
MySQL: TIMESTAMPDIFF(MINUTE, …) / DATE_ADD(…)
PG:    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - …)) / 60
```

## Scenario: JPQL-only service (dialect change only)

**User:** "This Spring service has only JPQL — migrate datasource to PostgreSQL."

**Agent:**
1. Confirm no `nativeQuery=true` via inventory ripgrep
2. Update JDBC URL, driver, `PostgreSQLDialect`
3. Run scan — expect exit 0

**Expected fragments:**

```
No native @Query(nativeQuery=true) found — dialect + JDBC only.
Hibernate: MySQL8Dialect → PostgreSQLDialect
Scan gate: OK (exit 0)
```

## Scenario: Node mysql2 → pg cutover

**User:** "Migrate this Node service from mysql2 to pg — Sequelize config and timestamp hooks."

**Agent:**
1. Inventory `package.json` for `mysql2` / `dialect: 'mysql'`
2. Load nodejs-migration + timestamp-handling
3. Propose `pg` Pool / Sequelize dialect + hook changes

**Expected fragments:**

```
package.json: mysql2 → pg (remove mysql2 when unused)
Sequelize dialect: 'mysql' → 'postgres'
Raw SQL placeholders: ? → $1, $2, …
```

## Scenario: Cross-skill handoff to pr-review

**User:** "Review MR !482 for MySQL to PostgreSQL migration in relationship-consent-manager."

**Agent:**
1. Recognize MR review intent — not SQL rewrite
2. Route to **pr-review** with handoff context

**Expected fragments:**

```
**Handoff → pr-review**
- Service: relationship-consent-manager
- Trigger: MySQL→PG migration MR
- Ask: "Review MR !482 for MySQL→PostgreSQL migration in relationship-consent-manager"
```

## Scenario: OAuth expires trap (adversarial)

**User:** "Add @PreUpdate to refresh oauth_refresh_tokens.expires on every save."

**Agent:**
1. Refuse — token expiry is not last-updated
2. Cite migration-edge-cases §B

**Expected fragments:**

```
Do not @PreUpdate oauth_refresh_tokens.expires — invalidates tokens.
See migration-edge-cases.md §B and timestamp-handling.md (exclude OAuth expires).
```

## Scenario: Degraded scan (rg missing)

**User:** "Scan this service for MySQL dialect" (no `rg` on PATH)

**Agent:**
1. Run scan script
2. Report install requirement; do not claim clean

**Expected fragments:**

```
ERROR: ripgrep (rg) not found; install rg to run scan gate
```

Golden deliverable: [templates/SERVICE_PG_MIGRATION.md](templates/SERVICE_PG_MIGRATION.md).
