# Migration edge cases (beyond scan gate)

Patterns **not** reliably caught by `scan-mysql-dialect.sh`, or translations that need human judgment.

## Scan limitations

| Pattern | Why not scanned | Action |
|---------|-----------------|--------|
| MySQL `` `identifier` `` backticks | False positives: JS template literals, PHP shell `` `cmd` `` | Audit native SQL / `.sql` manually |
| `CAST(SUBSTRING(x,1,2) AS CHAR)` | Nested parens break `CAST\([^)]* AS CHAR\)` regex | Audit native SQL / `.sql` manually |
| `total DIV count_val` | `DIV` lookahead only fires before digit/string/paren | Audit native SQL / `.sql` manually |
| `NOW() + INTERVAL 1 HOUR` (MySQL) | Valid on both; MySQL interval literals differ in edge cases | Review interval syntax in native SQL |
| `ONLY_FULL_GROUP_BY` / `sql_mode` | Config, not syntax | See below |

## A. Translation caveats

### `TIMESTAMPDIFF(unit, start, end)`

MySQL returns `end - start`. PG: `EXTRACT(EPOCH FROM (end - start)) / unit_seconds`.

| Unit | PostgreSQL |
|------|------------|
| SECOND | `EXTRACT(EPOCH FROM (b - a))` |
| MINUTE | `/ 60` |
| HOUR | `/ 3600` |
| DAY | `(b::date - a::date)` (integer days) |

For integer truncation when `end >= start`, `FLOOR` matches MySQL. If `end < start`, MySQL truncates toward zero; PG `FLOOR` differs — use `TRUNC(...)` toward zero for parity.

### `CONVERT_TZ(dt, from_tz, to_tz)`

PG `AT TIME ZONE` depends on input type:

- `timestamp without time zone`: `dt AT TIME ZONE from_tz AT TIME ZONE to_tz` matches MySQL intent (interpret as `from_tz`, show in `to_tz`).
- `timestamptz`: semantics differ — first `AT TIME ZONE` strips offset. Prefer storing `timestamptz` and converting in app layer, or normalize to `timestamp without time zone` before converting.

Always validate with known fixtures per column type.

### `GROUP_CONCAT` with `ORDER BY` / `SEPARATOR`

```sql
-- MySQL
GROUP_CONCAT(col ORDER BY col ASC SEPARATOR ';')
-- PostgreSQL
string_agg(col::text, ';' ORDER BY col)
```

### `ON DUPLICATE KEY UPDATE`

Requires explicit conflict target: `ON CONFLICT (unique_cols) DO UPDATE SET …`. Identify the matching unique index — not mechanical.

### `DATEDIFF(a, b)` / `STR_TO_DATE`

| MySQL | PostgreSQL |
|-------|------------|
| `DATEDIFF(a, b)` | `(a::date - b::date)` |
| `STR_TO_DATE(s, '%Y-%m-%d')` | `to_date(s, 'YYYY-MM-DD')` |

### `REGEXP` / `RLIKE`

`RLIKE` is a MySQL synonym — rewrite to `~` / `~*` like `REGEXP`.

### `LIKE` escape

MySQL default escape `\`; PG `LIKE` has no default escape unless `ESCAPE` clause. Audit patterns with `\_` or `%` literals.

### `MATCH(cols) AGAINST('term')` fulltext search

Not a syntax-only rewrite. Requires a `tsvector` generated column or expression index (`to_tsvector('simple', cols)`)
plus a GIN index before `@@ plainto_tsquery(...)` performs acceptably — schema change, not just query
rewrite. Boolean-mode (`AGAINST('term' IN BOOLEAN MODE)`) needs `to_tsquery`/`websearch_to_tsquery`
instead of `plainto_tsquery`; relevance ranking (`MATCH(...) AGAINST(...)` used as a score) needs
`ts_rank`/`ts_rank_cd`. Flag for manual design review — do not propose an inline rewrite.

## B. OAuth `expires` columns (critical)

`oauth_authorization_codes.expires` and `oauth_refresh_tokens.expires` are **token expiry deadlines**, not “last updated” timestamps.

**Do not** set them to `now()` on `@PreUpdate` / `before_update` — that invalidates tokens. Only application token-issuance logic should write `expires`.

See [timestamp-handling.md](timestamp-handling.md) (custom-named columns — exclude OAuth `expires`).

## C. Database / runtime behavior

### Transaction isolation

| | MySQL (InnoDB default) | PostgreSQL default |
|---|------------------------|-------------------|
| Default | `REPEATABLE READ` | `READ COMMITTED` |
| Snapshot | Whole transaction | Per statement |

Long read transactions and read-your-own-writes can differ. SMS cooling and financial reads: test under PG default isolation.

### `sql_mode` / `ONLY_FULL_GROUP_BY`

PG behaves like strict MySQL. Queries with non-aggregated columns not in `GROUP BY` that “worked” on loose MySQL will fail at runtime — **not** caught by scan.

### Sequences after data import

After bulk load, reset: `SELECT setval(pg_get_serial_sequence('tbl','id'), (SELECT MAX(id) FROM tbl));` — or first INSERT hits PK conflict.

### Stored procedures / triggers

DBA-owned; app scan does not cover. Confirm migration runbook converted MySQL routines.

### Hibernate L2 cache (partial fleet)

Shared cache across MySQL/PG services can hydrate wrong types (`boolean` vs `0/1`). Flush or partition cache per cutover.

## D. Connection hygiene

### `pool_recycle=85` (Python)

ARCH wiki example value — tune to **below** your load balancer idle timeout (e.g. NLB ~350s). `85` is aggressive; increase if connection churn is high.

### `application_name`

Set on every driver, then use `pg_stat_activity.application_name` or Datadog `db.system:postgresql` + service tags to trace which deploy owns a query.

## E. 200+ tables vs 14 custom columns

Org estimate: **200+** tables used MySQL `ON UPDATE CURRENT_TIMESTAMP`. Most use standard `created_at` / `updated_at` (§1 auditing). The **14-table** list is only non-standard **last-updated** column names — not an exhaustive table census. Use the [migration tracker](https://docs.google.com/spreadsheets/d/1TzlHh-tfc-usiF3qAEUIeGbND9-9yZ9L5pBRBXFY0ZA/edit?usp=sharing) for repo scope.
