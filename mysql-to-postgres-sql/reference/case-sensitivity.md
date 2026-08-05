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
