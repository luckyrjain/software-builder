"""Tests for scripts/verify_redaction.py — the automated half of log-redaction.md's Phase 5
pre-render checklist (issue #61 item 3)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_redaction.py"

sys.path.insert(0, str(ROOT / "scripts"))
import verify_redaction as verifier  # noqa: E402


def _run(*paths: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(p) for p in paths]],
        capture_output=True,
        text=True,
        check=False,
    )


def test_clean_file_passes(tmp_path: Path):
    f = tmp_path / "evidence.json"
    f.write_text('{"sample_messages": ["payment gateway timeout", "retry succeeded"]}', encoding="utf-8")
    result = _run(f)
    assert result.returncode == 0, result.stdout
    assert "clean" in result.stdout


def test_unredacted_authorization_header_fails(tmp_path: Path):
    f = tmp_path / "evidence.json"
    f.write_text('{"requestHeaders":{"Authorization":"Basic SECRETTOKEN"}}', encoding="utf-8")
    result = _run(f)
    assert result.returncode == 1
    assert f"{f}:1:" in result.stdout


def test_unredacted_api_key_fails(tmp_path: Path):
    f = tmp_path / "evidence.json"
    f.write_text("api_key=sk_live_abcdef1234567890", encoding="utf-8")
    result = _run(f)
    assert result.returncode == 1


def test_unredacted_password_fails(tmp_path: Path):
    f = tmp_path / "evidence.json"
    f.write_text("password=hunter2superSecret", encoding="utf-8")
    result = _run(f)
    assert result.returncode == 1


def test_unredacted_pem_block_fails(tmp_path: Path):
    f = tmp_path / "notes.md"
    f.write_text(
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA1234567890abcdef\n-----END RSA PRIVATE KEY-----",
        encoding="utf-8",
    )
    result = _run(f)
    assert result.returncode == 1


def test_already_redacted_content_passes(tmp_path: Path):
    f = tmp_path / "evidence.json"
    f.write_text('{"requestHeaders":{"Authorization":"[REDACTED]"}, "api_key": "[REDACTED]"}', encoding="utf-8")
    result = _run(f)
    assert result.returncode == 0, result.stdout


def test_straggler_token_after_redacted_marker_still_fails(tmp_path: Path):
    """A marker present but a raw token still trailing it must still be caught — the marker alone
    is not proof of safety."""
    f = tmp_path / "evidence.json"
    f.write_text(
        "requestHeaders={Authorization=[REDACTED] MDEzMUEyRDBDNkY0NEQ0QjFGNDIwODk2NkY1MTlF, x-merchantid=acme}",
        encoding="utf-8",
    )
    result = _run(f)
    assert result.returncode == 1


def test_secret_value_never_appears_in_output(tmp_path: Path):
    """The verifier's own output must not leak the secret it's reporting on."""
    f = tmp_path / "evidence.json"
    f.write_text("api_key=sk_live_THIS_MUST_NOT_APPEAR_IN_OUTPUT", encoding="utf-8")
    result = _run(f)
    assert "THIS_MUST_NOT_APPEAR_IN_OUTPUT" not in result.stdout
    assert "THIS_MUST_NOT_APPEAR_IN_OUTPUT" not in result.stderr


def test_multiple_files_reports_each(tmp_path: Path):
    clean = tmp_path / "clean.json"
    clean.write_text('{"sample_messages": ["ok"]}', encoding="utf-8")
    leaky = tmp_path / "leaky.json"
    leaky.write_text("password=hunter2superSecret", encoding="utf-8")
    result = _run(clean, leaky)
    assert result.returncode == 1
    assert f"{leaky}:1:" in result.stdout
    assert str(clean) not in result.stdout


def test_missing_file_errors(tmp_path: Path):
    result = _run(tmp_path / "does-not-exist.json")
    assert result.returncode == 1
    assert "error" in result.stderr


def test_find_leaky_lines_reports_correct_line_number():
    text = "line one is fine\napi_key=sk_live_secret_value\nline three is fine"
    assert verifier.find_leaky_lines(text) == [2]
