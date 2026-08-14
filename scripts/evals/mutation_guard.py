"""Executable Batch 3 guardrail mutation checks.

Each adversarial class declares a representative golden fixture, the untrusted
input field that receives the configured mutation payload, and the protected
outcome that represents attacker success. The check proves two things:

1. appending the configured attack payload to untrusted input keeps the golden
   safety assertions green; and
2. flipping the protected outcome to the unsafe value makes those same
   assertions fail.

This is deterministic fixture mutation testing. It does not replace live/model
evals; it proves the regression assertions are wired to detect guardrail loss.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from scripts.evals.golden import GoldenCase, run_golden_case
from scripts.evals.types import EvalResult
from scripts.yaml_safety import load_unique_yaml_file, require_mapping


def _resolve_path(data: dict[str, Any], dotted_path: str) -> Any:
    current: Any = data
    for segment in dotted_path.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(dotted_path)
        current = current[segment]
    return current


def _set_path(data: dict[str, Any], dotted_path: str, value: Any) -> None:
    segments = dotted_path.split(".")
    if not segments or any(not segment for segment in segments):
        raise KeyError(dotted_path)
    current: Any = data
    for segment in segments[:-1]:
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(dotted_path)
        current = current[segment]
    leaf = segments[-1]
    if not isinstance(current, dict) or leaf not in current:
        raise KeyError(dotted_path)
    current[leaf] = value


def run_guardrail_mutation_checks(
    root: Path,
    golden_cases: list[GoldenCase],
) -> list[EvalResult]:
    eval_contract = require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "eval_contracts.yaml"),
        "eval contracts",
    )
    adversarial = require_mapping(eval_contract.get("adversarial_classes"), "adversarial_classes")
    anchor_doc = require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "mutation_anchors.yaml"),
        "mutation anchors",
    )
    anchors = require_mapping(anchor_doc.get("anchors"), "mutation anchors.anchors")
    golden_by_ref = {f"{case.skill}/{case.case_id}": case for case in golden_cases}

    output: list[EvalResult] = []
    for class_id in sorted(adversarial):
        messages: list[str] = []
        raw_class = require_mapping(adversarial[class_id], f"adversarial_classes.{class_id}")
        raw_anchor = anchors.get(class_id)
        if not isinstance(raw_anchor, dict):
            output.append(EvalResult("batch3-mutation", class_id, False, ["missing mutation anchor"]))
            continue
        anchor = require_mapping(raw_anchor, f"mutation anchors.{class_id}")

        mutation = raw_class.get("mutation")
        case_ref = anchor.get("case_ref")
        raw_pattern = anchor.get("raw_pattern")
        raw_path = anchor.get("raw_path")
        unsafe_path = anchor.get("unsafe_path")
        unsafe_value = anchor.get("unsafe_value")
        for name, value in {
            "mutation": mutation,
            "case_ref": case_ref,
            "raw_pattern": raw_pattern,
            "raw_path": raw_path,
            "unsafe_path": unsafe_path,
        }.items():
            if not isinstance(value, str) or not value:
                messages.append(f"{name} must be a non-empty string")
        if messages:
            output.append(EvalResult("batch3-mutation", class_id, False, messages))
            continue

        assert isinstance(mutation, str)
        assert isinstance(case_ref, str)
        assert isinstance(raw_pattern, str)
        assert isinstance(raw_path, str)
        assert isinstance(unsafe_path, str)
        fixture = golden_by_ref.get(case_ref)
        if fixture is None:
            output.append(EvalResult("batch3-mutation", class_id, False, [f"missing golden fixture {case_ref}"]))
            continue

        original = run_golden_case(fixture)
        if not original.passed:
            messages.append(f"baseline golden fixture is already failing: {case_ref}")

        try:
            recorded = json.dumps(fixture.recorded_output, sort_keys=True)
            if not re.search(raw_pattern, recorded, flags=re.IGNORECASE | re.MULTILINE):
                messages.append(f"raw pattern {raw_pattern!r} is absent from recorded_output")
        except re.error as exc:
            messages.append(f"invalid raw_pattern {raw_pattern!r}: {exc}")

        try:
            raw_value = _resolve_path(fixture.recorded_output, raw_path)
            if not isinstance(raw_value, str):
                messages.append(f"raw_path {raw_path!r} must resolve to a string")
            else:
                injected_output = copy.deepcopy(fixture.recorded_output)
                _set_path(injected_output, raw_path, f"{raw_value}\n{mutation}")
                injected = run_golden_case(replace(fixture, recorded_output=injected_output))
                if not injected.passed:
                    messages.append(
                        "configured mutation payload breaks the safe fixture instead of remaining inert: "
                        + "; ".join(injected.messages),
                    )
        except KeyError:
            messages.append(f"raw_path does not exist: {raw_path!r}")

        try:
            original_unsafe = _resolve_path(fixture.recorded_output, unsafe_path)
            if original_unsafe == unsafe_value:
                messages.append(f"unsafe_path {unsafe_path!r} is already at the unsafe value")
            else:
                compromised_output = copy.deepcopy(fixture.recorded_output)
                _set_path(compromised_output, unsafe_path, unsafe_value)
                compromised = run_golden_case(replace(fixture, recorded_output=compromised_output))
                if compromised.passed:
                    messages.append(
                        f"guardrail assertions did not detect unsafe outcome {unsafe_path}={unsafe_value!r}",
                    )
        except KeyError:
            messages.append(f"unsafe_path does not exist: {unsafe_path!r}")

        output.append(EvalResult("batch3-mutation", class_id, not messages, messages))
    return output
