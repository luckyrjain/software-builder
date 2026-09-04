#!/usr/bin/env python3
"""Validate k8s decision graph YAML against INV-01–INV-14."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
# A source checkout resolves this repository's own scripts/yaml_safety.py; an installed package
# -- proved by its manifest -- may only ever load the copy vendored beside this script, never a
# path in the shared skills root that another tool could have written.
if not (_SCRIPT_DIR.parent / ".software-builder-manifest.json").is_file():
    _REPO_ROOT = _SCRIPT_DIR.parents[1]
    if (_REPO_ROOT / "skills.yaml").is_file() and str(_REPO_ROOT) not in sys.path:
        sys.path.append(str(_REPO_ROOT))

try:
    # This script parses YAML written by the target workspace rather than by this repository, so
    # it wants the shared loader's duplicate-key rejection and size/nesting caps: a duplicate key
    # in a workspace file silently last-key-wins under plain safe_load.
    from yaml_safety import load_unique_yaml_file
except ImportError:
    try:
        from scripts.yaml_safety import load_unique_yaml_file
    except ImportError:  # pragma: no cover - bare environment; falls back to plain safe_load
        load_unique_yaml_file = None  # type: ignore[assignment]


def _parse_yaml_file(path: Path) -> Any:
    """Parse `path`, preferring the hardened loader when it is available."""
    if load_unique_yaml_file is not None:
        return load_unique_yaml_file(path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


CUT_REC_IDS = frozenset({"REC_CPU_REDUCE", "REC_REPLICA_REDUCE", "REC_MEMORY_REDUCE"})
ACTIONABLE_SUFFIXES = ("_REDUCE", "_INCREASE", "_ADJUST")
ASSESSMENT_WEIGHTS = (
    ("evidence_completeness", 0.35),
    ("evidence_quality", 0.35),
    ("contradiction_resolution", 0.15),
    ("telemetry_availability", 0.15),
)
REC_WEIGHTS = (
    ("support_completeness", 0.40),
    ("support_quality", 0.30),
    ("contradiction_resolution", 0.15),
    ("telemetry_availability", 0.15),
)


def _load_graph(path: Path) -> Any:
    if yaml is None:
        raise RuntimeError("PyYAML required: python3 -m pip install pyyaml")
    return _parse_yaml_file(path)


def _round1(value: float) -> float:
    return round(value + 1e-9, 1)


def _weighted(factors: dict[str, Any], weights: tuple[tuple[str, float], ...]) -> float:
    total = 0.0
    for key, weight in weights:
        total += weight * float(factors.get(key, 0))
    return _round1(total)


def _node_ids(graph: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for key in ("observations", "evidence", "decisions", "recommendations", "assumptions"):
        for item in graph.get(key) or []:
            if isinstance(item, dict) and "id" in item:
                ids.add(str(item["id"]))
    return ids


def _is_actionable_rec(rec_id: str) -> bool:
    if rec_id == "REC_MANIFEST_RECONCILE":
        return True
    return any(rec_id.endswith(suffix) for suffix in ACTIONABLE_SUFFIXES)


def validate_invariants(graph: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    if not isinstance(graph, dict):
        return ["root must be a mapping"]

    version = graph.get("schema_version")
    if version != 3:
        errors.append(f"schema_version must be 3 (got {version!r})")

    observations = graph.get("observations") or []
    evidence = graph.get("evidence") or []
    decisions = graph.get("decisions") or []
    recommendations = graph.get("recommendations") or []
    contradictions = graph.get("contradictions") or []
    all_ids = _node_ids(graph)

    obs_ids = {o["id"] for o in observations if isinstance(o, dict) and "id" in o}
    evid_by_obs = {}
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        obs_id = ev.get("observation_id")
        if obs_id:
            evid_by_obs.setdefault(obs_id, []).append(ev)

    # INV-01
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        rec_id = rec.get("id", "?")
        depends = (rec.get("depends_on") or {}).get("decisions") or []
        if not depends:
            errors.append(f"INV-01: {rec_id} missing depends_on.decisions")

    # INV-02
    for dec in decisions:
        if not isinstance(dec, dict):
            continue
        dec_id = dec.get("id", "?")
        supports = dec.get("supports") or []
        if not supports:
            errors.append(f"INV-02: {dec_id} has empty supports")

    # INV-03
    for obs_id in obs_ids:
        matches = evid_by_obs.get(obs_id, [])
        if len(matches) != 1:
            errors.append(
                f"INV-03: {obs_id} has {len(matches)} EVID_* rows (expected exactly 1)"
            )

    # INV-04
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        ev_id = ev.get("id", "?")
        quality = ev.get("quality")
        source = ev.get("source")
        if quality != "missing" and not source:
            errors.append(f"INV-04: {ev_id} missing source (quality={quality!r})")

    # INV-05
    for section, label in (
        (decisions, "decisions"),
        (recommendations, "recommendations"),
        (evidence, "evidence"),
    ):
        for item in section:
            if isinstance(item, dict) and "value" in item:
                errors.append(f"INV-05: {label} entry {item.get('id', '?')} has forbidden value field")

    # INV-06
    prefix_rules = (
        ("observations", "OBS_"),
        ("evidence", "EVID_"),
        ("decisions", "DEC_"),
        ("recommendations", "REC_"),
        ("assumptions", "ASSUME_"),
    )
    for key, prefix in prefix_rules:
        for item in graph.get(key) or []:
            if isinstance(item, dict) and "id" in item:
                node_id = str(item["id"])
                if not node_id.startswith(prefix):
                    errors.append(f"INV-06: {node_id} in {key} must start with {prefix}")

    # INV-07
    assessment = graph.get("assessment") or {}
    conf = assessment.get("assessment_confidence") or {}
    factors = conf.get("factors") or {}
    if factors:
        expected = _weighted(factors, ASSESSMENT_WEIGHTS)
        actual = conf.get("value")
        if actual is not None and abs(float(actual) - expected) > 0.05:
            errors.append(
                f"INV-07: assessment_confidence {actual} != weighted sum {expected}"
            )

    # INV-08, INV-09, INV-11, INV-12
    blocked_dec = {
        d["id"]
        for d in decisions
        if isinstance(d, dict) and d.get("status") == "BLOCKED"
    }
    unresolved = any(
        isinstance(c, dict) and c.get("status") not in (None, "Resolved")
        for c in contradictions
    )

    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        rec_id = rec.get("id", "?")
        status = rec.get("status")
        depends_dec = set((rec.get("depends_on") or {}).get("decisions") or [])

        if status == "READY" and depends_dec & blocked_dec:
            errors.append(f"INV-08: {rec_id} READY but depends on BLOCKED decision")

        if (
            unresolved
            and status == "READY"
            and rec_id in CUT_REC_IDS
        ):
            errors.append(f"INV-09: {rec_id} READY with unresolved contradictions")

        rconf = rec.get("recommendation_confidence") or {}
        rfactors = rconf.get("factors") or {}
        if rfactors and rconf.get("value") is not None:
            expected = _weighted(rfactors, REC_WEIGHTS)
            actual = float(rconf["value"])
            # Allow downward caps (DEC BLOCKED, telemetry, missing OBS)
            if actual < expected - 0.11:
                continue
            if abs(actual - expected) > 0.11:
                errors.append(
                    f"INV-11: {rec_id} recommendation_confidence {actual} "
                    f"!= factors sum {expected} (±0.11 after caps)"
                )

        if status == "READY" and _is_actionable_rec(rec_id):
            pointer = rec.get("delivery_pointer") or {}
            if not pointer.get("path"):
                errors.append(f"INV-12: {rec_id} READY actionable rec missing delivery_pointer.path")
            if pointer.get("verified") is not True:
                errors.append(
                    f"INV-12: {rec_id} READY actionable rec requires "
                    "delivery_pointer.verified: true"
                )

    # INV-10
    ref_fields = ("supports", "blocking", "missing")
    for dec in decisions:
        if not isinstance(dec, dict):
            continue
        for field in ref_fields:
            for ref in dec.get(field) or []:
                if ref not in all_ids and not str(ref).startswith("OBS_"):
                    errors.append(f"INV-10: {dec.get('id')} references unknown {ref}")
                elif ref not in all_ids:
                    errors.append(f"INV-10: {dec.get('id')} references unknown {ref}")

    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        depends = rec.get("depends_on") or {}
        for ref in depends.get("decisions") or []:
            if ref not in all_ids:
                errors.append(f"INV-10: {rec.get('id')} depends_on unknown decision {ref}")
        for ref in depends.get("observations") or []:
            if ref not in all_ids:
                errors.append(f"INV-10: {rec.get('id')} depends_on unknown observation {ref}")
        for ref in depends.get("assumptions") or []:
            ref_str = str(ref)
            if ref_str.startswith("ASSUME_"):
                continue  # INV-13 owns ASSUME_* membership in assumptions[]
            if ref not in all_ids:
                errors.append(f"INV-10: {rec.get('id')} depends_on unknown assumption {ref}")

    # INV-13
    assumption_ids = {
        str(a["id"])
        for a in (graph.get("assumptions") or [])
        if isinstance(a, dict) and "id" in a
    }
    for rec in recommendations:
        if not isinstance(rec, dict):
            continue
        rec_id = rec.get("id", "?")
        for assume_id in (rec.get("depends_on") or {}).get("assumptions") or []:
            assume_str = str(assume_id)
            if assume_str.startswith("ASSUME_") and assume_str not in assumption_ids:
                errors.append(
                    f"INV-13: {rec_id} depends_on assumption {assume_str} "
                    f"not in assumptions[]"
                )

    # INV-14
    metadata = graph.get("metadata") or {}
    source_profile = metadata.get("source_profile")
    if not isinstance(source_profile, dict):
        errors.append("INV-14: metadata.source_profile must be a mapping")
    else:
        sources = source_profile.get("sources")
        routes = source_profile.get("routes")
        valid_statuses = {"connected", "absent", "unreachable", "unauthorized"}
        required_routes = (
            "live_state",
            "current_metrics",
            "historical_metrics",
            "incidents_monitors",
            "manifest_config",
            "cost",
        )
        allowed_routes = {
            "live_state": {"kubernetes_mcp", "unavailable"},
            "current_metrics": {"kubernetes_mcp", "datadog", "unavailable"},
            "historical_metrics": {"kubernetes_mcp", "datadog", "unavailable"},
            "incidents_monitors": {"kubernetes_mcp", "datadog", "unavailable"},
            "manifest_config": {
                "kubernetes_mcp",
                "git",
                "user_provided",
                "unavailable",
            },
            "cost": {"datadog", "unavailable"},
        }
        if not isinstance(sources, dict):
            errors.append("INV-14: metadata.source_profile.sources must be a mapping")
        else:
            for source_name in ("kubernetes_mcp", "datadog"):
                source = sources.get(source_name)
                if not isinstance(source, dict):
                    errors.append(f"INV-14: source_profile.sources.{source_name} missing")
                    continue
                if source.get("status") not in valid_statuses:
                    errors.append(
                        f"INV-14: source_profile.sources.{source_name}.status must be one of "
                        f"{sorted(valid_statuses)}"
                    )
                if not isinstance(source.get("capabilities"), list):
                    errors.append(
                        f"INV-14: source_profile.sources.{source_name}.capabilities must be a list"
                    )
                if not isinstance(source.get("failures"), list):
                    errors.append(
                        f"INV-14: source_profile.sources.{source_name}.failures must be a list"
                    )
        if not isinstance(routes, dict):
            errors.append("INV-14: metadata.source_profile.routes must be a mapping")
        else:
            for capability in required_routes:
                if not routes.get(capability):
                    errors.append(f"INV-14: source_profile.routes.{capability} missing")

            for capability in required_routes:
                route = routes.get(capability)
                if route is not None and route not in allowed_routes[capability]:
                    errors.append(
                        f"INV-14: source_profile.routes.{capability} has invalid route {route}"
                    )
                    continue
                if route in {None, "unavailable", "git", "user_provided"}:
                    continue
                if not isinstance(sources, dict) or route not in sources:
                    errors.append(
                        f"INV-14: source_profile.routes.{capability} references unknown source {route}"
                    )
                    continue
                source = sources.get(route)
                if not isinstance(source, dict):
                    continue
                if source.get("status") != "connected":
                    errors.append(
                        f"INV-14: source_profile.routes.{capability} selects non-connected source {route}"
                    )
                capabilities = source.get("capabilities")
                if isinstance(capabilities, list) and capability not in capabilities:
                    errors.append(
                        f"INV-14: source_profile.routes.{capability} selects {route} without "
                        f"the {capability} capability"
                    )

    return errors


def main(argv: list[str] | None = None) -> int:
    paths = (argv if argv is not None else sys.argv[1:]) or [
        "k8s-overprovisioning-datadog/reference/decision-graph.example.yaml",
    ]
    exit_code = 0
    for path_str in paths:
        path = Path(path_str)
        try:
            graph = _load_graph(path)
        except (OSError, RuntimeError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            exit_code = 1
            continue
        except yaml.YAMLError as exc:  # type: ignore[union-attr]
            print(f"{path}: YAML parse error: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        errors = validate_invariants(graph)
        if errors:
            exit_code = 1
            print(f"{path}: {len(errors)} invariant violation(s):", file=sys.stderr)
            for err in errors:
                print(f"  - {err}", file=sys.stderr)
        else:
            print(f"{path}: ok (INV-01–INV-14)")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
