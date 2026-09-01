from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.eval_tier_health import (
    build_eval_tier_health,
    build_per_skill_golden_coverage,
    is_healthy,
    render_markdown,
)
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_eval_tier_health_covers_all_deterministic_tiers() -> None:
    report = build_eval_tier_health()

    assert report["required_tiers"] == 3
    assert report["covered_tiers"] == 3
    assert set(report["tiers"]) == {
        "tier_1_structural",
        "tier_2_transcript",
        "tier_3_golden",
    }
    assert all(count > 0 for count in report["tiers"].values())
    assert report["unexpected_static_tiers"] == {}
    assert report["live_model_harness"] == {
        "available": True,
        "ci_blocking": False,
    }
    assert is_healthy(report) is True


_MINIMAL_SKILLS_YAML = """
schema_version: 1
skills:
  example:
    path: example
    category: architecture
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    capabilities:
      required: [host.repository.read]
    lint:
      skill_md_max_lines: 180
      target: example
    risk_class: [read-only]
"""


def test_global_template_with_invalid_assertions_is_excluded(tmp_path: Path) -> None:
    (tmp_path / "skills.yaml").write_text(_MINIMAL_SKILLS_YAML, encoding="utf-8")
    fixtures_dir = tmp_path / "evals" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    (tmp_path / "evals" / "transcripts").mkdir(parents=True)
    (tmp_path / "evals" / "golden").mkdir(parents=True)
    (fixtures_dir / "_global.yaml").write_text(
        "happy:\n"
        "  tier: 1\n"
        "  assertions:\n"
        "    - type: contains\n"
        "      value: ok\n"
        "adversarial:\n"
        "  tier: 1\n"
        "  assertions: null\n",
        encoding="utf-8",
    )

    report = build_eval_tier_health(tmp_path)

    # scripts.evals.__main__.run_all() skips a global template whose
    # `assertions` isn't a list -- this report must not claim coverage the
    # real eval runner wouldn't execute. Only "happy" (1 registered skill)
    # should be counted; "adversarial" has assertions: null.
    assert report["tiers"]["tier_1_structural"] == 1


def test_missing_live_harness_does_not_fail_deterministic_health() -> None:
    report = build_eval_tier_health()
    report["live_model_harness"] = {"available": False, "ci_blocking": False}

    assert is_healthy(report) is True
    assert "Live model harness: **missing** (non-blocking)" in render_markdown(report)


def test_eval_tier_health_markdown_is_deterministic_and_explicit() -> None:
    report = build_eval_tier_health()

    first = render_markdown(report)
    second = render_markdown(report)

    assert first == second
    assert "### Eval tier coverage" in first
    assert "Tier 1 structural cases" in first
    assert "Tier 2 transcript cases" in first
    assert "Tier 3 golden cases" in first
    assert "Deterministic tiers covered: **3/3**" in first
    assert "Unexpected static tiers: **0**" in first
    assert "Live model harness: **available** (non-blocking)" in first


def test_eval_tier_health_cli_runs_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/eval_tier_health.py", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"covered_tiers": 3' in result.stdout
    assert '"unexpected_static_tiers": {}' in result.stdout


# --- Fix 1: per-skill Tier-3 golden coverage (non-fatal WARNING) -----------------


def _two_skill_yaml() -> str:
    def entry(name: str) -> str:
        return f"""  {name}:
    path: {name}
    category: architecture
    invocation: ambient
    hosts:
      cursor: {{discovery: rule}}
      claude: {{install: true}}
      kiro: {{discovery: manual}}
    install:
      requires: []
    capabilities:
      required: [host.repository.read]
    lint:
      skill_md_max_lines: 180
      target: {name}
    risk_class: [read-only]
"""

    return "schema_version: 1\nskills:\n" + entry("alpha") + entry("beta") + entry("gamma")


