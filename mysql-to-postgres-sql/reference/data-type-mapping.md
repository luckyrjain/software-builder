# Data type & JPA mapping

Schema migration is DBA-owned; this file covers **application mapping** pitfalls when the same Java/Python code runs against PostgreSQL.

## MySQL → PostgreSQL types

| MySQL | PostgreSQL | Application note |
|-------|------------|------------------|
| `TINYINT(1)` | `BOOLEAN` | `is_canceled = 0` → `= false`; projection interfaces may expect `0/1` |
| `TINYINT` | `SMALLINT` | |
| `DATETIME` | `TIMESTAMP` | Prefer `Instant` / `OffsetDateTime` in Java |
| `DOUBLE` | `DOUBLE PRECISION` | |
| `BLOB` | `BYTEA` | |
| `AUTO_INCREMENT` | `SERIAL` / `BIGSERIAL` / `GENERATED … AS IDENTITY` | Use `@GeneratedValue` — do not assume `LAST_INSERT_ID()` |
| `UNSIGNED INT` | `INTEGER` + `CHECK (col >= 0)` or `BIGINT` | Widen if values exceed signed range |
| `TINYTEXT` / `MEDIUMTEXT` / `LONGTEXT` | `TEXT` | |
| `ENUM('a','b')` | `CHECK` or PG `ENUM` type | See below |

## ENUM handling (Java Spring Boot)

**Option 1 — store as string (recommended):**

```java
@Enumerated(EnumType.STRING)
private Status status;
```

**Option 2 — native PostgreSQL ENUM:**

```java
@JdbcType(PostgreSQLEnumJdbcType.class)
private PostStatus status;
```

Validate existing DB values map 1:1 before cutover; add migration for invalid legacy values.

## Semantic traps in native SQL

| Pattern | MySQL | PostgreSQL |
|---------|-------|------------|
| Boolean filter | `WHERE active = 1` | `WHERE active = true` (if column is boolean) |
| Boolean in SELECT | `(expr > n) AS flag` returns `0/1` | Returns `boolean` — check DTO/interface type |
| Integer division | `SELECT 5 DIV 2` → `2` | `SELECT 5 / 2` → `2` only with `::integer` cast on operands |
| Last insert id | `LAST_INSERT_ID()` | `INSERT … RETURNING id` or `currval()` on sequence |

## Collection touchpoints

- **CLMS** `TblUserLoanRepository`: `is_canceled = 0` — verify PG column type
- **EMS** `CAST(… AS CHAR)` → `::text` (see [collection-domain-files.md](collection-domain-files.md))

## Verification

- Hibernate schema validation or integration tests against PG Testcontainers
- Shadow compare sample rows for boolean and enum columns
