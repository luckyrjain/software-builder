from __future__ import annotations

from pathlib import Path

from scripts.evals.__main__ import run_all
from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import parse_registry
from scripts.registry.skill_frontmatter_schema import PLATFORM_CONTRACT

ROOT = Path(__file__).resolve().parents[2]


def test_platform_eval_contract_is_wired_into_default_runner() -> None:
    results = run_all(ROOT)
    platform_results = {result.case_id: result for result in results if result.skill == "platform"}

    expected = {
        "routing-prd-vs-code-review",
        "routing-prod-failure-vs-sizing",
        "adversarial-class-instruction_override",
        "untrusted-surface-webhook_payloads",
        "degraded-host-missing_observability",
        "golden-structural-coverage",
        "required-dimensions",
    }
    assert expected.issubset(platform_results)
    assert all(result.passed for result in platform_results.values()), platform_results


def test_every_registered_skill_visibly_declares_platform_contract() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    assert len(registry.skills) == 23

    for skill_id, entry in registry.skills.items():
        frontmatter = load_skill_frontmatter(ROOT / entry.path / "SKILL.md")
        assert frontmatter.get("platform_contract") == PLATFORM_CONTRACT, skill_id
