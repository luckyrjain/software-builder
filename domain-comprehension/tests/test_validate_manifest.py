"""Tests for validate_manifest_yaml.py"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_manifest_yaml import validate_manifest  # noqa: E402

pytest.importorskip("yaml")


def _minimal_manifest() -> dict:
    template = ROOT / "templates" / "manifest.yaml"
    import yaml

    return yaml.safe_load(template.read_text(encoding="utf-8"))


def test_minimal_template_validates() -> None:
    errors = validate_manifest(_minimal_manifest())
    assert errors == []


def test_missing_schema_version() -> None:
    data = _minimal_manifest()
    del data["schema_version"]
    errors = validate_manifest(data)
    assert any("schema_version" in e for e in errors)


def test_complete_phase_requires_completed_at() -> None:
    data = _minimal_manifest()
    data["phases"]["session_0"]["status"] = "complete"
    data["phases"]["session_0"]["completed_at"] = None
    errors = validate_manifest(data)
    assert any("session_0.completed_at" in e for e in errors)


def test_skipped_phase_requires_reason() -> None:
    data = _minimal_manifest()
    data["phases"]["p2b"]["status"] = "skipped"
    data["phases"]["p2b"]["skip_reason"] = None
    errors = validate_manifest(data)
    assert any("p2b.skip_reason" in e for e in errors)


def test_strict_first_pass_incomplete(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["engagement"]["status"] = "FIRST_PASS_COMPLETE"
    errors = validate_manifest(data, workspace_root=tmp_path, strict=True)
    assert any("strict:" in e for e in errors)


def test_workspace_root_checks_stub_files(tmp_path: Path) -> None:
    data = _minimal_manifest()
    (tmp_path / "domain-config.yaml").write_text("domain: {}\n", encoding="utf-8")
    data["artifacts"][0]["status"] = "stub"
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert not any("domain-config.yaml" in e for e in errors)

    (tmp_path / "domain-config.yaml").unlink()
    errors_missing = validate_manifest(_minimal_manifest(), workspace_root=tmp_path)
    assert any("domain-config.yaml" in e for e in errors_missing)


def test_schema_version_one_rejected() -> None:
    data = _minimal_manifest()
    data["schema_version"] = 1
    errors = validate_manifest(data)
    assert any("schema_version" in e for e in errors)


def test_invalid_repo_classification() -> None:
    data = _minimal_manifest()
    data["repos"] = [{"name": "foo", "classification": "ACTIVE"}]
    errors = validate_manifest(data)
    assert any("classification invalid" in e for e in errors)


def test_evidence_summary_negative_rejected() -> None:
    data = _minimal_manifest()
    data["evidence_summary"]["files_inspected"] = -1
    errors = validate_manifest(data)
    assert any("files_inspected" in e for e in errors)


def test_evidence_summary_boolean_count_rejected() -> None:
    # bool is a subclass of int in Python, so a bare `isinstance(x, int)` check silently accepts
    # `true`/`false` wherever a count is expected — same footgun _plain_int() guards against for
    # schema_version and discovery_budget counters.
    data = _minimal_manifest()
    data["evidence_summary"]["files_inspected"] = True
    errors = validate_manifest(data)
    assert any("evidence_summary.files_inspected must be an integer" in e for e in errors)


def test_runtime_validation_boolean_count_rejected() -> None:
    data = _minimal_manifest()
    data["runtime_validation"]["edges_total"] = False
    errors = validate_manifest(data)
    assert any("runtime_validation.edges_total must be an integer" in e for e in errors)


def test_runtime_validation_negative_rejected() -> None:
    # Unlike evidence_summary's counters (see test_evidence_summary_negative_rejected), the
    # runtime_validation.edges_total/edges_confirmed checks had no >= 0 guard, so a negative
    # count silently validated clean.
    data = _minimal_manifest()
    data["runtime_validation"]["edges_confirmed"] = -1
    errors = validate_manifest(data)
    assert any("runtime_validation.edges_confirmed must be >= 0" in e for e in errors)


def test_check_content_p2b_pending_skips_runtime_gate(tmp_path: Path) -> None:
    data = _minimal_manifest()
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("P2b complete" in e for e in errors)


def test_check_content_exec_summary_sections(tmp_path: Path) -> None:
    data = _minimal_manifest()
    (tmp_path / "EXEC_SUMMARY.md").write_text("# Executive Summary\n\n## Draft Five Questions\n", encoding="utf-8")
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("Evidence summary" in e for e in errors)
    assert any("Engineering Leader Summary" in e for e in errors)


def test_check_content_p2b_runtime_in_map(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p2b"]["status"] = "complete"
    data["phases"]["p2b"]["completed_at"] = "2026-07-02T00:00:00Z"
    (tmp_path / "DOMAIN_MAP.md").write_text("## Runtime validation (Datadog)\n\n| hop |\n", encoding="utf-8")
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("P2b complete" in e for e in errors)


def test_check_content_p2b_e2e_supplement_requires_map_link(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p2b"]["status"] = "complete"
    data["phases"]["p2b"]["completed_at"] = "2026-07-02T00:00:00Z"
    (tmp_path / "DOMAIN_MAP.md").write_text("# Map\n", encoding="utf-8")
    (tmp_path / "E2E_FLOW.md").write_text("## Runtime validation\n\n| hop |\n", encoding="utf-8")
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("link to E2E_FLOW.md" in e for e in errors)


def test_check_content_p2b_e2e_supplement_with_link(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p2b"]["status"] = "complete"
    data["phases"]["p2b"]["completed_at"] = "2026-07-02T00:00:00Z"
    (tmp_path / "DOMAIN_MAP.md").write_text(
        "## Runtime validation (Datadog)\n\nSee E2E_FLOW.md for full table.\n",
        encoding="utf-8",
    )
    (tmp_path / "E2E_FLOW.md").write_text("## Runtime validation\n\n| hop |\n", encoding="utf-8")
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("P2b complete" in e for e in errors)


def test_check_content_merge_conflict_open_blocks_p0_p1_complete(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    data["phases"]["p1"]["status"] = "complete"
    data["phases"]["p1"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | HIGH | open |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p0 must not be complete" in e for e in errors)
    assert any("phases.p1 must not be complete" in e for e in errors)


def test_check_content_merge_conflict_resolved_allows_complete(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | HIGH | resolved |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("Merge Conflicts" in e for e in errors)


def test_check_content_no_risk_map_skips_merge_conflicts_gate(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("Merge Conflicts" in e for e in errors)


def test_check_content_merge_conflict_backticked_status_blocks(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | HIGH | `open` |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p0 must not be complete" in e for e in errors)


def test_check_content_merge_conflict_status_prefixed_value_blocks(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | HIGH | Status: open |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p0 must not be complete" in e for e in errors)


def test_check_content_merge_conflict_header_resolution_survives_extra_column(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p1"]["status"] = "complete"
    data["phases"]["p1"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | HIGH | open |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p1 must not be complete" in e for e in errors)


def test_check_content_merge_conflict_header_resolution_ignores_extra_trailing_cell(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p1"]["status"] = "complete"
    data["phases"]["p1"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | HIGH | open | Notes: pending review |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p1 must not be complete" in e for e in errors)


def test_check_content_merge_conflict_dash_evidence_not_mistaken_for_separator(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Foo---Bar.java:12 | svc-b/Repo.java:9 | HIGH | open |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p0 must not be complete" in e for e in errors)


def test_check_content_merge_conflict_second_table_in_section_detected(tmp_path: Path) -> None:
    """A second table under the same heading must get its own header row, not the first table's.

    Without resetting header/column tracking between tables, the second table's header row is
    read as a data row against the first table's column index, so an `open` status in a
    differently-ordered second table can be missed entirely.
    """
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "First table already resolved:\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | HIGH | resolved |\n"
        "\n"
        "Second table, columns in a different order, still open:\n\n"
        "| Status | New repo | Entity/Context/Path |\n"
        "|--------|----------|----------------------|\n"
        "| open | svc-c | orders table |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p0 must not be complete" in e for e in errors)


def _mark_api_tooling_ok(data: dict) -> None:
    for artifact in data["artifacts"]:
        if artifact["id"] == "api_tooling_export":
            artifact["status"] = "ok"
            return
    raise AssertionError("api_tooling_export artifact not found in template — run Task 1 first")


def test_check_content_api_tooling_ok_valid_collection_passes(tmp_path: Path) -> None:
    data = _minimal_manifest()
    _mark_api_tooling_ok(data)
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    postman_dir = tmp_path / "postman"
    postman_dir.mkdir()
    (postman_dir / "postman_collection.json").write_text(
        '{"info": {"name": "x"}, "item": []}', encoding="utf-8"
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("api_tooling_export" in e or "postman_collection.json" in e for e in errors)


def test_check_content_api_tooling_ok_missing_file_fails(tmp_path: Path) -> None:
    data = _minimal_manifest()
    _mark_api_tooling_ok(data)
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("postman/postman_collection.json is missing" in e for e in errors)


def test_check_content_api_tooling_ok_invalid_json_fails(tmp_path: Path) -> None:
    data = _minimal_manifest()
    _mark_api_tooling_ok(data)
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    postman_dir = tmp_path / "postman"
    postman_dir.mkdir()
    (postman_dir / "postman_collection.json").write_text("{not valid json", encoding="utf-8")
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("invalid JSON" in e for e in errors)


def test_check_content_api_tooling_n_a_skips_check(tmp_path: Path) -> None:
    data = _minimal_manifest()
    # api_tooling_export stays at its template default status: n_a
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("api_tooling_export" in e or "postman_collection.json" in e for e in errors)


# --- engagement.artifact_root (issue #55) -----------------------------------------------------


def test_artifact_root_unset_resolves_directly_under_workspace_root(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["artifacts"][0]["status"] = "stub"
    (tmp_path / "domain-config.yaml").write_text("domain: {}\n", encoding="utf-8")
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert not any("domain-config.yaml" in e for e in errors)


def test_artifact_root_set_resolves_artifacts_under_subdirectory(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["engagement"]["artifact_root"] = ".domain-comprehension/20260809T060000Z"
    data["artifacts"][0]["status"] = "stub"

    # Not at workspace_root directly — must be missing until placed under artifact_root.
    errors_missing = validate_manifest(data, workspace_root=tmp_path)
    assert any("domain-config.yaml" in e for e in errors_missing)

    run_dir = tmp_path / ".domain-comprehension" / "20260809T060000Z"
    run_dir.mkdir(parents=True)
    (run_dir / "domain-config.yaml").write_text("domain: {}\n", encoding="utf-8")
    errors_found = validate_manifest(data, workspace_root=tmp_path)
    assert not any("domain-config.yaml" in e for e in errors_found)


def test_artifact_root_absolute_path_rejected(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["engagement"]["artifact_root"] = "/etc/somewhere"
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert any("artifact_root must be a relative path" in e for e in errors)


def test_artifact_root_parent_traversal_rejected(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["engagement"]["artifact_root"] = "../escape"
    errors = validate_manifest(data, workspace_root=tmp_path)
    assert any("artifact_root must be a relative path" in e for e in errors)


def test_check_content_exec_summary_resolves_under_artifact_root(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["engagement"]["artifact_root"] = "run-a"
    run_dir = tmp_path / "run-a"
    run_dir.mkdir()
    (run_dir / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("EXEC_SUMMARY.md" in e for e in errors)

    # The same content at workspace_root (not under artifact_root) must NOT satisfy the check.
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (run_dir / "EXEC_SUMMARY.md").unlink()
    errors_wrong_location = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("EXEC_SUMMARY.md" in e for e in errors_wrong_location)
