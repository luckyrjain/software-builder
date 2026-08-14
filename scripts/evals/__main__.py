from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.evals.batch3_contract import run_batch3_contract_checks
from scripts.evals.golden import (
    find_oversized_descriptions,
    find_vacuous_anchored_patterns,
    load_golden_fixtures,
    run_golden_case,
)
from scripts.evals.mutation_guard import run_guardrail_mutation_checks
from scripts.evals.platform_contract import run_platform_contract_checks
from scripts.evals.scenario_harness import run_per_skill_scenarios
from scripts.evals.transcript import load_transcript_fixtures, run_transcript_case
from scripts.evals.types import EvalResult
from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import Registry, parse_registry
from scripts.registry.skill_frontmatter_schema import automation_only_guard_errors
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]

WORKFLOW_REQUIRED_KEYS = ("workflow_version", "phase", "produces", "consumes")


@dataclass(frozen=True)
class EvalCase:
    skill: str
    case_id: str
    tier: int
    description: str
    assertions: list[dict[str, Any]]
    path: Path


def load_fixtures(fixtures_dir: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for path in sorted(fixtures_dir.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = load_unique_yaml_file(path)
        if not isinstance(raw, dict):
            raise ValueError(f"{path}: fixture root must be a mapping")
        skill = str(raw.get("skill", ""))
        case_id = str(raw.get("case_id", ""))
        if not skill or not case_id:
            raise ValueError(f"{path}: skill and case_id are required")
        assertions = raw.get("assertions", [])
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(f"{path}: assertions must be a non-empty list")
        cases.append(
            EvalCase(
                skill=skill,
                case_id=case_id,
                tier=int(raw.get("tier", 1)),
                description=str(raw.get("description", "")),
                assertions=assertions,
                path=path,
            ),
        )
    return cases


def _skill_dir(root: Path, skill_id: str) -> Path:
    return root / skill_id


def _run_assertion(
    root: Path,
    skill_id: str,
    assertion: dict[str, Any],
) -> list[str]:
    atype = str(assertion.get("type", ""))
    if atype == "file_exists":
        rel = str(assertion.get("path", ""))
        target = _skill_dir(root, skill_id) / rel
        if not target.is_file():
            return [f"missing file: {rel}"]
        return []

    if atype == "skill_md_contains":
        pattern = str(assertion.get("pattern", ""))
        skill_md = (_skill_dir(root, skill_id) / "SKILL.md").read_text(encoding="utf-8")
        if not re.search(pattern, skill_md, flags=re.IGNORECASE | re.MULTILINE):
            return [f"SKILL.md missing pattern: {pattern!r}"]
        return []

    if atype == "forbid_pattern":
        rel = str(assertion.get("path", "SKILL.md"))
        pattern = str(assertion.get("pattern", ""))
        text = (_skill_dir(root, skill_id) / rel).read_text(encoding="utf-8")
        if re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE):
            return [f"{rel} matched forbidden pattern: {pattern!r}"]
        return []

    if atype == "workflow_frontmatter_all":
        workflow_dir = _skill_dir(root, skill_id) / "workflow"
        if not workflow_dir.is_dir():
            return [f"missing workflow directory for {skill_id}"]
        errors: list[str] = []
        for workflow_file in sorted(workflow_dir.glob("*.md")):
            try:
                frontmatter = load_skill_frontmatter(workflow_file)
            except YAML_SAFETY_ERRORS as exc:
                errors.append(f"{workflow_file.name}: {exc}")
                continue
            for key in WORKFLOW_REQUIRED_KEYS:
                if key not in frontmatter:
                    errors.append(f"{workflow_file.name}: missing frontmatter key {key!r}")
        return errors

    if atype == "path_contains":
        rel = str(assertion.get("path", ""))
        pattern = str(assertion.get("pattern", ""))
        target = _skill_dir(root, skill_id) / rel
        if not target.is_file():
            return [f"missing file: {rel}"]
        if not re.search(pattern, target.read_text(encoding="utf-8"), flags=re.IGNORECASE | re.MULTILINE):
            return [f"{rel} missing pattern: {pattern!r}"]
        return []

    if atype == "registry_invocation":
        registry = parse_registry(root / "skills.yaml")
        expected = str(assertion.get("expected", ""))
        actual = registry.skills[skill_id].invocation
        if actual != expected:
            return [f"registry invocation {actual!r} != expected {expected!r}"]
        return []

    if atype == "automation_only_guard":
        registry = parse_registry(root / "skills.yaml")
        entry = registry.skills[skill_id]
        frontmatter = load_skill_frontmatter(_skill_dir(root, skill_id) / "SKILL.md")
        return automation_only_guard_errors(entry.invocation, frontmatter)

    raise ValueError(f"unknown assertion type: {atype!r}")


def run_case(root: Path, case: EvalCase) -> EvalResult:
    messages: list[str] = []
    skill_md = _skill_dir(root, case.skill) / "SKILL.md"
    if not skill_md.is_file():
        return EvalResult(case.skill, case.case_id, False, [f"missing SKILL.md for {case.skill}"])

    for index, assertion in enumerate(case.assertions):
        try:
            messages.extend(_run_assertion(root, case.skill, assertion))
        except (OSError, KeyError, *YAML_SAFETY_ERRORS) as exc:
            messages.append(f"assertion[{index}] failed: {exc}")

    return EvalResult(case.skill, case.case_id, not messages, messages)


def filtered(
    case_list: Iterable[Any],
    skill_filter: str | None,
    tier_filter: int | None,
) -> Iterator[Any]:
    for case in case_list:
        if skill_filter and case.skill != skill_filter:
            continue
        if tier_filter is not None and case.tier != tier_filter:
            continue
        yield case


def admit_case(
    case: Any,
    dispatch: Callable[[Any], EvalResult],
    *,
    seen: set[tuple[str, str]],
    registry: Registry,
) -> EvalResult:
    key = (case.skill, case.case_id)
    if key in seen:
        return EvalResult(
            case.skill,
            case.case_id,
            False,
            [f"duplicate eval case id for skill {case.skill!r}"],
        )
    seen.add(key)
    if case.skill not in registry.skills:
        return EvalResult(case.skill, case.case_id, False, ["skill not in skills.yaml"])
    return dispatch(case)


def run_all(
    root: Path,
    *,
    skill_filter: str | None = None,
    tier_filter: int | None = None,
    golden_cases: list[Any] | None = None,
) -> list[EvalResult]:
    registry = parse_registry(root / "skills.yaml")
    cases = load_fixtures(root / "evals" / "fixtures")
    transcript_cases = load_transcript_fixtures(root / "evals" / "transcripts")
    if golden_cases is None:
        golden_cases = load_golden_fixtures(root / "evals" / "golden")
    global_fixture = root / "evals" / "fixtures" / "_global.yaml"
    if global_fixture.is_file():
        global_raw = load_unique_yaml_file(global_fixture)
        if isinstance(global_raw, dict):
            for skill_id in sorted(registry.skills):
                if skill_filter and skill_id != skill_filter:
                    continue
                for template_name in ("happy", "adversarial"):
                    template = global_raw.get(template_name)
                    if not isinstance(template, dict):
                        continue
                    assertions = template.get("assertions", [])
                    if not isinstance(assertions, list):
                        continue
                    cases.append(
                        EvalCase(
                            skill=skill_id,
                            case_id=f"global-{template_name}",
                            tier=int(template.get("tier", 1)),
                            description=str(template.get("description", "")),
                            assertions=assertions,
                            path=global_fixture,
                        ),
                    )

    results: list[EvalResult] = []
    seen: set[tuple[str, str]] = set()
    for case in filtered(cases, skill_filter, tier_filter):
        results.append(admit_case(case, lambda c: run_case(root, c), seen=seen, registry=registry))
    for case in filtered(transcript_cases, skill_filter, tier_filter):
        results.append(admit_case(case, run_transcript_case, seen=seen, registry=registry))
    for case in filtered(golden_cases, skill_filter, tier_filter):
        results.append(admit_case(case, run_golden_case, seen=seen, registry=registry))

    # Repository-wide scenario/contract checks belong to the normal unfiltered
    # harness. Focused --skill/--tier runs stay focused and do not claim full
    # platform coverage.
    if skill_filter is None and tier_filter is None:
        scenario_results = run_per_skill_scenarios(
            root,
            registry,
            case_results=results,
            golden_cases=golden_cases,
        )
        results.extend(scenario_results)

        platform_results = run_platform_contract_checks(
            root,
            registry,
            case_results=results,
            golden_cases=golden_cases,
        )
        results.extend(platform_results)

        mutation_results = run_guardrail_mutation_checks(root, golden_cases)
        results.extend(mutation_results)

        results.extend(
            run_batch3_contract_checks(
                root,
                registry,
                case_results=results,
                golden_cases=golden_cases,
            ),
        )
    return results


def summarize(results: list[EvalResult]) -> dict[str, Any]:
    passed = sum(1 for result in results if result.passed)
    return {
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": [
            {
                "skill": result.skill,
                "case_id": result.case_id,
                "passed": result.passed,
                "messages": result.messages,
            }
            for result in results
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scripts.evals")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--skill", help="run evals for one skill id")
    parser.add_argument("--tier", type=int, help="run evals for one tier only (1=contract, 2=transcript, 3=golden)")
    parser.add_argument("--report", type=Path, help="write JSON report to path")
    args = parser.parse_args(argv)

    try:
        golden_dir = args.repo_root / "evals" / "golden"
        golden_cases = load_golden_fixtures(golden_dir)
        for checker in (find_vacuous_anchored_patterns, find_oversized_descriptions):
            for warning in checker(golden_cases, skill_filter=args.skill, tier_filter=args.tier):
                print(f"warning: {warning}", file=sys.stderr)
        results = run_all(
            args.repo_root, skill_filter=args.skill, tier_filter=args.tier, golden_cases=golden_cases,
        )
    except (OSError, ValueError, *YAML_SAFETY_ERRORS) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    summary = summarize(results)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    failed = 0
    for result in results:
        status = "ok" if result.passed else "FAIL"
        print(f"{status}: {result.skill}/{result.case_id}")
        if result.messages:
            for message in result.messages:
                print(f"  - {message}", file=sys.stderr)
        if not result.passed:
            failed += 1

    if failed:
        print(f"error: {failed} eval case(s) failed", file=sys.stderr)
        return 1
    print(f"ok: {summary['passed']} eval case(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
