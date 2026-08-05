"""Tests for templates/postman/fetch_otp_from_redis.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "templates" / "postman" / "fetch_otp_from_redis.py"
sys.path.insert(0, str(ROOT / "templates" / "postman"))

from fetch_otp_from_redis import build_key, main  # noqa: E402


def test_build_key_substitutes_identifier() -> None:
    assert build_key("otp:{identifier}", "919999999999") == "otp:919999999999"


def test_build_key_missing_placeholder_raises() -> None:
    with pytest.raises(ValueError):
        build_key("otp:fixed", "919999999999")


def test_build_key_extra_placeholder_raises_value_error() -> None:
    with pytest.raises(ValueError):
        build_key("otp:{identifier}:{tenant}", "919999999999")


def test_main_extra_placeholder_prints_clean_error(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--key-pattern", "otp:{identifier}:{tenant}", "--identifier", "919999999999"])
    assert exit_code == 1
    assert "error:" in capsys.readouterr().err


def test_main_missing_required_args_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0


def test_script_compiles_without_redis_installed() -> None:
    with pytest.raises(ImportError):
        import redis  # noqa: F401
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_module_imports_without_redis_installed() -> None:
    # Importing the module itself must not require `redis` — only calling
    # fetch_otp() should. This is what makes --help usable without the
    # redis package installed.
    import fetch_otp_from_redis

    assert hasattr(fetch_otp_from_redis, "fetch_otp")
