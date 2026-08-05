"""Scripted eval for migration-program-manager's aggregator."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import pytest  # noqa: E402

from aggregate_migration_status import (  # noqa: E402
    build_rollup,
    compute_staleness,
    derive_status,
    gate_signature,
    join_squad,
    load_manifest,
    load_state,
    normalize_confidence,
    parse_migration_status,
    parse_squad_map,
    ManifestEntry,
    ManifestError,
)

SQUAD_MAP_FIXTURE = """# Squad Map

**MCP profile:** GitLab OK
**Last run:** 2026-08-01T00:00:00Z

## Repo → squad

| Repo | GitLab namespace | GitLab squad | Datadog service | Datadog team | Confidence | Evidence |
|------|------------------|--------------|-----------------|--------------|------------|----------|
| api-disbursement | acme/disbursement/api-disbursement | disbursement | disbursement-service | disbursement-platform | HIGH | evidence here |
| api-payouts | acme/payouts/api-payouts | payouts | payouts-service | payouts-platform | MEDIUM | evidence here |

## Conflicts (GitLab squad ≠ Datadog team)

| Repo | GitLab squad | Datadog team | Notes |
|------|--------------|--------------|-------|
| legacy-ledger | payments | collections | mismatch |

## Unmapped repos

| Repo | Reason |
|------|--------|
| some-tool | no CODEOWNERS |

## Out of scope (archived)

