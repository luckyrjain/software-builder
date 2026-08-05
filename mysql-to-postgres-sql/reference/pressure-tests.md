# Pressure tests — mysql-to-postgres-sql

Run when editing `SKILL.md`, `workflow/`, `reference/`, or scan scripts. Targets guardrails that regress easily.

**Automated:** `bash tests/run_pressure_tests.sh` (also via `make lint-mysql-to-postgres-sql`).

| # | Scenario | Expected behavior |
|---|----------|-------------------|
| 1 | Service with only JPQL + `MySQL8Dialect` | Dialect + JDBC/driver only; no native SQL rewrites; scan clean on `.java` without `nativeQuery` |
| 2 | `Scan tests/fixtures/mysql-dialect/hits for MySQL dialect` | Invoke `scan-mysql-dialect.sh`; list hits; map tiers via domain pack or function-translations |
| 3 | Agent proposes `@PreUpdate` on `oauth_refresh_tokens.expires` | Refuse; cite migration-edge-cases §B |
| 4 | `Review MR !482 for MySQL→PG migration` | Route to **pr-review**; do not start rewrite workflow |
| 5 | `Who owns collection-admin-api-service?` | Route to **squad-map** |
| 6 | `Map bounded contexts in collection` | Route to **domain-comprehension** |
| 7 | Scan hits remain; user asks "are we done?" | Answer **no**; cite gate step 6 + open hit list |
| 8 | `TIMESTAMPDIFF` rewrite without `FLOOR` on HOUR cooling | Flag semantic trap; cite function-translations cooling pattern |
| 9 | Node service: `mysql2` + raw `?` placeholders | Load nodejs-migration; rewrite placeholders to `$1`… |
| 10 | Agent bulk-reads entire `reference/` tree | Only lazy-load-index triggers; only the file(s) named for that trigger (some triggers pair 2 files) |
| 11 | `rg` missing on PATH | Scan script exits 1 with install message — not silent pass |
| 12 | Cutover caused wrong SMS blocking | Escalate **incident-rca** with shadow-compare evidence |
| 13 | `CAST(x AS CHAR)` split across concatenated string literals (`"CAST(x " + "AS CHAR)"`) | Scan detects it (multi-line-aware, bounded span) — not a silent miss |
| 14 | `JSON_EXTRACT(...)` / `MATCH(...) AGAINST(...)` in native SQL; Java lambda `x -> x+1` and bare `col->'key'` jsonb access nearby | Scan flags the JSON/fulltext functions; does not false-positive on `->` used as a lambda arrow or PG-compatible jsonb operator |
| 15 | `LIMIT_KEY`/`RATE_LIMIT_THRESHOLD` constants; a comment mentioning "DIV nodes" | Scan stays clean — LIMIT/DIV glue is bounded to plausible string-concatenation punctuation, not any code |

Smoke invocation strings: [smoke-test.md](smoke-test.md).
