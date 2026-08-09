#!/usr/bin/env python3
"""AST-backed secondary check for MySQL-only SQL dialect constructs, over standalone .sql files.

Complements `scripts/scan-mysql-dialect.sh`'s regex scan rather than replacing it. The regex scan
greps embedded SQL fragments across arbitrary source files (Java, PHP, JS, TS, Python, SQL) —
those fragments usually are not, on their own, valid standalone SQL a parser could parse (they're
concatenated inside string literals, ORM DSL calls, etc.), so a real SQL parser cannot cover them.
This script instead parses each *.sql file in full with sqlglot's MySQL dialect and walks the
resulting AST, which:

- Is comment- and string-literal-aware (the regex scan is not — `-- uses DATE_FORMAT() historically`
  inside a .sql file's comment would false-positive under regex, not here).
- Catches constructs the regex's bounded lookahead can miss on complex multi-line expressions.
- Cannot cover every function the regex scan does. sqlglot normalizes several MySQL-only spellings
  into dialect-generic AST node types it ALSO uses for the portable Postgres-native spelling of the
  same operation — GROUP_CONCAT()/STRING_AGG(), DATE_FORMAT()/TO_CHAR(), INSTR()/STRPOS(),
  REGEXP·RLIKE/`~`, and MATCH()·AGAINST()/`@@ to_tsquery()` all parse to the *same* AST type
  regardless of which spelling was in the source (verified empirically, not assumed — see the
  script's own git history for the probe). Flagging that type would false-positive on portable code
  using the Postgres-native spelling, so those five are deliberately left to the regex scan, which
  still needs to run for them. Same reasoning covers IFNULL, ISNULL, DATE_ADD, CAST(...AS CHAR),
  CURDATE, DIV, and comma-form LIMIT — never in this checker's scope. See
  reference/ast-vs-regex-scan.md for the full division of labor.

Exit code: 0 if no MySQL-only construct found (parse errors alone do not fail the check — a .sql
file sqlglot can't parse, e.g. vendor DELIMITER blocks, is reported but not gating). Exit 1 if any
MySQL-only construct is found.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import sqlglot
    from sqlglot import exp
except ImportError:  # pragma: no cover - exercised when sqlglot missing
    sqlglot = None  # type: ignore
    exp = None  # type: ignore

# AST node classes sqlglot gives a dedicated type for, verified NOT to collide with any portable
# Postgres-native spelling of the same operation (see the module docstring). GroupConcat, TimeToStr,
# StrPosition, RegexpLike, and MatchAgainst were tested and excluded for exactly that reason — do
# not add them back without re-verifying against sqlglot's current version.
TYPED_NODE_LABELS = {
    "TimestampDiff": "TIMESTAMPDIFF()",
    "SubstringIndex": "SUBSTRING_INDEX()",
    "ConvertTimezone": "CONVERT_TZ()",
    "DateDiff": "DATEDIFF()",
    "StrToDate": "STR_TO_DATE()",
    "JSONExtract": "JSON_EXTRACT()",
    "JSONObjectAgg": "JSON_OBJECTAGG()",
    "JSONSet": "JSON_SET()",
    "JSONRemove": "JSON_REMOVE()",
}

# Functions sqlglot has no dedicated node for — it parses them as a generic call (exp.Anonymous)
# with the literal function name preserved, which is just as reliable a signal.
ANONYMOUS_MYSQL_FUNCS = {
    "ADDTIME": "ADDTIME()",
    "FIND_IN_SET": "FIND_IN_SET()",
    "UNIX_TIMESTAMP": "UNIX_TIMESTAMP()",
    "LAST_INSERT_ID": "LAST_INSERT_ID()",
    "JSON_UNQUOTE": "JSON_UNQUOTE()",
    "JSON_ARRAYAGG": "JSON_ARRAYAGG()",
    "JSON_CONTAINS": "JSON_CONTAINS()",
    "JSON_MERGE": "JSON_MERGE()",
}


@dataclass
class Finding:
    path: Path
    line: int | None
    label: str
    snippet: str


def _approx_line(text: str, needle: str, cursor: int) -> tuple[int | None, int]:
    """Best-effort line number for `needle` at or after `cursor` in `text`.

    sqlglot doesn't track source positions on successfully-parsed nodes, so this is a heuristic:
    search case-insensitively for the construct's own name starting from the last match found in
    this file (monotonically increasing) so repeated constructs don't all report the first hit.
    """
    idx = text.lower().find(needle.lower(), cursor)
    if idx == -1:
        return None, cursor
    return text.count("\n", 0, idx) + 1, idx + len(needle)


def _walk_statement(stmt: "exp.Expression", path: Path, text: str, cursor: int) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    for node in stmt.walk():
        e = node[0] if isinstance(node, tuple) else node
        cls = type(e).__name__
        label = None
        name_for_line = None
        if cls in TYPED_NODE_LABELS:
            label = TYPED_NODE_LABELS[cls]
            name_for_line = label.split("(")[0].split("/")[0]
        elif cls == "Anonymous":
            fn_name = str(e.this or "").upper() if hasattr(e, "this") else ""
            if fn_name in ANONYMOUS_MYSQL_FUNCS:
                label = ANONYMOUS_MYSQL_FUNCS[fn_name]
                name_for_line = fn_name
        elif cls == "OnConflict" and e.args.get("duplicate"):
            label = "ON DUPLICATE KEY UPDATE"
            name_for_line = "ON DUPLICATE KEY"

        if label:
            line, cursor = _approx_line(text, name_for_line, cursor)
            findings.append(Finding(path=path, line=line, label=label, snippet=e.sql(dialect="mysql")[:80]))
    return findings, cursor


def check_file(path: Path) -> tuple[list[Finding], list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    findings: list[Finding] = []
    parse_errors: list[str] = []
    try:
        statements = sqlglot.parse(text, read="mysql")
    except Exception as exc:  # sqlglot raises a variety of its own error types
        parse_errors.append(f"{path}: {exc}")
        return findings, parse_errors

    cursor = 0
    for stmt in statements:
        if stmt is None:
            continue
        stmt_findings, cursor = _walk_statement(stmt, path, text, cursor)
        findings.extend(stmt_findings)
    return findings, parse_errors


def _collect_sql_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files.extend(sorted(p.rglob("*.sql")))
        elif p.suffix == ".sql":
            files.append(p)
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help=".sql files or directories to scan")
    args = parser.parse_args(argv)

    if sqlglot is None:
        print("error: sqlglot is required — pip install sqlglot", file=sys.stderr)
        return 1

    sql_files = _collect_sql_files(args.paths)
    if not sql_files:
        print("ast-check: no .sql files found")
        return 0

    total_findings = 0
    total_parse_errors = 0
    for f in sql_files:
        findings, parse_errors = check_file(f)
        for pe in parse_errors:
            print(f"PARSE ERROR: {pe}")
            total_parse_errors += 1
        for finding in findings:
            loc = f"{finding.path}:{finding.line}" if finding.line else str(finding.path)
            print(f"{loc}: {finding.label} — {finding.snippet}")
            total_findings += 1

    print(
        f"\nast-check: {len(sql_files)} .sql file(s) scanned, "
        f"{total_findings} MySQL-only construct(s), {total_parse_errors} parse error(s)"
    )
    return 1 if total_findings else 0


if __name__ == "__main__":
    sys.exit(main())
