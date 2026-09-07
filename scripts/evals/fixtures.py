"""Tier-1 static fixture loading: `EvalCase` records from `evals/fixtures/**/*.yaml`, plus
the synthetic per-skill cases `evals/fixtures/_global.yaml`'s `happy`/`adversarial` templates
expand into.

A leaf module (no dependency on `scripts.evals.__main__`) specifically so both the CLI
entrypoint (`__main__.py`, which runs these cases) and the referential-integrity linter
(`contract_lint.py`, which only needs the ref set) and the coverage report
(`scripts/eval_tier_health.py`, which only needs per-tier counts) can share one loader and
one definition of "which global template cases actually run" without an import cycle -- the
three used to carry independent, and in one case looser, copies of this logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.registry.schema import Registry
from scripts.yaml_safety import load_unique_yaml_file


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


def global_template_fixture_path(root: Path) -> Path:
    return root / "evals" / "fixtures" / "_global.yaml"


def load_global_template_cases(
    root: Path,
    registry: Registry,
    *,
    skill_filter: str | None = None,
) -> list[EvalCase]:
    """Synthetic `{skill}/global-happy` and `{skill}/global-adversarial` cases for every
    registered skill, from `_global.yaml`'s `happy`/`adversarial` templates -- e.g.
    degraded_host_cases' `backlog-runner/global-happy` resolves only through this path, not
    through any file actually named for that skill.

    A template contributes a case only when its `assertions` field is shaped as a list --
    deliberately looser than `load_fixtures`' own validity rule, which additionally requires
    the list to be non-empty: this mirrors the pre-extraction behavior in `__main__.run_all`
    exactly, so a caller that only wants case identity (contract_lint's ref set) sees exactly
    the cases a caller that runs them (`run_all`) or counts them (`eval_tier_health`) would --
    including the edge case of a template whose `assertions` is present but empty (`[]`),
    which is accepted here (and always has been) and would vacuously pass if run.
    """
    global_fixture = global_template_fixture_path(root)
    if not global_fixture.is_file():
        return []
    global_raw = load_unique_yaml_file(global_fixture)
    if not isinstance(global_raw, dict):
        return []
    cases: list[EvalCase] = []
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
    return cases
