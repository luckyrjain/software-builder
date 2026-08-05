# MySQL → PostgreSQL function translations

Every construct matched by `scripts/scan-mysql-dialect.sh` has a row below. Edge cases and manual audits: [migration-edge-cases.md](migration-edge-cases.md).

| MySQL | PostgreSQL | Notes |
|-------|------------|-------|
| `IFNULL(a, b)` | `COALESCE(a, b)` | |
| `IF(cond, a, b)` | `CASE WHEN cond THEN a ELSE b END` | |
| `DATE_FORMAT(ts, '%Y-%m-%d')` | `to_char(ts, 'YYYY-MM-DD')` | Prefer `ts::date` + app format |
| `DATE_FORMAT(ts, '%d-%m-%Y')` | `to_char(ts, 'DD-MM-YYYY')` | |
| `DATE_FORMAT(ts, '%b %d,%Y')` | `to_char(ts, 'Mon DD,YYYY')` | Verify month abbrev |
| `TIMESTAMPDIFF(SECOND, a, b)` | `EXTRACT(EPOCH FROM (b - a))` | |
| `TIMESTAMPDIFF(MINUTE, a, b)` | `EXTRACT(EPOCH FROM (b - a)) / 60` | Integer: `FLOOR` if `b >= a`; see edge cases |
| `TIMESTAMPDIFF(HOUR, a, b)` | `EXTRACT(EPOCH FROM (b - a)) / 3600` | Same truncation note |
| `TIMESTAMPDIFF(DAY, a, b)` | `(b::date - a::date)` | Returns integer days |
| `DATE_ADD(ts, INTERVAL n MINUTE)` | `ts + (n * INTERVAL '1 minute')` | |
| `DATE_ADD(NOW(), INTERVAL n MINUTE)` | `NOW() + (n * INTERVAL '1 minute')` | |
| `DATEDIFF(a, b)` | `(a::date - b::date)` | |
| `STR_TO_DATE(s, fmt)` | `to_date(s, fmt_pg)` | Map format tokens (`%Y` → `YYYY`) |
| `DATE(col)` | `col::date` | |
| `CAST(x AS CHAR)` | `x::text` | |
| `CONVERT_TZ(dt, from, to)` | `dt AT TIME ZONE from AT TIME ZONE to` | **Type-dependent** — see edge cases |
| `ADDTIME(ts, '0 05:30:00')` | `ts + INTERVAL '5 hours 30 minutes'` | |
| `SUBSTRING_INDEX(s, ' ', 1)` | `split_part(s, ' ', 1)` | |
| `GROUP_CONCAT(col)` | `string_agg(col::text, ',')` | |
| `GROUP_CONCAT(c ORDER BY c SEPARATOR ';')` | `string_agg(c::text, ';' ORDER BY c)` | `ORDER BY` inside `string_agg` |
| `FIND_IN_SET(x, list)` | `x = ANY(string_to_array(list, ','))` | |
| `ON DUPLICATE KEY UPDATE` | `ON CONFLICT (cols) DO UPDATE SET …` | Must name unique constraint columns |
| `INSERT IGNORE` | `ON CONFLICT DO NOTHING` | |
| `UNIX_TIMESTAMP(ts)` | `EXTRACT(EPOCH FROM ts)` | |
| `CURDATE()` | `CURRENT_DATE` | |
| `ISNULL(expr)` | `expr IS NULL` | Not a function on PG; distinct from `IFNULL` |
| `REGEXP pat` / `RLIKE pat` | `~ pat` / `~* pat` | Escape metacharacters |
| `INSTR(str, substr)` | `POSITION(substr IN str)` or `STRPOS(str, substr)` | |
| `a DIV b` | `(a / b)::integer` | Scan: uppercase `DIV` between SQL operands only |
| `LAST_INSERT_ID()` | `INSERT … RETURNING id` | After import: `setval` — see edge cases |
| `LIMIT offset, count` | `LIMIT count OFFSET offset` | Two-arg MySQL form only |
| `NOW()` / `CURRENT_TIMESTAMP()` | Same | |
| `CONCAT_WS`, `REPLACE`, `COALESCE` | Same | |
| `LIMIT n` (single arg) | Same | |
| `ROW_NUMBER() OVER (...)` | Same | |
| `JSON_EXTRACT(col, '$.path')` | `col->'path'` (nested: `col->'a'->'b'`) | MySQL `$.path` JSONPath syntax ≠ PG's chained `->` — not a drop-in string substitution |
| `JSON_UNQUOTE(JSON_EXTRACT(col, '$.path'))` | `col->>'path'` | |
| `JSON_ARRAYAGG(x)` | `jsonb_agg(x)` | |
| `JSON_OBJECTAGG(k, v)` | `jsonb_object_agg(k, v)` | |
| `JSON_CONTAINS(col, val)` | `col @> val::jsonb` | Verify containment direction/semantics match |
| `JSON_SET(col, '$.path', val)` | `jsonb_set(col, '{path}', to_jsonb(val))` | Path syntax differs (`$.a.b` → `'{a,b}'`) |
| `JSON_REMOVE(col, '$.path')` | `col #- '{path}'` | |
| `JSON_MERGE(a, b)` | `a::jsonb || b::jsonb` | MySQL `JSON_MERGE` (and its alias `JSON_MERGE_PRESERVE`) does a **shallow** top-level merge — same as PG `\|\|`. If the app actually needs `JSON_MERGE_PATCH` (deep/recursive merge) semantics, `\|\|` is wrong — verify which one the code relies on before translating |
| `YEAR(ts)` | `EXTRACT(YEAR FROM ts)` | Returns numeric; cast to `int` if the app compares as integer |
| `MONTH(ts)` | `EXTRACT(MONTH FROM ts)` | |
| `WEEK(ts)` | `EXTRACT(WEEK FROM ts)` | **Not a drop-in** — MySQL `WEEK()` mode defaults and week-numbering (Sun/Mon start, ISO vs non-ISO) differ from PG's ISO-8601 `EXTRACT(WEEK ...)`; verify the MySQL call's mode argument before translating |
| `MATCH(cols) AGAINST('term')` | `to_tsvector('simple', cols) @@ plainto_tsquery('simple', 'term')` | **Not syntax-only** — needs a `tsvector` column/expression + GIN index; escalate to manual design review, see edge cases |

### Manual audit (not in scan)

| MySQL | PostgreSQL | Notes |
|-------|------------|-------|
| `` `column` `` backticks | `"column"` or lowercase unquoted | JS/PHP backticks cause scan false positives — audit SQL strings |
| `NOW() + INTERVAL 1 DAY` | Usually same on PG | Verify interval unit syntax |

## Cooling-period pattern (P0)

**MySQL:**
```sql
TIMESTAMPDIFF(MINUTE, tsc.added_timestamp, CURRENT_TIMESTAMP()) < :cool
DATE_ADD(MAX(added_timestamp), INTERVAL :cool MINUTE) AS nextdate
(TIMESTAMPDIFF(MINUTE, MAX(added_timestamp), CURRENT_TIMESTAMP()) > :cool) AS isExceed
WHERE DATE(tsc.added_timestamp) = :today
```

**PostgreSQL:**
```sql
EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - tsc.added_timestamp)) / 60 < :cool
MAX(added_timestamp) + (:cool * INTERVAL '1 minute') AS nextdate
(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MAX(added_timestamp))) / 60 > :cool) AS isExceed
WHERE tsc.added_timestamp::date = :today
```

Intervals are past → positive; `FLOOR` on hour variant optional for display parity with MySQL `TIMESTAMPDIFF(HOUR, ...)`.
