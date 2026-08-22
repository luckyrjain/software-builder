from __future__ import annotations

from pathlib import Path

from scripts.evals.__main__ import run_all
from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import parse_registry

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


def test_every_registered_skill_keeps_platform_metadata_in_manifest() -> None:
    from scripts.registry.canonical_manifest import load_canonical_manifest

    registry = parse_registry(ROOT / "skills.yaml")
    manifest = load_canonical_manifest(ROOT)
    assert len(registry.skills) == 34
    assert set(manifest["skills"]) == set(registry.skills)

    for skill_id, entry in registry.skills.items():
        frontmatter = load_skill_frontmatter(ROOT / entry.path / "SKILL.md")
        assert "platform_contract" not in frontmatter
        assert "skill_version" not in frontmatter
        assert manifest["skills"][skill_id]["entrypoint"] == "SKILL.md"
