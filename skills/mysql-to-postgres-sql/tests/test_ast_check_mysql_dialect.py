"""Tests for scripts/ast_check_mysql_dialect.py (issue #54)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ast_check_mysql_dialect.py"
FIXTURES = ROOT / "tests" / "fixtures" / "ast-check"
HITS = FIXTURES / "hits.sql"
CLEAN = FIXTURES / "clean.sql"

pytest.importorskip("sqlglot")

sys.path.insert(0, str(ROOT / "scripts"))
import ast_check_mysql_dialect as checker  # noqa: E402


def _run(*paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(p) for p in paths]],
        capture_output=True,
        text=True,
        check=False,
    )


def test_hits_fixture_fails():
    result = _run(HITS)
    assert result.returncode == 1, result.stdout
    assert "TIMESTAMPDIFF" in result.stdout
    assert "SUBSTRING_INDEX" in result.stdout
    assert "ON DUPLICATE KEY UPDATE" in result.stdout
    assert "UNIX_TIMESTAMP" in result.stdout
    assert "JSON_EXTRACT" in result.stdout


def test_clean_fixture_passes():
    result = _run(CLEAN)
    assert result.returncode == 0, result.stdout
    assert "0 MySQL-only construct" in result.stdout


def test_clean_fixture_comment_mention_not_flagged():
    """The clean fixture mentions SUBSTRING_INDEX/UNIX_TIMESTAMP in a -- comment — a checker that
    isn't comment-aware (i.e. that fell back to text search) would false-positive on this."""
    result = _run(CLEAN)
    assert result.returncode == 0
    assert "SUBSTRING_INDEX" not in result.stdout
    assert "UNIX_TIMESTAMP" not in result.stdout


def test_directory_scan_finds_both_fixtures():
    result = _run(FIXTURES)
    assert "2 .sql file(s) scanned" in result.stdout


def test_parse_error_is_reported_but_not_gating(tmp_path: Path):
    bad = tmp_path / "broken.sql"
    bad.write_text("DELIMITER $$\nCREATE PROCEDURE foo() BEGIN SELECT 1; END$$\nDELIMITER ;\n", encoding="utf-8")
    result = _run(bad)
    assert result.returncode == 0, "a file sqlglot can't parse must not fail the check"
    assert "PARSE ERROR" in result.stdout


def test_no_sql_files_is_a_clean_no_op(tmp_path: Path):
    result = _run(tmp_path)
    assert result.returncode == 0
    assert "no .sql files found" in result.stdout


# --- Regression guards: portable Postgres-native spellings must never be flagged -----------------
# sqlglot canonicalizes several MySQL-only functions and their portable Postgres-native equivalent
# to the *same* AST node type (verified empirically — see the checker module's docstring). These
# five are therefore deliberately excluded from TYPED_NODE_LABELS; if one is ever added back
# without re-verifying, these tests catch the false positive it would reintroduce.


@pytest.mark.parametrize(
    "portable_sql",
    [
        "SELECT STRING_AGG(name, ', ') FROM t;",
        "SELECT TO_CHAR(x, 'YYYY') FROM t;",
        "SELECT STRPOS(a, b) FROM t;",
        "SELECT a ~ b FROM t;",
        "SELECT * FROM t WHERE to_tsvector(a) @@ to_tsquery('x');",
    ],
)
def test_portable_spellings_never_flagged(portable_sql: str, tmp_path: Path):
    f = tmp_path / "portable.sql"
    f.write_text(portable_sql, encoding="utf-8")
    findings, parse_errors = checker.check_file(f)
    assert findings == [], f"portable spelling incorrectly flagged: {portable_sql!r} -> {findings}"


def test_on_conflict_do_update_not_flagged_only_on_duplicate_key_is():
    duplicate_key = "INSERT INTO t (a,b) VALUES (1,2) ON DUPLICATE KEY UPDATE b = VALUES(b);"
    on_conflict = "INSERT INTO t (a,b) VALUES (1,2) ON CONFLICT (a) DO UPDATE SET b = EXCLUDED.b;"

    import sqlglot

    dup_stmt = sqlglot.parse_one(duplicate_key, read="mysql")
    conflict_stmt = sqlglot.parse_one(on_conflict, read="postgres")

    dup_findings, _ = checker._walk_statement(dup_stmt, Path("x.sql"), duplicate_key, 0)
    conflict_findings, _ = checker._walk_statement(conflict_stmt, Path("x.sql"), on_conflict, 0)

    assert any(f.label == "ON DUPLICATE KEY UPDATE" for f in dup_findings)
    assert not any(f.label == "ON DUPLICATE KEY UPDATE" for f in conflict_findings)
