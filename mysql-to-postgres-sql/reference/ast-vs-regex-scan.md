# Regex scan vs. AST-backed secondary check

Two scripts, two different jobs — run both, neither replaces the other.

## `scripts/scan-mysql-dialect.sh` (primary gate, always required)

Regex scan (via `mysql-dialect-patterns.sh`) over the touched service's source files —
`*.java`, `*.php`, `*.sql`, `*.py`, `*.js`, `*.ts`. This is the merge gate: **exit 0 required**
per [skill-contract.md](skill-contract.md). It has to cover application code because most
MySQL-dialect SQL in a real migration lives *inside* that code — string-concatenated queries,
ORM raw-SQL calls, JDBC templates — not as standalone `.sql` files a parser could read. A regex
scan is the only thing that can look inside a Java string literal or a JS template literal.

Trade-off: no comment/string-literal awareness (a `.sql` file's own `-- comment` mentioning
`DATE_FORMAT` looks the same as code to a regex), and each pattern's lookahead is bounded (`{0,80}`
chars) to avoid runaway matches — an unusually long multi-line construct can slip past it.

## `scripts/ast_check_mysql_dialect.py` (secondary, `.sql` files only)

Parses each `*.sql` file in full with [sqlglot](https://github.com/tobymao/sqlglot)'s MySQL
dialect and walks the resulting AST. Only covers standalone `.sql` files (schema/migration/stored
procedure scripts) — it cannot parse a SQL fragment embedded in application code, which usually
isn't valid SQL on its own (missing terminators, string concatenation placeholders, etc.).

What it adds over the regex scan, for the `.sql` files it can parse:
- Comment- and string-literal-aware — a `.sql` file's own comment mentioning a MySQL function name
  is not a hit (verified by `test_clean_fixture_comment_mention_not_flagged`).
- No lookahead bound — catches constructs spread across an arbitrarily long expression.
- Structural certainty — `ON DUPLICATE KEY UPDATE` is detected via the parser's own conflict-type
  flag (`OnConflict(duplicate=True)`), not a text pattern that could be defeated by formatting.

**What it deliberately does NOT cover**, and why: sqlglot canonicalizes several MySQL-only
functions to the *same* AST node type it uses for their portable Postgres-native equivalent —
parsing `GROUP_CONCAT(...)` and `STRING_AGG(...)` (or `DATE_FORMAT`/`TO_CHAR`, `INSTR`/`STRPOS`,
`REGEXP`/`~`, `MATCH()...AGAINST()`/`@@ to_tsquery()`) both produce the identical node type. There
is no reliable AST-level signal to tell which spelling was actually in the source once sqlglot has
normalized it — flagging that node type would false-positive on already-portable code. Those five,
plus `IFNULL`, `ISNULL`, `DATE_ADD`, `CAST(...AS CHAR)`, `CURDATE`, `DIV`, and comma-form `LIMIT`,
stay covered by the regex scan only. This was verified empirically against the installed sqlglot
version, not assumed — see `tests/test_ast_check_mysql_dialect.py`'s
`test_portable_spellings_never_flagged` for the regression guard.

Constructs this checker **does** reliably catch (verified, see
`tests/fixtures/ast-check/hits.sql`): `TIMESTAMPDIFF()`, `SUBSTRING_INDEX()`, `CONVERT_TZ()`,
`DATEDIFF()`, `STR_TO_DATE()`, `JSON_EXTRACT()`, `JSON_OBJECTAGG()`, `JSON_SET()`,
`JSON_REMOVE()`, `ADDTIME()`, `FIND_IN_SET()`, `UNIX_TIMESTAMP()`, `LAST_INSERT_ID()`,
`JSON_UNQUOTE()`, `JSON_ARRAYAGG()`, `JSON_CONTAINS()`, `JSON_MERGE()`, and
`ON DUPLICATE KEY UPDATE`.

A file sqlglot can't parse at all (vendor `DELIMITER` blocks, dynamic SQL builders, etc.) is
reported as a parse error but does **not** fail the check — parse failure isn't proof of
MySQL-specificity, just a signal worth a human look.

## Running both

```bash
bash scripts/scan-mysql-dialect.sh <service-path>                       # required — merge gate
python3 scripts/ast_check_mysql_dialect.py <service-path-or-.sql-files>  # supplementary, .sql only
```

`make lint-mysql-to-postgres-sql` runs both.
