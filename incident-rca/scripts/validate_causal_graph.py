#!/usr/bin/env python3
"""Validate incident-rca causal graph YAML (schema_version 1) against an evidence bundle.

Machine checks (CG-01..CG-09) for the prose rules in reference/evidence-quality.md:
acyclicity, evidence-backed edges, hypothesis score arithmetic, confidence caps,
observability-source count, and the no-best-guess-primary rule.
Schema: reference/causal-graph-schema.md.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

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


NODE_KINDS = ("event", "trigger", "root_cause", "contributing", "systemic")
BAND_ORDER = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
EVIDENCE_LIST_FIELDS = (
    "error_signals",
    "deploy_events",
    "jira_issues",
    "infra_signals",
    "known_issue_matches",
    "evidence_links",
    "query_signals",
    "recurrence_history",
)
EVIDENCE_REF_RE = re.compile(r"^([a-z_]+)\[(\d+)\]$")

# Observability platforms (per reference/causal-graph-schema.md's `observability_sources_responded`
# and reference/evidence-schema.md's source conventions). GitLab/Jenkins/Jira are change-management
# sources, not observability, and never count here.
OBSERVABILITY_SOURCES = {
    "datadog",
    "kubesense",
    "kubesense-mcp",
    "kubesense-spl",
    "prometheus",
    "loki",
}
OBSERVABILITY_EVIDENCE_FIELDS = ("error_signals", "infra_signals")

REQUIRED_TOP_LEVEL = (
    "schema_version",
    "service",
    "window",
    "trigger_status",
    "observability_sources_responded",
    "nodes",
    "edges",
    "hypotheses",
    "conclusion",
)

HYPOTHESIS_REQUIRED = (
    "id",
    "type",
    "base",
    "quality_bonus",
    "source_bonus",
    "counter_penalty",
    "gap_penalty",
    "adjusted",
    "display_score",
    "band",
    "unresolved_contradictions",
    "supporting_quality",
    "ruled_out",
)


def _score_band(display_score: int) -> str:
    if display_score >= 75:
        return "HIGH"
    if display_score >= 50:
        return "MEDIUM"
    if display_score >= 25:
        return "LOW"
    return "UNKNOWN"


def _display_score(adjusted: float, total: float) -> int:
    if total <= 0:
        return 0
    value = adjusted / total * 100
    return max(0, min(100, int(value + 0.5)))


def _check_structure(graph: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(graph, dict):
        return ["root must be a mapping"]
    for key in REQUIRED_TOP_LEVEL:
        if key not in graph:
            errors.append(f"missing required field: {key}")
    if graph.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if graph.get("trigger_status") not in ("identified", "unknown"):
        errors.append("trigger_status must be 'identified' or 'unknown'")
    if "observability_sources_responded" in graph:
        sources = graph.get("observability_sources_responded")
        if isinstance(sources, bool) or not isinstance(sources, int) or sources < 0:
            errors.append(
                "observability_sources_responded must be a non-negative integer"
            )
    for key in ("nodes", "edges", "hypotheses"):
        if key in graph and not isinstance(graph.get(key), list):
            errors.append(f"{key} must be a list")
    if "conclusion" in graph and not isinstance(graph.get("conclusion"), dict):
        errors.append("conclusion must be a mapping")
    for index, hyp in enumerate(graph.get("hypotheses") or []):
        if not isinstance(hyp, dict):
            errors.append(f"hypotheses[{index}] must be a mapping")
            continue
        for key in HYPOTHESIS_REQUIRED:
            if key not in hyp:
                errors.append(f"hypotheses[{index}] missing required field: {key}")
    return errors


def _check_nodes_edges(graph: dict) -> list[str]:
    errors: list[str] = []
    nodes = graph.get("nodes") or []
    node_ids: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"CG-02: nodes[{index}] must be a mapping")
            continue
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            errors.append(f"CG-02: nodes[{index}] missing id")
            continue
        if node_id in node_ids:
            errors.append(f"CG-02: duplicate node id: {node_id}")
        node_ids.append(node_id)
        if node.get("kind") not in NODE_KINDS:
            errors.append(f"CG-02: node {node_id} has invalid kind: {node.get('kind')!r}")
    known = set(node_ids)
    for index, edge in enumerate(graph.get("edges") or []):
        if not isinstance(edge, dict):
            errors.append(f"CG-02: edges[{index}] must be a mapping")
            continue
        for endpoint in ("from", "to"):
            if edge.get(endpoint) not in known:
                errors.append(
                    f"CG-02: edges[{index}].{endpoint} references unknown node: {edge.get(endpoint)!r}"
                )
    return errors


def _check_acyclic(graph: dict) -> list[str]:
    adjacency: dict[str, list[str]] = {}
    for edge in graph.get("edges") or []:
        if isinstance(edge, dict):
            adjacency.setdefault(str(edge.get("from")), []).append(str(edge.get("to")))
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    def visit(node: str) -> bool:
        color[node] = GRAY
        for nxt in adjacency.get(node, []):
            state = color.get(nxt, WHITE)
            if state == GRAY:
                return True
            if state == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    for start in list(adjacency):
        if color.get(start, WHITE) == WHITE and visit(start):
            return ["CG-01: causal graph contains a cycle — feedback loops belong in prose"]
    return []


def _check_edge_evidence(graph: dict, evidence: Any) -> list[str]:
    errors: list[str] = []
    evidence = evidence if isinstance(evidence, dict) else {}
    for index, edge in enumerate(graph.get("edges") or []):
        if not isinstance(edge, dict):
            continue
        refs = edge.get("evidence")
        if not isinstance(refs, list) or not refs:
            errors.append(f"CG-03: edges[{index}] must cite at least one evidence ref")
            continue
        for ref in refs:
            match = EVIDENCE_REF_RE.match(ref) if isinstance(ref, str) else None
            if not match:
                errors.append(f"CG-03: edges[{index}] malformed evidence ref: {ref!r}")
                continue
            field, pos = match.group(1), int(match.group(2))
            if field not in EVIDENCE_LIST_FIELDS:
                errors.append(f"CG-03: edges[{index}] unknown evidence field: {field}")
                continue
            entries = evidence.get(field)
            if not isinstance(entries, list) or pos >= len(entries):
                errors.append(
                    f"CG-03: edges[{index}] evidence ref does not resolve: {field}[{pos}]"
                )
    return errors


def _check_observability_sources(graph: dict, evidence: Any) -> list[str]:
    errors: list[str] = []
    declared = graph.get("observability_sources_responded")
    if not isinstance(declared, int):
        return errors  # already flagged by _check_structure
    evidence = evidence if isinstance(evidence, dict) else {}
    actual_sources: set[str] = set()
    for field in OBSERVABILITY_EVIDENCE_FIELDS:
        for entry in evidence.get(field) or []:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source")
            if isinstance(source, str) and source.lower() in OBSERVABILITY_SOURCES:
                actual_sources.add(source.lower())
    if declared != len(actual_sources):
        errors.append(
            "CG-09: observability_sources_responded "
            f"{declared} != distinct observability sources found in evidence "
            f"({len(actual_sources)}: {sorted(actual_sources) or 'none'})"
        )
    return errors


def _check_hypotheses(graph: dict) -> list[str]:
    errors: list[str] = []
    hypotheses = [h for h in (graph.get("hypotheses") or []) if isinstance(h, dict)]
    numeric_ok: list[dict] = []
    contradictions: dict[Any, int] = {}
    for hyp in hypotheses:
        hid = hyp.get("id", "?")
        raw_contradictions = hyp.get("unresolved_contradictions")
        if isinstance(raw_contradictions, int) and not isinstance(raw_contradictions, bool):
            contradictions[hid] = raw_contradictions
        elif raw_contradictions is not None:
            errors.append(
                f"CG-06: hypothesis {hid} unresolved_contradictions must be an integer"
            )
        try:
            base = float(hyp["base"])
            quality_bonus = float(hyp["quality_bonus"])
            source_bonus = float(hyp["source_bonus"])
            counter_penalty = float(hyp["counter_penalty"])
            gap_penalty = float(hyp["gap_penalty"])
            adjusted = float(hyp["adjusted"])
        except (KeyError, TypeError, ValueError):
            errors.append(f"CG-04: hypothesis {hid} has missing or non-numeric score fields")
            continue
        if quality_bonus > 15:
            errors.append(f"CG-04: hypothesis {hid} quality_bonus {quality_bonus} exceeds cap 15")
        if counter_penalty < 0:
            errors.append(
                f"CG-04: hypothesis {hid} counter_penalty {counter_penalty} must be >= 0"
            )
        elif hid in contradictions and counter_penalty != 10 * contradictions[hid]:
            errors.append(
                f"CG-04: hypothesis {hid} counter_penalty {counter_penalty} != "
                f"10 * unresolved_contradictions ({contradictions[hid]})"
            )
        if gap_penalty not in (0, 15):
            errors.append(f"CG-04: hypothesis {hid} gap_penalty {gap_penalty} must be 0 or 15")
        if source_bonus not in (0, 10):
            errors.append(f"CG-04: hypothesis {hid} source_bonus {source_bonus} must be 0 or 10")
        expected = max(
            0.0, base + quality_bonus + source_bonus - counter_penalty - gap_penalty
        )
        if abs(adjusted - expected) > 1e-6:
            errors.append(
                f"CG-04: hypothesis {hid} adjusted {adjusted} != expected {expected}"
            )
        numeric_ok.append(hyp)

    total = sum(float(h["adjusted"]) for h in numeric_ok)
    max_adjusted = max((float(h["adjusted"]) for h in numeric_ok), default=0.0)

    sources = graph.get("observability_sources_responded")
    trigger_unknown = graph.get("trigger_status") != "identified"

    for hyp in numeric_ok:
        hid = hyp.get("id", "?")
        expected_display = _display_score(float(hyp["adjusted"]), total)
        if hyp.get("display_score") != expected_display:
            errors.append(
                f"CG-05: hypothesis {hid} display_score {hyp.get('display_score')} "
                f"!= expected {expected_display}"
            )
        band = hyp.get("band")
        if band not in BAND_ORDER:
            errors.append(f"CG-06: hypothesis {hid} invalid band: {band!r}")
            continue
        caps: list[tuple[str, str]] = []
        if isinstance(sources, int) and sources < 2:
            caps.append(("MEDIUM", "single observability source"))
        if contradictions.get(hid, 0) > 0:
            caps.append(("MEDIUM", "unresolved contradictions"))
        if trigger_unknown:
            caps.append(("MEDIUM", "trigger unknown"))
        quality = hyp.get("supporting_quality") or []
        if quality and all(q == "Assumed" for q in quality):
            caps.append(("LOW", "Assumed-only support"))
        caps.append((_score_band(expected_display), "score band"))
        for cap_band, reason in caps:
            if BAND_ORDER[band] > BAND_ORDER[cap_band]:
                errors.append(
                    f"CG-06: hypothesis {hid} band {band} exceeds {cap_band} cap ({reason})"
                )
        expected_ruled_out = max_adjusted > 0 and float(hyp["adjusted"]) < 0.5 * max_adjusted
        if bool(hyp.get("ruled_out")) != expected_ruled_out:
            errors.append(
                f"CG-08: hypothesis {hid} ruled_out must be {expected_ruled_out} "
                f"(adjusted {hyp['adjusted']} vs 0.5 × {max_adjusted})"
            )

    conclusion = graph.get("conclusion")
    if isinstance(conclusion, dict):
        primary = conclusion.get("primary")
        high_ids = [h.get("id") for h in numeric_ok if h.get("band") == "HIGH"]
        if primary == "none" or primary is None:
            if high_ids:
                errors.append(
                    f"CG-07: conclusion.primary is none but HIGH hypotheses exist: {high_ids}"
                )
        elif primary not in high_ids:
            errors.append(
                f"CG-07: conclusion.primary {primary!r} must name a HIGH-band hypothesis "
                "(no best-guess primary when all <= MEDIUM after caps)"
            )
    return errors


def validate_causal_graph(graph: Any, evidence: Any) -> list[str]:
    errors = _check_structure(graph)
    if not isinstance(graph, dict) or any("must be a list" in e for e in errors):
        return errors
    errors.extend(_check_nodes_edges(graph))
    errors.extend(_check_acyclic(graph))
    errors.extend(_check_edge_evidence(graph, evidence))
    errors.extend(_check_observability_sources(graph, evidence))
    errors.extend(_check_hypotheses(graph))
    return errors


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if yaml is None:
        print("PyYAML is required — pip install PyYAML", file=sys.stderr)
        return 2
    if len(args) != 2:
        print(
            "usage: validate_causal_graph.py <causal-graph.yaml> <evidence.json>",
            file=sys.stderr,
        )
        return 2
    graph_path, evidence_path = Path(args[0]), Path(args[1])
    try:
        graph = _parse_yaml_file(graph_path)
    except (OSError, yaml.YAMLError) as exc:
        print(f"{graph_path}: {exc}", file=sys.stderr)
        return 1
    try:
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{evidence_path}: {exc}", file=sys.stderr)
        return 1
    errors = validate_causal_graph(graph, evidence)
    if errors:
        print(f"{graph_path}: validation failed", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print(f"{graph_path}: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
