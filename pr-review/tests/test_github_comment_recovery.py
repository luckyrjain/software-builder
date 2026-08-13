"""Executable contract tests for ambiguous GitHub comment-write recovery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "github-comment-recovery.py"
HEAD = "a" * 40
BODY = "Sanitized review body.\n"
IDENTITY = "finding-7"


def run_cli(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        input=input_text,
        capture_output=True,
        check=False,
        text=True,
    )


def prepare() -> dict[str, object]:
    result = run_cli(
        "prepare",
        "--body-stdin",
        "--head-sha",
        HEAD,
        "--comment-kind",
        "inline",
        "--identity",
        IDENTITY,
        input_text=BODY,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def reconcile(tmp_path: Path, comments: list[str], *, complete: bool, attempt: int):
    readback = tmp_path / "comments.json"
    readback.write_text(
        json.dumps({"complete": complete, "comments": [{"body": body} for body in comments]}),
        encoding="utf-8",
    )
    result = run_cli(
        "reconcile",
        "--body-stdin",
        "--head-sha",
        HEAD,
        "--comment-kind",
        "inline",
        "--identity",
        IDENTITY,
        "--readback-file",
        str(readback),
        "--ambiguous-attempt",
        str(attempt),
        input_text=BODY,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_prepare_hashes_only_exact_sanitized_body_before_adding_marker():
    prepared = prepare()
    expected_hash = hashlib.sha256(BODY.encode("utf-8")).hexdigest()
    expected_marker = (
        "<!-- cursor-pr-review-write:v1 "
        f"head={HEAD} kind=inline identity={IDENTITY} body_sha256={expected_hash} -->"
    )
    assert prepared == {
        "body_sha256": expected_hash,
        "marker": expected_marker,
        "post_body": expected_marker + "\n" + BODY,
    }
    assert hashlib.sha256(str(prepared["post_body"]).encode("utf-8")).hexdigest() != expected_hash


def test_complete_readback_with_exact_post_body_accepts_ambiguous_write(tmp_path):
    prepared = prepare()
    assert reconcile(tmp_path, [str(prepared["post_body"])], complete=True, attempt=1) == {
        "outcome": "accepted",
        "retry": False,
    }


def test_complete_readback_proving_absence_allows_one_retry(tmp_path):
    assert reconcile(tmp_path, ["unrelated comment"], complete=True, attempt=1) == {
        "outcome": "absent",
        "retry": True,
    }


def test_second_ambiguous_write_never_allows_another_retry(tmp_path):
    assert reconcile(tmp_path, [], complete=True, attempt=2) == {
        "outcome": "ambiguous",
        "retry": False,
    }


def test_incomplete_paginated_readback_cannot_prove_absence(tmp_path):
    assert reconcile(tmp_path, [], complete=False, attempt=1) == {
        "outcome": "ambiguous",
        "retry": False,
    }
