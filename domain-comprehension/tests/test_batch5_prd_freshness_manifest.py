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
    assert any("artifact prd must have status=ok" in error for error in errors)


def test_waived_prd_blocks_strict_first_pass_completion(tmp_path: Path) -> None:
    data = _manifest()
    data["engagement"]["status"] = "FIRST_PASS_COMPLETE"
    _artifact(data, "prd")["status"] = "waived"
    errors = validate_manifest(data, workspace_root=tmp_path, strict=True)
    assert any("artifact prd must have status=ok" in error for error in errors)


def test_optional_prd_row_blocks_strict_first_pass_completion(tmp_path: Path) -> None:
    data = _manifest()
    data["engagement"]["status"] = "FIRST_PASS_COMPLETE"
    prd = _artifact(data, "prd")
    prd["required"] = False
    prd["status"] = "stale"
    errors = validate_manifest(data, workspace_root=tmp_path, strict=True)
    assert any("artifact prd must have required=true" in error for error in errors)
    assert any("artifact prd must have status=ok" in error for error in errors)


def test_missing_machine_artifact_blocks_strict_first_pass_completion(tmp_path: Path) -> None:
    data = _manifest()
    data["engagement"]["status"] = "FIRST_PASS_COMPLETE"
    data["artifacts"] = [
        item
        for item in data["artifacts"]
        if item["id"] != "dependency_graph_machine"
    ]
    errors = validate_manifest(data, workspace_root=tmp_path, strict=True)
    assert any(
        "required machine artifact dependency_graph_machine is missing" in error
        for error in errors
    )


def test_first_pass_complete_stale_prd_fails_without_strict_or_workspace() -> None:
    data = _manifest()
    data["engagement"]["status"] = "FIRST_PASS_COMPLETE"
    _artifact(data, "prd")["status"] = "stale"
    errors = validate_manifest(data)
    assert any("artifact prd must have status=ok" in error for error in errors)


def test_waived_machine_artifacts_block_prd_ok_under_first_pass_complete() -> None:
    data = _manifest()
    data["engagement"]["status"] = "FIRST_PASS_COMPLETE"
    _artifact(data, "prd")["status"] = "ok"
    for artifact_id in (
        "api_event_schema",
        "data_ownership_graph",
        "dependency_graph_machine",
        "capability_traceability",
    ):
        _artifact(data, artifact_id)["status"] = "waived"
    errors = validate_manifest(data)
    assert any(
        "PRD status=ok is forbidden while required machine artifact(s) are waived" in error
        for error in errors
    )


def test_p5_complete_blocks_stale_prd_without_strict() -> None:
    data = _manifest()
    data["phases"]["p5"]["status"] = "complete"
    data["phases"]["p5"]["completed_at"] = "2026-08-17T00:00:00Z"
    _artifact(data, "prd")["status"] = "stale"
    errors = validate_manifest(data)
    assert any(
        "phases.p5 cannot be complete while artifacts[id=prd].status is 'stale'" in error
        for error in errors
    )


def test_p5_complete_requires_prd_ok_not_stub() -> None:
    data = _manifest()
    data["phases"]["p5"]["status"] = "complete"
    data["phases"]["p5"]["completed_at"] = "2026-08-17T00:00:00Z"
    _artifact(data, "prd")["status"] = "stub"
    errors = validate_manifest(data)
    assert any(
        "phases.p5 cannot be complete while artifacts[id=prd].status is 'stub'" in error
        for error in errors
    )


def test_p5_complete_requires_prd_row() -> None:
    data = _manifest()
    data["phases"]["p5"]["status"] = "complete"
    data["phases"]["p5"]["completed_at"] = "2026-08-17T00:00:00Z"
    data["artifacts"] = [item for item in data["artifacts"] if item["id"] != "prd"]
    errors = validate_manifest(data)
    assert any(
        "phases.p5 cannot be complete while artifacts[id=prd] is missing" in error
        for error in errors
    )


def test_machine_artifact_ok_requires_source_revision_repos(tmp_path: Path) -> None:
    data = _manifest()
    machine = _artifact(data, "api_event_schema")
    machine["status"] = "ok"
    (tmp_path / "API_EVENT_SCHEMA.yaml").write_text(
        "schema_version: 1\nsource_revision:\n  repos: []\nrecords: []\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert any(
        "api_event_schema source_revision.repos must be a non-empty list" in error
        for error in errors
    )


def test_machine_artifact_ok_rejects_hollow_source_revision_repos(tmp_path: Path) -> None:
    data = _manifest()
    machine = _artifact(data, "api_event_schema")
    machine["status"] = "ok"
    (tmp_path / "API_EVENT_SCHEMA.yaml").write_text(
        "schema_version: 1\nsource_revision:\n  repos:\n    - {}\nrecords: []\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert any("source_revision.repos[0].repo must be a non-empty string" in error for error in errors)
    assert any("commit_sha must be a non-empty string" in error for error in errors)


def test_machine_artifact_directory_path_rejected(tmp_path: Path) -> None:
    data = _manifest()
    machine = _artifact(data, "api_event_schema")
    machine["status"] = "ok"
    machine["path"] = "API_EVENT_SCHEMA.yaml/"
    (tmp_path / "API_EVENT_SCHEMA.yaml").mkdir()
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert any(
        "machine artifact api_event_schema path must be a file, not a directory" in error
        for error in errors
    )
    assert not any("schema_version" in error for error in errors)  # content check must not be skipped via dir


def test_stale_prd_still_requires_file_on_disk(tmp_path: Path) -> None:
    data = _manifest()
    prd = _artifact(data, "prd")
    prd["status"] = "stale"
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert any("artifact file missing on disk: PRD.md (status=stale)" in error for error in errors)

    (tmp_path / "PRD.md").write_text("# stale baseline\n", encoding="utf-8")
    errors_with_file = validate_manifest(data, workspace_root=tmp_path)
    assert not any("PRD.md (status=stale)" in error for error in errors_with_file)
