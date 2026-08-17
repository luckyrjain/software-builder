from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_manifest_yaml import validate_manifest  # noqa: E402


def _manifest() -> dict:
    return yaml.safe_load((ROOT / "templates/manifest.yaml").read_text(encoding="utf-8"))


def _artifact(data: dict, artifact_id: str) -> dict:
    return next(item for item in data["artifacts"] if item["id"] == artifact_id)


def test_prd_may_be_marked_stale_during_in_progress_engagement() -> None:
    data = _manifest()
    _artifact(data, "prd")["status"] = "stale"
    assert validate_manifest(data) == []


def test_stale_status_is_restricted_to_prd_artifact() -> None:
    data = _manifest()
    _artifact(data, "api_event_schema")["status"] = "stale"
    errors = validate_manifest(data)
    assert any("status=stale is only valid for artifact id 'prd'" in error for error in errors)


def test_stale_status_with_unhashable_artifact_id_does_not_crash() -> None:
    # Regression test: the stale-id check used to do a raw `item_id not in
    # STALEABLE_ARTIFACT_IDS` frozenset-membership test, which raises TypeError for an
    # unhashable id (a hand-edited manifest.yaml can put a list/mapping where a string id is
    # expected) instead of reporting a clean validation error.
    data = _manifest()
    item = _artifact(data, "api_event_schema")
    item["id"] = ["not", "a", "string"]
    item["status"] = "stale"
    errors = validate_manifest(data)
    assert any("status=stale is only valid for artifact id 'prd'" in error for error in errors)


def test_stale_prd_blocks_strict_first_pass_completion(tmp_path: Path) -> None:
    data = _manifest()
    data["engagement"]["status"] = "FIRST_PASS_COMPLETE"
    _artifact(data, "prd")["status"] = "stale"
    errors = validate_manifest(data, workspace_root=tmp_path, strict=True)
    assert any("strict: required artifact prd status=stale" in error for error in errors)


def test_stale_prd_still_requires_file_on_disk(tmp_path: Path) -> None:
    data = _manifest()
    prd = _artifact(data, "prd")
    prd["status"] = "stale"
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert any("artifact file missing on disk: PRD.md (status=stale)" in error for error in errors)

    (tmp_path / "PRD.md").write_text("# stale baseline\n", encoding="utf-8")
    errors_with_file = validate_manifest(data, workspace_root=tmp_path)
    assert not any("PRD.md (status=stale)" in error for error in errors_with_file)
