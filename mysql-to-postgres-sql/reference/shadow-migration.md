# Shadow period & partial migration

Hard cutover is the default merge gate (`scan-mysql-dialect.sh` clean + PG datasource). Use this guide when services run **both** databases during validation or when the fleet is **partially** migrated.

## Dual-query / shadow compare

During PG staging validation:

1. Run the same read path against **MySQL prod sample** and **PG staging** for fixed `userId` / primary keys.
2. Compare row counts, cooling-window blocks, date strings, and boolean flags — not byte-identical JSON if drivers differ.
3. Log divergences with query text + bind params; fix SQL rewrite before toggling prod traffic.

Do **not** join MySQL and PostgreSQL in a single SQL statement across services — compare in application or test harness.

## Feature flags / connection toggle

| Pattern | Use |
|---------|-----|
| Env var `DB_VENDOR=mysql\|postgres` | Single binary, switch `DataSource` / engine URL at startup |
| Per-request routing | Avoid unless read-only; writes must not split across DBs |
| Strangler: read PG, write both | Short window only; requires conflict resolution — prefer read-only shadow |

Remove MySQL pool from config after shadow period passes and scan is clean.

## Partial fleet (some services on PG, some on MySQL)

- **No cross-DB joins** in one service — call peer service APIs instead of federated SQL.
- **Eventual consistency:** Kafka/outbox payloads must not assume MySQL `AUTO_INCREMENT` ids match PG sequences.
- **Shared tables:** coordinate cutover order via [your migration tracker](<link to your migration tracker>).

## Rollback

1. Revert datasource env to MySQL; redeploy last known-good image.
2. PG writes during cutover may not exist on MySQL — treat rollback as **read fallback** unless dual-write was implemented.
3. Post-incident: **incident-rca** if user-facing; **pr-review** on the migration MR.

## Optional Datadog verification

When Datadog MCP is available after cutover:

- Query APM for `service:<name>` — expect `postgresql.query` (or `postgres.query`) spans, not `mysql.query`.
- Compare error rate and p95 latency in the migration window vs baseline.

No MCP required — manual APM UI check suffices (see SETUP.md).