def _write_golden_fixture(path: Path, *, skill: str, case_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                f"skill: {skill}",
                f"case_id: {case_id}",
                "tier: 3",
                "description: test fixture",
                "recorded_output:",
                "  status: ok",
                "assertions:",
                "  - type: field_present",
                "    path: status",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _stub_repo(tmp_path: Path) -> Path:
    """A tiny repo with three skills exercising every branch of the new check:

    alpha: only the mandatory adversarial anchor golden -> flagged.
    beta:  the adversarial anchor plus a real positive-path golden -> not flagged.
    gamma: no golden fixtures at all -> flagged, no adversarial anchor either.
    """
    (tmp_path / "skills.yaml").write_text(_two_skill_yaml(), encoding="utf-8")
    golden_dir = tmp_path / "evals" / "golden"
    _write_golden_fixture(golden_dir / "alpha" / "golden-injection.yaml", skill="alpha", case_id="golden-injection")
    _write_golden_fixture(golden_dir / "beta" / "golden-injection.yaml", skill="beta", case_id="golden-injection")
    _write_golden_fixture(golden_dir / "beta" / "positive-case.yaml", skill="beta", case_id="positive-case")

    adversarial_dir = tmp_path / "evals" / "adversarial"
    adversarial_dir.mkdir(parents=True)
    (adversarial_dir / "cases.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "dimension: adversarial",
                "cases:",
                "  - skill: alpha",
                "    golden_ref: alpha/golden-injection",
                "  - skill: beta",
                "    golden_ref: beta/golden-injection",
                "  - skill: gamma",
                "    golden_ref: gamma/golden-injection",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_per_skill_golden_coverage_flags_skills_with_only_the_adversarial_anchor(tmp_path: Path) -> None:
    root = _stub_repo(tmp_path)

    coverage = build_per_skill_golden_coverage(root)

    assert coverage["skills"]["alpha"] == {
        "golden_case_count": 1,
        "has_adversarial_anchor": True,
        "has_non_adversarial_golden": False,
    }
    assert coverage["skills"]["beta"] == {
        "golden_case_count": 2,
        "has_adversarial_anchor": True,
        "has_non_adversarial_golden": True,
    }
    assert coverage["skills"]["gamma"] == {
        "golden_case_count": 0,
        "has_adversarial_anchor": False,
        "has_non_adversarial_golden": False,
    }
    assert coverage["skills_missing_non_adversarial_golden"] == ["alpha", "gamma"]


def test_per_skill_golden_coverage_is_non_fatal(tmp_path: Path) -> None:
    root = _stub_repo(tmp_path)
    coverage = build_per_skill_golden_coverage(root)
    assert coverage["skills_missing_non_adversarial_golden"] == ["alpha", "gamma"]

    # Splice the stub repo's gap into an otherwise-healthy real report (same
    # override pattern as test_missing_live_harness_does_not_fail_deterministic_health
    # above) so this test isolates the one thing it's checking: that a
    # non-empty per-skill warning list never flips is_healthy() to False.
    report = build_eval_tier_health()
    assert is_healthy(report) is True
    report["per_skill_golden_coverage"] = coverage
    assert is_healthy(report) is True

    markdown = render_markdown(report)
    assert "Per-skill Tier-3 golden coverage (WARNING, non-blocking)" in markdown
    assert "Skills missing non-adversarial golden coverage: **2**" in markdown
    assert "`alpha`" in markdown
    assert "`gamma`" in markdown
    assert "`beta`" not in markdown.split("### Per-skill Tier-3 golden coverage")[1]


def test_per_skill_golden_coverage_reports_zero_when_nothing_missing(tmp_path: Path) -> None:
    root = _stub_repo(tmp_path)
    # Give alpha and gamma a non-adversarial golden too, closing the gap.
    _write_golden_fixture(
        root / "evals" / "golden" / "alpha" / "positive-case.yaml", skill="alpha", case_id="positive-case"
    )
    _write_golden_fixture(
        root / "evals" / "golden" / "gamma" / "positive-case.yaml", skill="gamma", case_id="positive-case"
    )

    report = build_eval_tier_health(root)
    assert report["per_skill_golden_coverage"]["skills_missing_non_adversarial_golden"] == []
    assert "Skills missing non-adversarial golden coverage: **0**" in render_markdown(report)


def test_per_skill_golden_coverage_covers_every_registered_skill_on_real_repo() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    coverage = build_per_skill_golden_coverage(ROOT)

    assert set(coverage["skills"]) == set(registry.skills)
    # is_healthy() must stay indifferent to this new field on the real repo too.
    report = build_eval_tier_health(ROOT)
    assert is_healthy(report) is True
