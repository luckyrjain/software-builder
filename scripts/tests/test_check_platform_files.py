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


def test_required_platform_files_covers_clis_actual_is_file_gates() -> None:
    """REQUIRED_PLATFORM_FILES is derived from scripts/registry/cli.py's own
    `optional_layer_paths` rather than hand-copied beside it, so a new `.is_file()` gate
    joins this inventory automatically. This asserts that derivation still holds -- and
    that the three generated contract projections, which no gate keys off of but which
    `make generate` maintains, remain covered too.
    """
    from scripts.registry.canonical_manifest import LEGACY_PROJECTION_FILENAMES, legacy_projection_path
    from scripts.registry import cli as registry_cli

    gate_relpaths = {
        str(path.relative_to(ROOT)) for path in registry_cli.optional_layer_paths(ROOT)
    }
    projection_relpaths = {
        str(legacy_projection_path(ROOT, section).relative_to(ROOT))
        for section in LEGACY_PROJECTION_FILENAMES
    }

    assert gate_relpaths | projection_relpaths == set(REQUIRED_PLATFORM_FILES)


def test_deleting_a_generated_contract_projection_fails_the_check(tmp_path: Path) -> None:
    """The inventory's whole purpose: a file whose absence disables or staleness-hides a
    layer must fail loudly here. composition_runtime.yaml used to be absent from the
    hand-maintained list and was caught only incidentally by `generate --check`."""
    for relpath in REQUIRED_PLATFORM_FILES:
        target = tmp_path / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("", encoding="utf-8")
    (tmp_path / "scripts" / "registry" / "composition_runtime.yaml").unlink()

    assert missing_platform_files(tmp_path) == ["scripts/registry/composition_runtime.yaml"]
