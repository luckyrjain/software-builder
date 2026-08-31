"""Static referential-integrity lint for the eval cross-reference registries.

scripts/registry/eval_contracts.yaml and mutation_anchors.yaml reference golden
fixtures by "skill/case_id" string and, for mutation anchors, by dotted paths
into a specific fixture's recorded_output. Today those references are only
proven valid as a side effect of executing the full eval suite
(mutation_guard.py, batch3_contract.py, platform_contract.py) -- a typo'd
case_ref or a recorded_output shape change under an anchor's raw_path/
unsafe_path surfaces as a KeyError/failure message in a file the author never
touched, and only on a full `python3 -m scripts.evals` run.

This module checks the same references structurally -- existence, not
pass/fail -- without executing any assertion or fixture mutation, so it can
run standalone and fast, including from a --skill-filtered dev loop that
doesn't otherwise load these registries at all.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from scripts.evals.golden import GoldenCase, golden_case_index, load_golden_fixtures, resolve_path
from scripts.evals.transcript import load_transcript_fixtures
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]

_KNOWN_CONTRACT_GATES = ("routing_collisions", "adversarial_matrix")


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list) or not value:
        return None
    if not all(isinstance(item, str) and item for item in value):
        return None
    return value


def _check_case_refs(
    refs: list[str],
    *,
    location: str,
    known_refs: set[str],
) -> list[str]:
    errors = []
    for ref in refs:
        if ref not in known_refs:
            errors.append(f"{location}: case_ref {ref!r} does not resolve to a loaded fixture/transcript/golden case")
    return errors


def _fixture_case_refs(fixtures_dir: Path) -> tuple[set[str], list[str]]:
    """Scan Tier-1 fixtures (evals/fixtures/**/*.yaml) for their "skill/case_id" refs.

    Reimplements just the ref-extraction half of __main__.load_fixtures rather
    than importing it: __main__.py is the CLI entrypoint, and wiring this
    linter into a --skill-filtered eval run (a later step) would make that an
    import cycle. The two independently enforce "skill and case_id are
    required" the same way; if that check ever needs to change, this module's
    copy has to change with it, which is a one-line coupling worth accepting
    to avoid the cycle.
    """
    refs: set[str] = set()
    errors: list[str] = []
    if not fixtures_dir.is_dir():
        return refs, errors
    for path in sorted(fixtures_dir.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            raw = load_unique_yaml_file(path)
        except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
            errors.append(f"{path}: {exc}")
            continue
        if not isinstance(raw, dict):
            errors.append(f"{path}: fixture root must be a mapping")
            continue
        skill = str(raw.get("skill", ""))
        case_id = str(raw.get("case_id", ""))
        if not skill or not case_id:
            errors.append(f"{path}: skill and case_id are required")
            continue
        refs.add(f"{skill}/{case_id}")
    return refs, errors


def _global_template_refs(root: Path) -> tuple[set[str], list[str]]:
    """Every registered skill gets a synthetic "{skill}/global-happy" and
    "{skill}/global-adversarial" ref when evals/fixtures/_global.yaml defines
    those templates (see __main__.run_all) -- e.g. degraded_host_cases'
    backlog-runner/global-happy resolves only through this path, not through
    any file actually named for that skill.
    """
    refs: set[str] = set()
    errors: list[str] = []
    global_fixture = root / "evals" / "fixtures" / "_global.yaml"
    if not global_fixture.is_file():
        return refs, errors
    try:
        raw = load_unique_yaml_file(global_fixture)
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return refs, [f"{global_fixture}: {exc}"]
    if not isinstance(raw, dict):
        return refs, [f"{global_fixture}: must be a mapping"]
    try:
        registry = parse_registry(root / "skills.yaml")
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return refs, [f"{root / 'skills.yaml'}: {exc}"]
    for template_name in ("happy", "adversarial"):
        if isinstance(raw.get(template_name), dict):
            for skill_id in registry.skills:
                refs.add(f"{skill_id}/global-{template_name}")
    return refs, errors


def _known_case_refs(root: Path, golden_cases: list[GoldenCase]) -> tuple[set[str], list[str]]:
    """Union of every "skill/case_id" ref a case_refs list in eval_contracts.yaml
    can legally point at: Tier-1 fixtures, Tier-2 transcripts, Tier-3 golden
    fixtures, and the synthetic per-skill _global.yaml templates -- the same
    four sources __main__.run_all feeds into the eval result set case_refs
    are checked against at runtime.
    """
    refs: set[str] = {f"{case.skill}/{case.case_id}" for case in golden_cases}
    errors: list[str] = []

    fixture_refs, fixture_errors = _fixture_case_refs(root / "evals" / "fixtures")
    refs |= fixture_refs
    errors.extend(fixture_errors)

    try:
        transcript_cases = load_transcript_fixtures(root / "evals" / "transcripts")
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        errors.append(f"evals/transcripts: {exc}")
    else:
        refs |= {f"{case.skill}/{case.case_id}" for case in transcript_cases}

    global_refs, global_errors = _global_template_refs(root)
    refs |= global_refs
    errors.extend(global_errors)

    return refs, errors


def _lint_dimension_coverage(contract: dict[str, Any], known_refs: set[str]) -> list[str]:
    errors: list[str] = []
    coverage = contract.get("dimension_coverage")
    if not isinstance(coverage, dict):
        return [f"dimension_coverage: must be a mapping, got {type(coverage).__name__}"]
    for dimension, raw in sorted(coverage.items()):
        location = f"dimension_coverage.{dimension}"
        if not isinstance(raw, dict):
            errors.append(f"{location}: must be a mapping")
            continue
        case_refs = raw.get("case_refs")
        gate = raw.get("contract_gate")
        has_refs = case_refs is not None
        has_gate = gate is not None
        if has_refs == has_gate:
            errors.append(f"{location}: declare exactly one of case_refs or contract_gate")
        if has_refs:
            refs = _string_list(case_refs)
            if refs is None:
                errors.append(f"{location}.case_refs: must be a non-empty list of non-empty strings")
            else:
                errors.extend(_check_case_refs(refs, location=f"{location}.case_refs", known_refs=known_refs))
        if has_gate and gate not in _KNOWN_CONTRACT_GATES:
            errors.append(f"{location}.contract_gate: unknown gate {gate!r}, expected one of {_KNOWN_CONTRACT_GATES}")
    return errors


def _lint_behavior_scenarios(contract: dict[str, Any], known_refs: set[str]) -> list[str]:
    errors: list[str] = []
    scenarios = contract.get("behavior_scenarios")
    if not isinstance(scenarios, dict):
        return [f"behavior_scenarios: must be a mapping, got {type(scenarios).__name__}"]
    for scenario_id, raw in sorted(scenarios.items()):
        location = f"behavior_scenarios.{scenario_id}"
        if not isinstance(raw, dict):
            errors.append(f"{location}: must be a mapping")
            continue
        case_refs = raw.get("case_refs")
        gate = raw.get("contract_gate")
        has_refs = case_refs is not None
        has_gate = gate is not None
        if has_refs == has_gate:
            errors.append(f"{location}: declare exactly one of case_refs or contract_gate")
        if has_refs:
            refs = _string_list(case_refs)
            if refs is None:
                errors.append(f"{location}.case_refs: must be a non-empty list of non-empty strings")
            else:
                errors.extend(_check_case_refs(refs, location=f"{location}.case_refs", known_refs=known_refs))
        if has_gate and gate not in _KNOWN_CONTRACT_GATES:
            errors.append(f"{location}.contract_gate: unknown gate {gate!r}, expected one of {_KNOWN_CONTRACT_GATES}")
    return errors


def _lint_referenced_matrix(
    contract: dict[str, Any],
    *,
    key: str,
    known_refs: set[str],
    require_mutation: bool,
) -> list[str]:
    errors: list[str] = []
    matrix = contract.get(key)
    if not isinstance(matrix, dict):
        return [f"{key}: must be a mapping, got {type(matrix).__name__}"]
    for item_id, raw in sorted(matrix.items()):
        location = f"{key}.{item_id}"
        if not isinstance(raw, dict):
            errors.append(f"{location}: must be a mapping")
            continue
        if require_mutation:
            mutation = raw.get("mutation")
            if not isinstance(mutation, str) or not mutation.strip():
                errors.append(f"{location}.mutation: must be a non-empty string")
        refs = _string_list(raw.get("case_refs"))
        if refs is None:
            errors.append(f"{location}.case_refs: must be a non-empty list of non-empty strings")
        else:
            errors.extend(_check_case_refs(refs, location=f"{location}.case_refs", known_refs=known_refs))
    return errors


def _lint_golden_structural_coverage(contract: dict[str, Any], golden_cases: list[GoldenCase]) -> list[str]:
    errors: list[str] = []
    required = _string_list(contract.get("golden_structural_assertions"))
    if required is None:
        return ["golden_structural_assertions: must be a non-empty list of non-empty strings"]
    required_set = set(required)
    covered: set[str] = set()
    for case in golden_cases:
        for entry in case.contract_coverage:
            if not isinstance(entry, str) or not entry:
                errors.append(f"{case.path}: contract_coverage entries must be non-empty strings")
                continue
            covered.add(entry)
    missing = sorted(required_set - covered)
    unknown = sorted(covered - required_set)
    if missing:
        errors.append("golden_structural_assertions: no fixture declares contract_coverage for: " + ", ".join(missing))
    if unknown:
        errors.append("golden fixtures declare unknown contract_coverage entries: " + ", ".join(unknown))
    return errors


def _lint_mutation_anchors(
    root: Path,
    contract: dict[str, Any],
    golden_by_ref: dict[str, GoldenCase],
) -> list[str]:
    errors: list[str] = []
    anchors_path = root / "scripts" / "registry" / "mutation_anchors.yaml"
    try:
        anchor_doc = require_mapping(load_unique_yaml_file(anchors_path), str(anchors_path))
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return [f"{anchors_path}: {exc}"]

    if anchor_doc.get("schema_version") != 1:
        errors.append(f"{anchors_path}: schema_version must be 1")

    try:
        anchors = require_mapping(anchor_doc.get("anchors"), "anchors")
    except ValueError as exc:
        return [f"{anchors_path}: {exc}"]

    adversarial = contract.get("adversarial_classes")
    adversarial_keys = set(adversarial) if isinstance(adversarial, dict) else set()
    if set(anchors) != adversarial_keys:
        errors.append(
            f"{anchors_path}: anchor classes must exactly match adversarial_classes; "
            f"missing={sorted(adversarial_keys - set(anchors))}, extra={sorted(set(anchors) - adversarial_keys)}",
        )

    for class_id, raw in sorted(anchors.items()):
        location = f"{anchors_path}: anchors.{class_id}"
        if not isinstance(raw, dict):
            errors.append(f"{location}: must be a mapping")
            continue

        case_ref = raw.get("case_ref")
        raw_pattern = raw.get("raw_pattern")
        raw_path = raw.get("raw_path")
        unsafe_path = raw.get("unsafe_path")
        for field_name, value in (
            ("case_ref", case_ref),
            ("raw_pattern", raw_pattern),
            ("raw_path", raw_path),
            ("unsafe_path", unsafe_path),
        ):
            if not isinstance(value, str) or not value:
                errors.append(f"{location}.{field_name}: must be a non-empty string")
        if "unsafe_value" not in raw:
            errors.append(f"{location}.unsafe_value: is required")
        if not isinstance(case_ref, str) or not case_ref:
            continue

        fixture = golden_by_ref.get(case_ref)
        if fixture is None:
            errors.append(f"{location}.case_ref: {case_ref!r} does not resolve to a loaded golden fixture")
            continue

        if isinstance(raw_pattern, str) and raw_pattern:
            try:
                re.compile(raw_pattern)
            except re.error as exc:
                errors.append(f"{location}.raw_pattern: invalid regex {raw_pattern!r}: {exc}")

        if isinstance(raw_path, str) and raw_path:
            try:
                resolve_path(fixture.recorded_output, raw_path)
            except KeyError:
                errors.append(
                    f"{location}.raw_path: {raw_path!r} does not exist in "
                    f"{case_ref}'s recorded_output ({fixture.path})",
                )

        if isinstance(unsafe_path, str) and unsafe_path:
            try:
                resolve_path(fixture.recorded_output, unsafe_path)
            except KeyError:
                errors.append(
                    f"{location}.unsafe_path: {unsafe_path!r} does not exist in "
                    f"{case_ref}'s recorded_output ({fixture.path})",
                )

    return errors


def lint_contracts(root: Path, golden_cases: list[GoldenCase] | None = None) -> list[str]:
    """Return a list of referential-integrity errors, empty if clean.

    Pure structural check -- no assertion execution, no fixture mutation.
    Safe and fast to run on every invocation, including --skill-filtered ones.

    Pass golden_cases when the caller already loaded them (__main__.py loads
    them anyway for the eval run itself) so this doesn't parse the fixture
    tree a second time; omitted, it loads evals/golden itself.
    """
    contract_path = root / "scripts" / "registry" / "eval_contracts.yaml"
    try:
        contract = require_mapping(load_unique_yaml_file(contract_path), str(contract_path))
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        return [f"{contract_path}: {exc}"]

    if golden_cases is None:
        try:
            golden_cases = load_golden_fixtures(root / "evals" / "golden")
        except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
            return [f"evals/golden: {exc}"]
    golden_by_ref = golden_case_index(golden_cases)

    known_refs, ref_errors = _known_case_refs(root, golden_cases)
    if ref_errors:
        return sorted(set(ref_errors))

    errors: list[str] = []
    errors.extend(_lint_dimension_coverage(contract, known_refs))
    errors.extend(_lint_behavior_scenarios(contract, known_refs))
    errors.extend(
        _lint_referenced_matrix(
            contract, key="adversarial_classes", known_refs=known_refs, require_mutation=True,
        ),
    )
    errors.extend(
        _lint_referenced_matrix(
            contract, key="untrusted_surfaces", known_refs=known_refs, require_mutation=False,
        ),
    )
    errors.extend(
        _lint_referenced_matrix(
            contract, key="degraded_host_cases", known_refs=known_refs, require_mutation=False,
        ),
    )
    errors.extend(_lint_golden_structural_coverage(contract, golden_cases))
    errors.extend(_lint_mutation_anchors(root, contract, golden_by_ref))
    return sorted(set(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scripts.evals.contract_lint",
        description="Static referential-integrity lint for eval_contracts.yaml / mutation_anchors.yaml.",
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    errors = lint_contracts(args.repo_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"error: {len(errors)} contract reference error(s)", file=sys.stderr)
        return 1

    print("ok: eval contract cross-references resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
