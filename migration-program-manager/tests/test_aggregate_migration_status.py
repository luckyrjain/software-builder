"""Scripted eval for migration-program-manager's aggregator."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from aggregate_migration_status import (  # noqa: E402
    build_rollup,
    compute_staleness,
    derive_status,
    gate_signature,
    join_squad,
    parse_squad_map,
    ManifestEntry,
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


class TestDeriveStatus:
    def test_blocked_on_any_fail(self):
        assert derive_status({"scan_gate": "fail", "shadow_compare": "pending", "config_cutover": "pending"}) == "blocked"

    def test_done_when_all_pass(self):
        assert derive_status({"scan_gate": "pass", "shadow_compare": "pass", "config_cutover": "done"}) == "done"

    def test_in_progress_otherwise(self):
        assert derive_status({"scan_gate": "pass", "shadow_compare": "pending", "config_cutover": "pending"}) == "in_progress"


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


class TestBuildRollup:
    def test_missing_migration_status_is_a_gap_not_a_crash(self, tmp_path):
        ws = tmp_path / "empty-workspace"
        ws.mkdir()
        manifest = [ManifestEntry(workspace_root=str(ws))]
        items, gaps, state = build_rollup(manifest, {}, datetime.now(timezone.utc))
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
        items, gaps, state = build_rollup(manifest, {}, datetime.now(timezone.utc))
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
        items, gaps, state = build_rollup(manifest, {}, datetime.now(timezone.utc))
        names = {i.service for i in items}
        assert names == {"svc-a", "svc-b"}
        statuses = {i.service: i.status for i in items}
        assert statuses["svc-a"] == "done"
        assert statuses["svc-b"] == "blocked"
