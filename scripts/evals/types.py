from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.yaml_safety import is_valid_schema_version, load_unique_yaml_file, require_mapping

EVAL_CONTRACT_RELATIVE = Path("scripts") / "registry" / "eval_contracts.yaml"
MUTATION_ANCHORS_RELATIVE = Path("scripts") / "registry" / "mutation_anchors.yaml"


@dataclass(frozen=True)
class EvalResult:
    skill: str
    case_id: str
    passed: bool
    messages: list[str]


def eval_result(skill: str, case_id: str, messages: list[str]) -> EvalResult:
    """An EvalResult that passes exactly when it has nothing to report.

    Every contract checker in this package derives pass/fail the same way, from
    an accumulated message list; sharing the derivation keeps "no messages means
    passed" from being restated (and eventually contradicted) per module. Bind
    the skill once per module with functools.partial.
    """
    return EvalResult(skill, case_id, not messages, messages)


def eval_contract_path(root: Path) -> Path:
    return root / EVAL_CONTRACT_RELATIVE


def load_eval_contract(root: Path) -> dict[str, Any]:
    """Read and validate the eval contract document.

    Three checkers (eval_coverage_contract, platform_contract, contract_lint)
    read this one file. Each accepts an already-loaded document so a single run
    parses it once, and falls back to this loader when invoked on its own.
    """
    return require_mapping(load_unique_yaml_file(eval_contract_path(root)), "eval contracts")


def mutation_anchors_path(root: Path) -> Path:
    return root / MUTATION_ANCHORS_RELATIVE


def load_mutation_anchors(root: Path) -> dict[str, Any]:
    """Read and validate mutation_anchors.yaml, returning its `anchors` mapping.

    Three readers (contract_lint, eval_coverage_contract's mutation-anchor matrix,
    mutation_guard's guardrail runner) each used to parse this file with their own
    copy of the `schema_version == 1` + `anchors is a mapping` check -- one of the
    three (mutation_guard) had drifted enough to skip the schema_version check
    entirely. Sharing the check here closes that gap for all three at once, the
    same way `load_eval_contract` already does for eval_contracts.yaml.
    """
    path = mutation_anchors_path(root)
    doc = require_mapping(load_unique_yaml_file(path), str(path))
    if not is_valid_schema_version(doc.get("schema_version")):
        raise ValueError(f"{path}: schema_version must be 1")
    return require_mapping(doc.get("anchors"), f"{path}: anchors")


def missing_and_failing(
    refs: Iterable[str],
    case_results: dict[str, "EvalResult"],
) -> tuple[list[str], list[str]]:
    """Split `refs` (each a "skill/case_id" key) into (missing, failing) against `case_results`.

    eval_coverage_contract.py and platform_contract.py both resolve eval_contracts.yaml case_refs
    against a result map this same way in several places -- shared here so a fix to the
    missing/failing definition doesn't need to land in both files to stay in sync.
    """
    # Deduped: some callers pass a plain list straight from YAML (case_refs can list the same ref
    # twice by mistake), and a "missing referenced eval cases: x, x" message is worse than "x".
    ref_set = set(refs)
    missing = sorted(ref for ref in ref_set if ref not in case_results)
    failing = sorted(ref for ref in ref_set if ref in case_results and not case_results[ref].passed)
    return missing, failing
