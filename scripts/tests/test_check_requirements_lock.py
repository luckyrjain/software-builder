"""Tests for requirements.lock consistency checks."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_requirements_lock import (  # noqa: E402
    direct_package_names_from_lock,
    package_names_from_requirements,
    unsatisfied_locked_requirements,
)


def test_check_requirements_lock_passes_on_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_requirements_lock.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_direct_lock_entries_match_requirements_txt() -> None:
    required = package_names_from_requirements(ROOT / "requirements.txt")
    direct_locked = direct_package_names_from_lock(ROOT / "requirements.lock")
    assert required == direct_locked


def test_extra_direct_lock_entry_fails(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text("pytest>=9.1.1\n", encoding="utf-8")
    lockfile.write_text(
        "pytest==9.1.1 \\\n    # via -r requirements.txt\n"
        "orphan==1.0.0 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    required = package_names_from_requirements(requirements)
    direct_locked = direct_package_names_from_lock(lockfile)
    assert "orphan" in direct_locked - required


def test_unsatisfied_locked_version_is_reported(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text("sqlglot>=30.17.0\n", encoding="utf-8")
    lockfile.write_text(
        "sqlglot==30.15.0 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert unsatisfied_locked_requirements(requirements, lockfile) == [
        "sqlglot==30.15.0 does not satisfy sqlglot>=30.17.0"
    ]


def test_multiline_uv_provenance_marks_direct_entry(tmp_path: Path) -> None:
    lockfile = tmp_path / "requirements.lock"
    lockfile.write_text(
        """packaging==26.3 \\
    --hash=sha256:example
    # via
    #   pytest
    #   -r requirements.txt
""",
        encoding="utf-8",
    )

    assert direct_package_names_from_lock(lockfile) == {"packaging"}


def test_duplicate_constraints_and_lock_target_markers_are_supported(
    tmp_path: Path,
) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text(
        "demo>=1\ndemo<3\n"
        "active>=2; python_version >= '3.12'\n"
        "inactive>=99; python_version < '3.12'\n",
        encoding="utf-8",
    )
    lockfile.write_text(
        "active==2 \\\n    # via -r requirements.txt\n"
        "demo==2.0 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert package_names_from_requirements(requirements) == {"active", "demo"}
    assert unsatisfied_locked_requirements(requirements, lockfile) == []


def test_arbitrary_equality_uses_pep440_specifier_semantics(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text("demo===legacy\n", encoding="utf-8")
    lockfile.write_text(
        "demo==legacy \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert unsatisfied_locked_requirements(requirements, lockfile) == []


def test_cli_rejects_unsatisfied_version_with_error_output(tmp_path: Path) -> None:
    script = tmp_path / "scripts" / "check_requirements_lock.py"
    script.parent.mkdir()
    script.write_text(
        (ROOT / "scripts" / "check_requirements_lock.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    (tmp_path / "requirements.txt").write_text("demo>=2\n", encoding="utf-8")
    (tmp_path / "requirements.lock").write_text(
        "demo==1 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "does not satisfy demo>=2" in result.stderr


def test_duplicate_direct_lock_entries_are_rejected(tmp_path: Path) -> None:
    lockfile = tmp_path / "requirements.lock"
    lockfile.write_text(
        "demo==1 \\\n    # via -r requirements.txt\n"
        "demo==1 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate direct lock entry: demo"):
        direct_package_names_from_lock(lockfile)


def test_inline_comments_and_linux_markers_are_supported(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text(
        "demo>=1  # kept for the checker\n"
        "linux-only>=2; sys_platform == 'linux'\n"
        "windows-only>=2; sys_platform == 'win32'\n",
        encoding="utf-8",
    )
    lockfile.write_text(
        "demo==1 \\\n    # via -r requirements.txt\n"
        "linux-only==2 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert package_names_from_requirements(requirements) == {"demo", "linux-only"}
    assert unsatisfied_locked_requirements(requirements, lockfile) == []


def test_malformed_lock_entry_cannot_reuse_prior_parser_state(tmp_path: Path) -> None:
    lockfile = tmp_path / "requirements.lock"
    lockfile.write_text(
        "first==1 \\\n    # via pytest\n"
        "demo==2 garbage \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert direct_package_names_from_lock(lockfile) == set()


def test_unknown_platform_marker_is_rejected_fail_closed(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    requirements.write_text(
        "demo>=1; platform_release == 'known-kernel'\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="platform_release"):
        package_names_from_requirements(requirements)


def test_comment_stripping_respects_quoted_marker_values(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text(
        'demo>=1; python_version != "3.12 # literal"\n',
        encoding="utf-8",
    )
    lockfile.write_text(
        "demo==1 \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert package_names_from_requirements(requirements) == {"demo"}
    assert unsatisfied_locked_requirements(requirements, lockfile) == []


def test_unconstrained_requirement_rejects_invalid_lock_version(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements.txt"
    lockfile = tmp_path / "requirements.lock"
    requirements.write_text("demo\n", encoding="utf-8")
    lockfile.write_text(
        "demo==not-a-version \\\n    # via -r requirements.txt\n",
        encoding="utf-8",
    )

    assert unsatisfied_locked_requirements(requirements, lockfile) == [
        "demo==not-a-version is not a valid package version"
    ]