| Repo | Prior GitLab squad | Prior Datadog team | Archived at |
|------|---------------------|---------------------|-------------|
| old-repo | payments | payments | 2026-07-01T00:00:00Z |
"""


class TestParseSquadMap:
    def test_parses_main_table_only(self, tmp_path):
        p = tmp_path / "SQUAD_MAP.md"
        p.write_text(SQUAD_MAP_FIXTURE, encoding="utf-8")
        rows = parse_squad_map(p)
        assert len(rows) == 2
        assert rows[0]["Repo"] == "api-disbursement"
        assert rows[0]["GitLab squad"] == "disbursement"

    def test_excludes_conflicts_unmapped_archived_rows(self, tmp_path):
        p = tmp_path / "SQUAD_MAP.md"
        p.write_text(SQUAD_MAP_FIXTURE, encoding="utf-8")
        rows = parse_squad_map(p)
        repos = {r["Repo"] for r in rows}
        assert "legacy-ledger" not in repos
        assert "some-tool" not in repos
        assert "old-repo" not in repos

    def test_missing_file_returns_empty(self, tmp_path):
        assert parse_squad_map(tmp_path / "nope.md") == []


class TestJoinSquad:
    def test_matches_by_path(self):
        rows = [{"Repo": "api-disbursement", "GitLab squad": "disbursement", "Confidence": "HIGH"}]
        squad, confidence = join_squad("api-disbursement", "disbursement-svc", rows)
        assert squad == "disbursement"
        assert confidence == "HIGH"

    def test_falls_back_to_name(self):
        rows = [{"Repo": "api-payouts", "GitLab squad": "payouts", "Confidence": "MEDIUM"}]
        squad, confidence = join_squad("some/other/path", "api-payouts", rows)
        assert squad == "payouts"

    def test_unknown_when_no_match(self):
        squad, confidence = join_squad("nope", "nope", [])
        assert squad == "UNKNOWN"
        assert confidence == "UNKNOWN"

    def test_conflict_row_prefers_datadog_team_over_gitlab_squad(self):
        # squad-map's own documented tiebreak (runtime ownership over static GitLab grouping,
        # per org-rollup-schema.md and squad-mapping.md's Reconciliation table) -- never GitLab
        # squad when the two disagree.
        rows = [{"Repo": "legacy-ledger", "GitLab squad": "payments", "Datadog team": "collections", "Confidence": "MEDIUM"}]
        squad, confidence = join_squad("legacy-ledger", "legacy-ledger", rows)
        assert squad == "collections"

    def test_confidence_annotation_normalized_to_enum(self):
        rows = [{"Repo": "legacy-ledger", "GitLab squad": "payments", "Datadog team": "collections", "Confidence": "MEDIUM ⚠️ conflict"}]
        _, confidence = join_squad("legacy-ledger", "legacy-ledger", rows)
        assert confidence == "MEDIUM"


class TestNormalizeConfidence:
    def test_plain_values_pass_through(self):
        assert normalize_confidence("HIGH") == "HIGH"
        assert normalize_confidence("low") == "LOW"

    def test_unrecognized_or_empty_falls_back_to_unknown(self):
        assert normalize_confidence("") == "UNKNOWN"
        assert normalize_confidence(None) == "UNKNOWN"
        assert normalize_confidence("n/a") == "UNKNOWN"


class TestDeriveStatus:
    def test_blocked_on_any_fail(self):
        assert derive_status({"scan_gate": "fail", "shadow_compare": "pending", "config_cutover": "pending"}) == "blocked"

    def test_done_when_all_pass(self):
        assert derive_status({"scan_gate": "pass", "shadow_compare": "pass", "config_cutover": "done"}) == "done"

    def test_in_progress_otherwise(self):
        assert derive_status({"scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"}) == "in_progress"

    def test_done_when_dialect_only_gates_are_not_applicable(self):
        # mysql-to-postgres-sql's own template documents n/a as the legitimate terminal value for
        # a dialect-only service with nothing to shadow-compare or cut over.
        assert derive_status({"scan_gate": "pass", "shadow_compare": "n/a", "config_cutover": "n/a"}) == "done"


class TestStaleness:
    def test_first_observation_is_zero(self):
        now = datetime.now(timezone.utc)
        svc = {"name": "api-disbursement", "scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"}
        days, entry = compute_staleness("ws1", svc, {}, now)
        assert days == 0
        assert entry["gate_signature"] == gate_signature(svc)

    def test_unchanged_signature_accrues_staleness(self):
        now = datetime.now(timezone.utc)
        svc = {"name": "api-disbursement", "scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"}
        ten_days_ago = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {"ws1::api-disbursement": {"gate_signature": gate_signature(svc), "first_observed_at": ten_days_ago}}
        days, entry = compute_staleness("ws1", svc, state, now)
        assert days == 10

    def test_changed_signature_resets_to_zero(self):
        now = datetime.now(timezone.utc)
        old_svc = {"name": "api-disbursement", "scan_gate": "pending", "shadow_compare": "pending", "config_cutover": "pending"}
        new_svc = {"name": "api-disbursement", "scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"}
        ten_days_ago = (now - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {"ws1::api-disbursement": {"gate_signature": gate_signature(old_svc), "first_observed_at": ten_days_ago}}
        days, entry = compute_staleness("ws1", new_svc, state, now)
        assert days == 0
        assert entry["gate_signature"] == gate_signature(new_svc)

    def test_missing_first_observed_at_treated_as_first_observation(self):
        now = datetime.now(timezone.utc)
        svc = {"name": "api-disbursement", "scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"}
        state = {"ws1::api-disbursement": {"gate_signature": gate_signature(svc)}}
        days, entry = compute_staleness("ws1", svc, state, now)
        assert days == 0
        assert entry["gate_signature"] == gate_signature(svc)

    def test_unparseable_first_observed_at_treated_as_first_observation(self):
        now = datetime.now(timezone.utc)
        svc = {"name": "api-disbursement", "scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"}
        state = {"ws1::api-disbursement": {"gate_signature": gate_signature(svc), "first_observed_at": "not-a-date"}}
        days, entry = compute_staleness("ws1", svc, state, now)
        assert days == 0


class TestBuildRollup:
    def test_missing_migration_status_is_a_gap_not_a_crash(self, tmp_path):
        ws = tmp_path / "empty-workspace"
        ws.mkdir()
        manifest = [ManifestEntry(workspace_root=str(ws))]
        items, gaps, state = build_rollup(manifest, {}, datetime.now(timezone.utc), staleness_threshold_days=14)
        assert items == []
        assert len(gaps) == 1
        assert "MIGRATION_STATUS.yaml not found" in gaps[0].reason

    def test_missing_squad_map_yields_unknown_squad_not_a_crash(self, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text(
            "schema_version: 1\nservices:\n  - name: api-disbursement\n    path: api-disbursement\n"
            "    tier_focus: P0\n    scan_gate: pass\n    shadow_compare: pending\n    config_cutover: pending\n",
            encoding="utf-8",
        )
        manifest = [ManifestEntry(workspace_root=str(ws))]
        items, gaps, state = build_rollup(manifest, {}, datetime.now(timezone.utc), staleness_threshold_days=14)
        assert len(items) == 1
        assert items[0].squad == "UNKNOWN"
        assert any("SQUAD_MAP.md" in g.reason for g in gaps)

    def test_every_service_across_workspaces_is_included(self, tmp_path):
        ws1 = tmp_path / "ws1"
        ws1.mkdir()
        (ws1 / "MIGRATION_STATUS.yaml").write_text(
            "schema_version: 1\nservices:\n  - name: svc-a\n    path: svc-a\n"
            "    tier_focus: P0\n    scan_gate: pass\n    shadow_compare: pass\n    config_cutover: done\n",
            encoding="utf-8",
        )
        ws2 = tmp_path / "ws2"
        ws2.mkdir()
        (ws2 / "MIGRATION_STATUS.yaml").write_text(
            "schema_version: 1\nservices:\n  - name: svc-b\n    path: svc-b\n"
            "    tier_focus: P1\n    scan_gate: fail\n    shadow_compare: pending\n    config_cutover: pending\n",
            encoding="utf-8",
        )
        manifest = [ManifestEntry(workspace_root=str(ws1)), ManifestEntry(workspace_root=str(ws2))]
        items, gaps, state = build_rollup(manifest, {}, datetime.now(timezone.utc), staleness_threshold_days=14)
        names = {i.service for i in items}
        assert names == {"svc-a", "svc-b"}
        statuses = {i.service: i.status for i in items}
        assert statuses["svc-a"] == "done"
        assert statuses["svc-b"] == "blocked"

    def test_malformed_yaml_is_a_gap_not_a_crash_for_other_workspaces(self, tmp_path):
        broken = tmp_path / "broken"
        broken.mkdir()
        (broken / "MIGRATION_STATUS.yaml").write_text("services: [unterminated", encoding="utf-8")
        ok = tmp_path / "ok"
        ok.mkdir()
        (ok / "MIGRATION_STATUS.yaml").write_text(
            "schema_version: 1\nservices:\n  - name: svc-a\n    path: svc-a\n"
            "    tier_focus: P0\n    scan_gate: pass\n    shadow_compare: pass\n    config_cutover: done\n",
            encoding="utf-8",
        )
        manifest = [ManifestEntry(workspace_root=str(broken)), ManifestEntry(workspace_root=str(ok))]
        items, gaps, state = build_rollup(manifest, {}, datetime.now(timezone.utc), staleness_threshold_days=14)
        assert {i.service for i in items} == {"svc-a"}
        assert any("not valid YAML" in g.reason for g in gaps if g.workspace_root == str(broken))

    def test_unchanged_signature_past_threshold_is_stalled_not_in_progress(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text(
            "schema_version: 1\nservices:\n  - name: svc-a\n    path: svc-a\n"
            "    tier_focus: P0\n    scan_gate: pass\n    shadow_compare: pending\n    config_cutover: pending\n",
            encoding="utf-8",
        )
        now = datetime.now(timezone.utc)
        sig = gate_signature({"scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"})
        twenty_days_ago = (now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {f"{ws}::svc-a": {"gate_signature": sig, "first_observed_at": twenty_days_ago}}
        manifest = [ManifestEntry(workspace_root=str(ws))]
        items, gaps, new_state = build_rollup(manifest, state, now, staleness_threshold_days=14)
        assert items[0].status == "stalled"

    def test_done_service_never_flagged_stalled_regardless_of_staleness(self, tmp_path):
        # A finished migration's gate signature is expected to stay unchanged forever -- staleness
        # must only ever escalate a genuinely still-unsettled ("in_progress") service, never "done".
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text(
            "schema_version: 1\nservices:\n  - name: svc-a\n    path: svc-a\n"
            "    tier_focus: P0\n    scan_gate: pass\n    shadow_compare: pass\n    config_cutover: done\n",
            encoding="utf-8",
        )
        now = datetime.now(timezone.utc)
        sig = gate_signature({"scan_gate": "pass", "shadow_compare": "pass", "config_cutover": "done"})
        twenty_days_ago = (now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {f"{ws}::svc-a": {"gate_signature": sig, "first_observed_at": twenty_days_ago}}
        manifest = [ManifestEntry(workspace_root=str(ws))]
        items, gaps, new_state = build_rollup(manifest, state, now, staleness_threshold_days=14)
        assert items[0].status == "done"
        assert items[0].staleness_days == 20

    def test_blocked_outranks_stalled(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text(
            "schema_version: 1\nservices:\n  - name: svc-a\n    path: svc-a\n"
            "    tier_focus: P0\n    scan_gate: fail\n    shadow_compare: pending\n    config_cutover: pending\n",
            encoding="utf-8",
        )
        now = datetime.now(timezone.utc)
        sig = gate_signature({"scan_gate": "fail", "shadow_compare": "pending", "config_cutover": "pending"})
        twenty_days_ago = (now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {f"{ws}::svc-a": {"gate_signature": sig, "first_observed_at": twenty_days_ago}}
        manifest = [ManifestEntry(workspace_root=str(ws))]
        items, gaps, new_state = build_rollup(manifest, state, now, staleness_threshold_days=14)
        assert items[0].status == "blocked"


class TestParseMigrationStatus:
    def test_malformed_yaml_returns_gap_not_raises(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text("services: [unterminated", encoding="utf-8")
        services, gap = parse_migration_status(str(ws))
        assert services == []
        assert gap is not None
        assert "not valid YAML" in gap.reason

    def test_top_level_list_returns_gap_not_raises(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text("- foo\n- bar\n", encoding="utf-8")
        services, gap = parse_migration_status(str(ws))
        assert services == []
        assert gap is not None
        assert "must be a mapping" in gap.reason

    def test_non_list_services_returns_gap_not_raises(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text("services: not-a-list\n", encoding="utf-8")
        services, gap = parse_migration_status(str(ws))
        assert services == []
        assert gap is not None
        assert "must be a list" in gap.reason

    def test_non_dict_service_entries_are_skipped_not_a_crash(self, tmp_path):
        ws = tmp_path / "ws"
        ws.mkdir()
        (ws / "MIGRATION_STATUS.yaml").write_text(
            "services:\n  - name: svc-a\n    path: svc-a\n"
            "    tier_focus: P0\n    scan_gate: pass\n    shadow_compare: pass\n    config_cutover: done\n"
            "  - just-a-stray-string\n",
            encoding="utf-8",
        )
        services, gap = parse_migration_status(str(ws))
        assert gap is None
        assert len(services) == 1
        assert services[0]["name"] == "svc-a"


class TestLoadState:
    def test_corrupted_state_file_falls_back_to_empty(self, tmp_path):
        p = tmp_path / "state.json"
        p.write_text("{not valid json", encoding="utf-8")
        assert load_state(str(p)) == {}

    def test_missing_state_file_returns_empty(self, tmp_path):
        assert load_state(str(tmp_path / "nope.json")) == {}


class TestLoadManifest:
    def test_parses_valid_manifest(self, tmp_path):
        p = tmp_path / "manifest.json"
        p.write_text('[{"workspace_root": "/ws1"}, {"workspace_root": "/ws2", "squad_map_path": "/other.md"}]', encoding="utf-8")
        entries = load_manifest(str(p))
        assert [e.workspace_root for e in entries] == ["/ws1", "/ws2"]
        assert entries[1].squad_map_path == "/other.md"

    def test_malformed_json_raises_manifest_error_not_a_raw_traceback(self, tmp_path):
        p = tmp_path / "manifest.json"
        p.write_text("{not valid json", encoding="utf-8")
        with pytest.raises(ManifestError):
            load_manifest(str(p))

    def test_entry_missing_workspace_root_raises_manifest_error(self, tmp_path):
        p = tmp_path / "manifest.json"
        p.write_text('[{"squad_map_path": "/other.md"}]', encoding="utf-8")
        with pytest.raises(ManifestError):
            load_manifest(str(p))

    def test_non_array_top_level_raises_manifest_error(self, tmp_path):
        p = tmp_path / "manifest.json"
        p.write_text('{"workspace_root": "/ws1"}', encoding="utf-8")
        with pytest.raises(ManifestError):
            load_manifest(str(p))
