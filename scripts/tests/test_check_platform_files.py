"""Tests for the required-platform-files presence check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_platform_files import REQUIRED_PLATFORM_FILES, missing_platform_files  # noqa: E402


def test_check_platform_files_passes_on_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_platform_files.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_missing_platform_files_reports_absent_entries(tmp_path: Path) -> None:
    # Create every required file except one, to confirm the check reports exactly the gap.
    present = REQUIRED_PLATFORM_FILES[:-1]
    absent = REQUIRED_PLATFORM_FILES[-1]
    for relpath in present:
        target = tmp_path / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

    assert missing_platform_files(tmp_path) == [absent]


def test_missing_platform_files_empty_when_all_present(tmp_path: Path) -> None:
    for relpath in REQUIRED_PLATFORM_FILES:
        target = tmp_path / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")

    assert missing_platform_files(tmp_path) == []


def test_required_platform_files_matches_clis_actual_is_file_gates() -> None:
    """REQUIRED_PLATFORM_FILES is a second, independent copy of the paths behind
    scripts/registry/cli.py's `.is_file()` validation-layer gates -- it exists precisely
    because those gates can't be hard-required in cli.py itself without breaking the
    minimal test fixtures other registry tests rely on (see this module's docstring).
    That means nothing forces this list to grow if cli.py ever grows a new gate the same
    way; this test is that tripwire, asserting both lists name exactly the same files.
    """
    from scripts.registry import cli as registry_cli

    cli_gate_paths = {
        registry_cli._capability_catalog_path(ROOT),
        registry_cli._capability_families_path(ROOT),
        registry_cli._release_contract_path(ROOT),
        *registry_cli._p1_layer_paths(ROOT),
    }
    cli_gate_relpaths = {str(path.relative_to(ROOT)) for path in cli_gate_paths}

    assert cli_gate_relpaths == set(REQUIRED_PLATFORM_FILES), (
        "cli.py's .is_file() gate paths and check_platform_files.py's "
        "REQUIRED_PLATFORM_FILES have drifted apart -- update REQUIRED_PLATFORM_FILES "
        "to match."
    )
