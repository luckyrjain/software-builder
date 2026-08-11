"""Tests for the pinned-GitHub-Actions policy check."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from check_pinned_actions import find_unpinned_actions  # noqa: E402


def test_check_pinned_actions_passes_on_repo() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_pinned_actions.py")],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_sha_pinned_action_passes(tmp_path: Path) -> None:
    workflow = tmp_path / "ok.yml"
    workflow.write_text(
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n",
        encoding="utf-8",
    )
    assert find_unpinned_actions(workflow) == []


def test_uppercase_sha_passes(tmp_path: Path) -> None:
    # Regression: git/GitHub both accept upper- and lower-case hex SHAs interchangeably (they
    # refer to the identical commit), but an earlier lowercase-only regex rejected an uppercase
    # pin as a "mutable ref" — a false positive on a perfectly valid, immutable pin.
    workflow = tmp_path / "ok-upper.yml"
    workflow.write_text(
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@3D3C42E5AAC5BA805825DA76410C181273BA90B1 # v7.0.1\n",
        encoding="utf-8",
    )
    assert find_unpinned_actions(workflow) == []


def test_mutable_tag_fails(tmp_path: Path) -> None:
    workflow = tmp_path / "bad.yml"
    workflow.write_text(
        "jobs:\n"
        "  build:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/checkout@v4\n",
        encoding="utf-8",
    )
    errors = find_unpinned_actions(workflow)
    assert len(errors) == 1
    assert "actions/checkout@v4" in errors[0]
    assert "mutable ref" in errors[0]


def test_mutable_branch_ref_fails(tmp_path: Path) -> None:
    workflow = tmp_path / "bad-branch.yml"
    workflow.write_text(
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - uses: some-org/some-action@main\n",
        encoding="utf-8",
    )
    errors = find_unpinned_actions(workflow)
    assert len(errors) == 1
    assert "main" in errors[0]


def test_local_reusable_workflow_is_exempt(tmp_path: Path) -> None:
    workflow = tmp_path / "local.yml"
    workflow.write_text(
        "jobs:\n"
        "  call:\n"
        "    uses: ./.github/workflows/lint.yml\n",
        encoding="utf-8",
    )
    assert find_unpinned_actions(workflow) == []


def test_docker_reference_is_exempt(tmp_path: Path) -> None:
    workflow = tmp_path / "docker.yml"
    workflow.write_text(
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - uses: docker://ghcr.io/some/image:latest\n",
        encoding="utf-8",
    )
    assert find_unpinned_actions(workflow) == []


def test_short_sha_still_flagged(tmp_path: Path) -> None:
    # A short (abbreviated) commit SHA isn't stable the way a full 40-char SHA is — GitHub
    # itself only guarantees uniqueness for the full form, and a short prefix could
    # theoretically collide as the repo grows. Reject anything shorter than 40 hex chars.
    workflow = tmp_path / "short-sha.yml"
    workflow.write_text(
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - uses: actions/checkout@3d3c42e\n",
        encoding="utf-8",
    )
    errors = find_unpinned_actions(workflow)
    assert len(errors) == 1
    assert "mutable ref" in errors[0]
