# Case sensitivity

MySQL string comparisons are often **case-insensitive** (`utf8_general_ci`). PostgreSQL `=` and `LIKE` are **case-sensitive** unless configured otherwise.

**Example:** `WHERE email = 'User@Example.com'` will not match `user@example.com` on PG.

## Team decision (required before cutover)

Each service owning identity or compliance fields must document and implement one approach:

| Option | When to use | Pattern |
|--------|-------------|---------|
| **1. Normalize on write (recommended)** | Email, username, PAN | `LOWER()` at insert/update; query with `LOWER(column) = LOWER(:input)` |
| **2. `ILIKE`** | Ad-hoc search only | `WHERE email ILIKE :pattern` — not for unique lookups without index plan |
| **3. `CITEXT` extension** | Column always case-insensitive | `CREATE EXTENSION citext;` + `email CITEXT` |
| **4. Functional index** | High-volume `LOWER()` lookups | `CREATE INDEX ON users (LOWER(email));` |

## Fields to review in collection services

- Email / mobile lookups (CAAS, EMS defaulter flows)
- PAN, IFSC, bank codes
- Any `=` or `LIKE` on user-entered text in native SQL or JPQL

## Audit commands

```bash
# Native SQL equality on common sensitive columns (manual review hits)
rg -n "email\s*=\s*:|mobile\s*=\s*:|pan\s*=\s*:" --glob '*.java' <service_dir>
rg -n "WHERE.*=\s*'" --glob '*.java' <service_dir>  # literal string equality
```

## Verification

- Test lookup with mixed-case input against known PG seed row
- Document chosen convention in service README or `domain-config.yaml` notes

## Charset / encoding (verify before cutover)

MySQL's `utf8mb4` is full 4-byte Unicode (emoji, rare CJK characters); MySQL's older `utf8` alias is
actually a 3-byte-max subset and silently truncates/rejects 4-byte characters. PostgreSQL's `UTF8`
encoding is full Unicode by default, but a database or column created without an explicit encoding
can inherit a narrower server/template default — a mismatch here is a **silent data-corruption or
insert-failure risk**, not a query-syntax error, so the scan gate above cannot catch it.

Before cutover, verify:

- Source: `SHOW VARIABLES LIKE 'character_set_database';` / per-table `SHOW TABLE STATUS` — confirm
  `utf8mb4` (not legacy `utf8`/`latin1`) if the app ever stores emoji or non-Latin text.
- Target: `SHOW server_encoding;` and `\l` in `psql` — confirm the target database is `UTF8`, not
  inherited from a `SQL_ASCII`/`LATIN1` template.
- Test with a known 4-byte sample (e.g. an emoji) written through the app, not just via `psql`
  directly — the connection driver's own charset setting can silently mangle it even when both ends
  are UTF8.
