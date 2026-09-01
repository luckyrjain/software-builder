"""Tests for pr-gatekeeper/scripts/idempotency_store.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from idempotency_store import _safe_slug, _store_path  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "idempotency_store.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_check_then_mark(tmp_path: Path) -> None:
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "group/repo",
        "--merge-request-iid",
        "42",
        "--head-sha",
        "abc123",
    ]
    assert run(*base, "check").returncode == 0
    assert run(*base, "mark").returncode == 0
    assert run(*base, "check").returncode == 1

    base[-1] = "def456"
    assert run(*base, "check").returncode == 0


def test_run_if_new_skips_duplicate(tmp_path: Path) -> None:
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "group/repo",
        "--merge-request-iid",
        "42",
        "--head-sha",
        "abc123",
        "run-if-new",
        "--",
        sys.executable,
        "-c",
        "print('ok')",
    ]
    assert run(*base).returncode == 0
    assert run(*base).returncode == 1


def test_safe_slug_rejects_path_traversal() -> None:
    slug = _safe_slug("../../etc/passwd")
    # No path separator survives, so the whole traversal string collapses into
    # a single, harmless path segment rather than escaping into parent dirs.
    assert "/" not in slug
    assert "\\" not in slug


def test_safe_slug_strips_null_bytes_and_traversal_chars() -> None:
    slug = _safe_slug("group/repo\x00../evil")
    assert "\x00" not in slug
    assert "/" not in slug
    assert slug == "group_repo_.._evil"


def test_safe_slug_caps_length() -> None:
    slug = _safe_slug("a" * 500)
    assert len(slug) == 128


def test_safe_slug_collapses_all_dots() -> None:
    assert _safe_slug("..") == "_"
    assert _safe_slug(".") == "_"
    assert _safe_slug("") == "_"


def test_safe_slug_neutralizes_leading_dash() -> None:
    assert not _safe_slug("-rf").startswith("-")


def test_store_path_stays_within_root_for_traversal_project(tmp_path: Path) -> None:
    path = _store_path(tmp_path, "../../etc/passwd", 1)
    assert path.parent.parent == tmp_path
    assert ".." not in path.parts


def test_check_with_unusual_project_identifier(tmp_path: Path) -> None:
    # A null byte can't even survive as a literal subprocess argv element (the
    # OS/Python reject it before the script runs), so the CLI-level regression
    # case here uses traversal segments and an oversized identifier instead;
    # the null-byte case is covered directly against _safe_slug() above.
    base = [
        "--store-root",
        str(tmp_path),
        "--project",
        "../../etc/passwd" + "x" * 200,
        "--merge-request-iid",
        "1",
        "--head-sha",
        "abc123",
    ]
    result = run(*base, "check")
    assert result.returncode == 0
    # The store file must land inside store-root, not escape via traversal.
    created = list(tmp_path.rglob("mr-1.json"))
    assert created == []  # "check" alone does not write a record file
    assert run(*base, "mark").returncode == 0
    created = list(tmp_path.rglob("mr-1.json"))
    assert len(created) == 1
    assert tmp_path in created[0].resolve().parents
