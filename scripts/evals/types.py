from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class EvalResult:
    skill: str
    case_id: str
    passed: bool
    messages: list[str]


def missing_and_failing(
    refs: Iterable[str],
    case_results: dict[str, "EvalResult"],
) -> tuple[list[str], list[str]]:
    """Split `refs` (each a "skill/case_id" key) into (missing, failing) against `case_results`.

    batch3_contract.py and platform_contract.py both resolve eval_contracts.yaml case_refs
    against a result map this same way in several places -- shared here so a fix to the
    missing/failing definition doesn't need to land in both files to stay in sync.
    """
    ref_list = list(refs)
    missing = sorted(ref for ref in ref_list if ref not in case_results)
    failing = sorted(ref for ref in ref_list if ref in case_results and not case_results[ref].passed)
    return missing, failing
