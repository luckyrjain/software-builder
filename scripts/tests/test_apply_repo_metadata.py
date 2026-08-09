"""Tests for apply_repo_metadata.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.apply_repo_metadata import _load_metadata, apply_metadata


def test_load_metadata_parses_description_and_topics(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/repo-metadata.yaml").write_text(
        "description: Hello world\n"
        "topics:\n"
        "  - cursor\n"
        "  - agents\n",
        encoding="utf-8",
    )
    description, topics = _load_metadata(tmp_path)
    assert description == "Hello world"
    assert topics == ["cursor", "agents"]


@patch("scripts.apply_repo_metadata.subprocess.run")
def test_apply_metadata_syncs_topic_add_and_remove(mock_run: MagicMock, tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github/repo-metadata.yaml").write_text(
        "description: Demo repo\n"
        "topics:\n"
        "  - cursor\n"
        "  - agents\n",
        encoding="utf-8",
    )

    def run_side_effect(cmd, **kwargs):
        result = MagicMock()
        result.returncode = 0
        if cmd[:3] == ["git", "-C", str(tmp_path)]:
            result.stdout = f"{tmp_path}\n"
            return result
        if cmd[:3] == ["gh", "repo", "view"]:
            result.stdout = '{"repositoryTopics":[{"name":"cursor"},{"name":"stale-topic"}]}'
            return result
        result.returncode = 0
        return result

    mock_run.side_effect = run_side_effect

    apply_metadata(tmp_path, dry_run=False)

    edit_calls = [
        call
        for call in mock_run.call_args_list
        if call.args and call.args[0][:3] == ["gh", "repo", "edit"]
    ]
    assert len(edit_calls) == 1
    edit_cmd = edit_calls[0].args[0]
    assert "--remove-topic" in edit_cmd
    assert "stale-topic" in edit_cmd
    assert "--add-topic" in edit_cmd
    assert "agents" in edit_cmd
    assert edit_calls[0].kwargs["cwd"] == tmp_path
