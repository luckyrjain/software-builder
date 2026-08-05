#!/usr/bin/env python3
"""Aggregate MIGRATION_STATUS.yaml across many workspaces, joined to SQUAD_MAP.md.

Reads-only: never invokes mysql-to-postgres-sql or squad-map, only their existing
output files. Computes org_rollup_item entries (org-rollup-schema.md, pg_migration_gate
adapter) and persists per-service gate-signature state across runs so staleness
("gate unchanged for N days") can be computed even though MIGRATION_STATUS.yaml itself
has no per-gate timestamp.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised when PyYAML missing
    yaml = None  # type: ignore


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


@dataclass
class ManifestEntry:
    workspace_root: str
    squad_map_path: str | None = None

    def resolved_squad_map_path(self) -> Path:
        if self.squad_map_path:
            return Path(self.squad_map_path)
        return Path(self.workspace_root) / "SQUAD_MAP.md"


@dataclass
class RollupItem:
    service: str
    squad: str
    squad_confidence: str
    source_skill: str
    metric_type: str
    status: str
    priority: str | None
    value: dict[str, Any]
    evidence_ref: str
    last_updated: str
    staleness_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "service": self.service,
            "squad": self.squad,
            "squad_confidence": self.squad_confidence,
            "source_skill": self.source_skill,
            "metric_type": self.metric_type,
            "status": self.status,
            "priority": self.priority,
            "value": self.value,
            "evidence_ref": self.evidence_ref,
            "last_updated": self.last_updated,
            "staleness_days": self.staleness_days,
        }


@dataclass
class Gap:
    workspace_root: str
    reason: str


def load_manifest(path: str) -> list[ManifestEntry]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [
        ManifestEntry(
            workspace_root=entry["workspace_root"],
            squad_map_path=entry.get("squad_map_path"),
        )
        for entry in raw
    ]


def parse_migration_status(workspace_root: str) -> tuple[list[dict[str, Any]], Gap | None]:
    """Return (services, gap). services is [] and gap is set when the file is missing/unparseable."""
    status_path = Path(workspace_root) / "MIGRATION_STATUS.yaml"
    if not status_path.exists():
        return [], Gap(workspace_root, "MIGRATION_STATUS.yaml not found — run mysql-to-postgres-sql first")
    if yaml is None:  # pragma: no cover - exercised only without PyYAML installed
        return [], Gap(workspace_root, "PyYAML not installed — cannot parse MIGRATION_STATUS.yaml")
    with open(status_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    services = data.get("services") or []
    return services, None


def parse_squad_map(squad_map_path: Path) -> list[dict[str, str]]:
    """Parse SQUAD_MAP.md's '## Repo -> squad' table only.

    Tolerates the Conflicts / Unmapped repos / Out of scope (archived) sections that
    follow it in the same file -- stops reading rows the moment a new '## ' heading
    is hit after the join table has started, and never treats a row from any other
    section as part of the main join.
    """
    if not squad_map_path.exists():
        return []
    lines = squad_map_path.read_text(encoding="utf-8").splitlines()

    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("## Repo") and "squad" in line.lower():
            header_idx = i
            break
    if header_idx is None:
        return []

    rows: list[dict[str, str]] = []
    columns: list[str] | None = None
    for line in lines[header_idx + 1 :]:
        stripped = line.strip()
        if stripped.startswith("## "):
            break  # next section — Conflicts / Unmapped / Out of scope
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if columns is None:
            columns = cells
            continue
        if set(cells) <= {""} or all(set(c) <= {"-", ":"} for c in cells):
            continue  # separator row (---|---|...)
        if len(cells) != len(columns):
            continue  # malformed row — skip rather than crash
        rows.append(dict(zip(columns, cells)))
    return rows


def join_squad(service_path: str, service_name: str, squad_rows: list[dict[str, str]]) -> tuple[str, str]:
    """Match a MIGRATION_STATUS.yaml service to a squad. Returns (squad, confidence)."""
    for candidate in (service_path, service_name):
        if not candidate:
            continue
        for row in squad_rows:
            if row.get("Repo", "").strip() == candidate.strip():
                squad = row.get("GitLab squad") or row.get("Datadog team") or "UNKNOWN"
                confidence = row.get("Confidence", "UNKNOWN")
                return squad or "UNKNOWN", confidence or "UNKNOWN"
    return "UNKNOWN", "UNKNOWN"


def derive_status(svc: dict[str, Any]) -> str:
    gates = (svc.get("scan_gate"), svc.get("shadow_compare"), svc.get("config_cutover"))
    if "fail" in gates:
        return "blocked"
    if svc.get("scan_gate") == "pass" and svc.get("shadow_compare") == "pass" and svc.get("config_cutover") == "done":
        return "done"
    return "in_progress"


def gate_signature(svc: dict[str, Any]) -> str:
    return f"{svc.get('scan_gate')}|{svc.get('shadow_compare')}|{svc.get('config_cutover')}"


def load_state(state_path: str) -> dict[str, dict[str, str]]:
    p = Path(state_path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def save_state(state_path: str, state: dict[str, dict[str, str]]) -> None:
    Path(state_path).write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def compute_staleness(
    workspace_root: str,
    svc: dict[str, Any],
    state: dict[str, dict[str, str]],
    now: datetime,
) -> tuple[int, dict[str, str]]:
    """Returns (staleness_days, updated_state_entry). Mutates nothing -- caller persists."""
    key = f"{workspace_root}::{svc.get('name')}"
    sig = gate_signature(svc)
    prior = state.get(key)
    if prior is None or prior.get("gate_signature") != sig:
        entry = {"gate_signature": sig, "first_observed_at": now_iso()}
        return 0, entry
    first_observed = parse_iso(prior["first_observed_at"])
    staleness_days = (now - first_observed).days
    return staleness_days, prior


def build_rollup(
    manifest: list[ManifestEntry],
    state: dict[str, dict[str, str]],
    now: datetime,
) -> tuple[list[RollupItem], list[Gap], dict[str, dict[str, str]]]:
    items: list[RollupItem] = []
    gaps: list[Gap] = []
    new_state: dict[str, dict[str, str]] = {}

    for entry in manifest:
        services, gap = parse_migration_status(entry.workspace_root)
        if gap:
            gaps.append(gap)
            continue
        squad_map_path = entry.resolved_squad_map_path()
        squad_rows = parse_squad_map(squad_map_path)
        if not squad_rows:
            gaps.append(Gap(entry.workspace_root, f"No SQUAD_MAP.md at {squad_map_path} — run squad-map directly"))

        for svc in services:
            name = svc.get("name", "")
            path = svc.get("path", "")
            squad, confidence = join_squad(path, name, squad_rows)
            staleness_days, state_entry = compute_staleness(entry.workspace_root, svc, state, now)
            new_state[f"{entry.workspace_root}::{name}"] = state_entry

            items.append(
                RollupItem(
                    service=name,
                    squad=squad,
                    squad_confidence=confidence,
                    source_skill="mysql-to-postgres-sql",
                    metric_type="pg_migration_gate",
                    status=derive_status(svc),
                    priority=svc.get("tier_focus") if svc.get("tier_focus") != "dialect-only" else None,
                    value={
                        "scan_gate": svc.get("scan_gate"),
                        "shadow_compare": svc.get("shadow_compare"),
                        "config_cutover": svc.get("config_cutover"),
                        "mr_url": svc.get("mr_url", ""),
                    },
                    evidence_ref=str(Path(entry.workspace_root) / "MIGRATION_STATUS.yaml"),
                    last_updated=now_iso(),
                    staleness_days=staleness_days,
                )
            )
    return items, gaps, new_state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, help="Path to a JSON program_manifest file")
    parser.add_argument("--staleness-threshold-days", type=int, required=True)
    parser.add_argument("--state-path", required=True)
    parser.add_argument("--out-rollup", required=True, help="Where to write migration_program_rollup.json")
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    state = load_state(args.state_path)
    now = datetime.now(timezone.utc)

    items, gaps, new_state = build_rollup(manifest, state, now)
    save_state(args.state_path, new_state)

    Path(args.out_rollup).write_text(
        json.dumps([i.to_dict() for i in items], indent=2, sort_keys=True), encoding="utf-8"
    )

    for gap in gaps:
        print(f"gap: {gap.workspace_root}: {gap.reason}", file=sys.stderr)

    blocked = sum(1 for i in items if i.status == "blocked")
    stalled = sum(1 for i in items if i.staleness_days >= args.staleness_threshold_days)
    print(f"{len(items)} services, {blocked} blocked, {stalled} stalled, {len(gaps)} workspace gaps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
