from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "evals" / "fixtures"
TRANSCRIPTS_DIR = ROOT / "evals" / "transcripts"
GLOBAL_FIXTURE = FIXTURES_DIR / "_global.yaml"

WORKFLOW_REQUIRED_KEYS = ("workflow_version", "phase", "produces", "consumes")


@dataclass(frozen=True)
class EvalCase:
    skill: str
    case_id: str
    tier: int
    description: str
    assertions: list[dict[str, Any]]
    path: Path


@dataclass(frozen=True)
class EvalResult:
    skill: str
    case_id: str
    passed: bool
    messages: list[str]


def load_fixtures(fixtures_dir: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for path in sorted(fixtures_dir.rglob("*.yaml")):
        if path.name.startswith("_"):
            continue
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
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
            except ValueError as exc:
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
        disable = frontmatter.get("disable-model-invocation") is True
        if entry.invocation == "automation-only" and not disable:
            return ["automation-only skill missing disable-model-invocation"]
        return []

    raise ValueError(f"unknown assertion type: {atype!r}")


def run_case(root: Path, case: EvalCase) -> EvalResult:
    messages: list[str] = []
    skill_md = _skill_dir(root, case.skill) / "SKILL.md"
    if not skill_md.is_file():
        return EvalResult(case.skill, case.case_id, False, [f"missing SKILL.md for {case.skill}"])

    for index, assertion in enumerate(case.assertions):
        try:
            messages.extend(_run_assertion(root, case.skill, assertion))
        except (OSError, ValueError, KeyError) as exc:
            messages.append(f"assertion[{index}] failed: {exc}")

    return EvalResult(case.skill, case.case_id, not messages, messages)


def run_all(
    root: Path,
    *,
    skill_filter: str | None = None,
    tier_filter: int | None = None,
) -> list[EvalResult]:
    from scripts.evals.transcript import load_transcript_fixtures, run_transcript_case

    registry = parse_registry(root / "skills.yaml")
    cases = load_fixtures(FIXTURES_DIR)
    transcript_cases = load_transcript_fixtures(root / "evals" / "transcripts")
    if GLOBAL_FIXTURE.is_file():
        global_raw = yaml.safe_load(GLOBAL_FIXTURE.read_text(encoding="utf-8"))
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
                            path=GLOBAL_FIXTURE,
                        ),
                    )

    results: list[EvalResult] = []
    seen: set[tuple[str, str]] = set()
    for case in cases:
        if skill_filter and case.skill != skill_filter:
            continue
        if tier_filter is not None and case.tier != tier_filter:
            continue
        key = (case.skill, case.case_id)
        if key in seen:
            continue
        seen.add(key)
        if case.skill not in registry.skills:
            results.append(
                EvalResult(case.skill, case.case_id, False, ["skill not in skills.yaml"]),
            )
            continue
        results.append(run_case(root, case))

    for case in transcript_cases:
        if skill_filter and case.skill != skill_filter:
            continue
        if tier_filter is not None and case.tier != tier_filter:
            continue
        key = (case.skill, case.case_id)
        if key in seen:
            continue
        seen.add(key)
        if case.skill not in registry.skills:
            results.append(
                EvalResult(case.skill, case.case_id, False, ["skill not in skills.yaml"]),
            )
            continue
        results.append(run_transcript_case(case))
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
    parser.add_argument("--tier", type=int, help="run evals for one tier only (1=contract, 2=transcript)")
    parser.add_argument("--report", type=Path, help="write JSON report to path")
    args = parser.parse_args(argv)

    try:
        results = run_all(args.repo_root, skill_filter=args.skill, tier_filter=args.tier)
    except (ValueError, yaml.YAMLError) as exc:
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
