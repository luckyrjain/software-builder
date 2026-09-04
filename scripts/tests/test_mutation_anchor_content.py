from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.evals.golden import load_golden_fixtures
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]


def test_mutation_anchor_patterns_exist_in_recorded_output_not_fixture_prose() -> None:
    raw = load_unique_yaml_file(ROOT / "scripts" / "registry" / "mutation_anchors.yaml")
    doc = require_mapping(raw, "mutation anchors")
    assert doc.get("schema_version") == 1
    anchors = require_mapping(doc.get("anchors"), "mutation anchors.anchors")
    golden = {
        f"{case.skill}/{case.case_id}": case
        for case in load_golden_fixtures(ROOT / "evals" / "golden")
    }

    for class_id, raw_anchor in anchors.items():
        anchor = require_mapping(raw_anchor, f"mutation anchors.{class_id}")
        case_ref = str(anchor.get("case_ref", ""))
        pattern = str(anchor.get("raw_pattern", ""))
        assert case_ref in golden, f"{class_id}: missing golden fixture {case_ref}"
        assert pattern, f"{class_id}: raw_pattern is required"
        recorded = json.dumps(golden[case_ref].recorded_output, sort_keys=True)
        assert re.search(pattern, recorded, flags=re.IGNORECASE | re.MULTILINE), (
            f"{class_id}: pattern {pattern!r} is not present in recorded_output for {case_ref}"
        )
