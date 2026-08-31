from __future__ import annotations

from pathlib import Path

from scripts.evals.contract_lint import (
    _known_case_refs,
    _lint_behavior_scenarios,
    _lint_dimension_coverage,
    _lint_golden_structural_coverage,
    _lint_mutation_anchors,
    _lint_referenced_matrix,
    lint_contracts,
    main,
)
from scripts.evals.golden import GoldenCase

ROOT = Path(__file__).resolve().parents[2]


def _golden_case(
    *,
    skill: str = "demo-skill",
    case_id: str = "case-1",
    recorded_output: dict | None = None,
    contract_coverage: list[str] | None = None,
) -> GoldenCase:
    return GoldenCase(
        skill=skill,
        case_id=case_id,
        tier=3,
        description="demo",
        recorded_output=recorded_output if recorded_output is not None else {"result_status": "ok"},
        assertions=[{"type": "field_present", "path": "result_status"}],
        path=Path(f"evals/golden/{skill}/{case_id}.yaml"),
        contract_coverage=contract_coverage or [],
    )


# --- integration: real repo state must stay clean --------------------------


def test_lint_contracts_passes_on_real_repo() -> None:
    assert lint_contracts(ROOT) == []


def test_main_returns_zero_on_real_repo() -> None:
    assert main(["--repo-root", str(ROOT)]) == 0


# --- _lint_dimension_coverage / _lint_behavior_scenarios --------------------


def test_lint_dimension_coverage_flags_missing_case_ref() -> None:
    contract = {"dimension_coverage": {"positive": {"case_refs": ["demo-skill/does-not-exist"]}}}
    errors = _lint_dimension_coverage(contract, known_refs={"demo-skill/case-1"})
    assert any("does-not-exist" in error for error in errors)


def test_lint_dimension_coverage_requires_exactly_one_of_refs_or_gate() -> None:
    both = {"dimension_coverage": {"positive": {"case_refs": ["demo-skill/case-1"], "contract_gate": "routing_collisions"}}}
    neither = {"dimension_coverage": {"positive": {}}}
    for contract in (both, neither):
        errors = _lint_dimension_coverage(contract, known_refs={"demo-skill/case-1"})
        assert any("declare exactly one of case_refs or contract_gate" in error for error in errors)


def test_lint_dimension_coverage_flags_unknown_gate() -> None:
    contract = {"dimension_coverage": {"ambiguous": {"contract_gate": "not_a_real_gate"}}}
    errors = _lint_dimension_coverage(contract, known_refs=set())
    assert any("unknown gate" in error for error in errors)


def test_lint_behavior_scenarios_flags_missing_case_ref() -> None:
    contract = {"behavior_scenarios": {"routing": {"case_refs": ["ghost/nowhere"]}}}
    errors = _lint_behavior_scenarios(contract, known_refs={"demo-skill/case-1"})
    assert any("ghost/nowhere" in error for error in errors)


# --- _lint_referenced_matrix (adversarial_classes / untrusted_surfaces / degraded_host_cases) --


def test_lint_referenced_matrix_requires_mutation_for_adversarial_classes() -> None:
    contract = {"adversarial_classes": {"gate_bypass": {"case_refs": ["demo-skill/case-1"]}}}
    errors = _lint_referenced_matrix(
        contract, key="adversarial_classes", known_refs={"demo-skill/case-1"}, require_mutation=True,
    )
    assert any("mutation" in error and "must be a non-empty string" in error for error in errors)


def test_lint_referenced_matrix_flags_missing_case_ref() -> None:
    contract = {"untrusted_surfaces": {"logs": {"case_refs": ["missing/ref"]}}}
    errors = _lint_referenced_matrix(
        contract, key="untrusted_surfaces", known_refs={"demo-skill/case-1"}, require_mutation=False,
    )
    assert any("missing/ref" in error for error in errors)


def test_lint_referenced_matrix_passes_when_ref_resolves() -> None:
    contract = {"untrusted_surfaces": {"logs": {"case_refs": ["demo-skill/case-1"]}}}
    errors = _lint_referenced_matrix(
        contract, key="untrusted_surfaces", known_refs={"demo-skill/case-1"}, require_mutation=False,
    )
    assert errors == []


# --- _lint_golden_structural_coverage ---------------------------------------


def test_lint_golden_structural_coverage_flags_missing_and_unknown() -> None:
    contract = {"golden_structural_assertions": ["result_status", "confidence"]}
    cases = [_golden_case(contract_coverage=["result_status", "not_a_real_assertion"])]
    errors = _lint_golden_structural_coverage(contract, cases)
    joined = " ".join(errors)
    assert "confidence" in joined
    assert "not_a_real_assertion" in joined


def test_lint_golden_structural_coverage_passes_when_exact_match() -> None:
    contract = {"golden_structural_assertions": ["result_status"]}
    cases = [_golden_case(contract_coverage=["result_status"])]
    assert _lint_golden_structural_coverage(contract, cases) == []


# --- _lint_mutation_anchors (reads mutation_anchors.yaml from disk) ---------


def _write_anchors(tmp_path: Path, body: str) -> None:
    anchors_dir = tmp_path / "scripts" / "registry"
    anchors_dir.mkdir(parents=True, exist_ok=True)
    (anchors_dir / "mutation_anchors.yaml").write_text(body, encoding="utf-8")


def test_lint_mutation_anchors_flags_bad_schema_version(tmp_path: Path) -> None:
    _write_anchors(
        tmp_path,
        """
schema_version: 2
anchors: {}
""",
    )
    contract = {"adversarial_classes": {}}
    errors = _lint_mutation_anchors(tmp_path, contract, golden_by_ref={})
    assert any("schema_version must be 1" in error for error in errors)


def test_lint_mutation_anchors_flags_class_set_mismatch(tmp_path: Path) -> None:
    _write_anchors(
        tmp_path,
        """
schema_version: 1
anchors:
  extra_class:
    case_ref: demo-skill/case-1
    raw_pattern: "foo"
    raw_path: diff_excerpt
    unsafe_path: result_status
    unsafe_value: bad
""",
    )
    contract = {"adversarial_classes": {"instruction_override": {"mutation": "x", "case_refs": ["demo-skill/case-1"]}}}
    errors = _lint_mutation_anchors(tmp_path, contract, golden_by_ref={})
    joined = " ".join(errors)
    assert "missing=['instruction_override']" in joined
    assert "extra=['extra_class']" in joined


def test_lint_mutation_anchors_flags_unresolvable_raw_path(tmp_path: Path) -> None:
    _write_anchors(
        tmp_path,
        """
schema_version: 1
anchors:
  instruction_override:
    case_ref: demo-skill/case-1
    raw_pattern: "foo"
    raw_path: field_that_does_not_exist
    unsafe_path: result_status
    unsafe_value: bad
""",
    )
    contract = {"adversarial_classes": {"instruction_override": {"mutation": "x", "case_refs": ["demo-skill/case-1"]}}}
    fixture = _golden_case(recorded_output={"result_status": "ok", "diff_excerpt": "hi"})
    errors = _lint_mutation_anchors(tmp_path, contract, golden_by_ref={"demo-skill/case-1": fixture})
    assert any(
        "raw_path" in error and "field_that_does_not_exist" in error and "does not exist" in error
        for error in errors
    )


def test_lint_mutation_anchors_flags_unresolvable_case_ref(tmp_path: Path) -> None:
    _write_anchors(
        tmp_path,
        """
schema_version: 1
anchors:
  instruction_override:
    case_ref: demo-skill/does-not-exist
    raw_pattern: "foo"
    raw_path: diff_excerpt
    unsafe_path: result_status
    unsafe_value: bad
""",
    )
    contract = {"adversarial_classes": {"instruction_override": {"mutation": "x", "case_refs": ["demo-skill/does-not-exist"]}}}
    errors = _lint_mutation_anchors(tmp_path, contract, golden_by_ref={})
    assert any("does not resolve to a loaded golden fixture" in error for error in errors)


def test_lint_mutation_anchors_flags_invalid_regex(tmp_path: Path) -> None:
    _write_anchors(
        tmp_path,
        r"""
schema_version: 1
anchors:
  instruction_override:
    case_ref: demo-skill/case-1
    raw_pattern: "["
    raw_path: diff_excerpt
    unsafe_path: result_status
    unsafe_value: bad
""",
    )
    contract = {"adversarial_classes": {"instruction_override": {"mutation": "x", "case_refs": ["demo-skill/case-1"]}}}
    fixture = _golden_case(recorded_output={"result_status": "ok", "diff_excerpt": "hi"})
    errors = _lint_mutation_anchors(tmp_path, contract, golden_by_ref={"demo-skill/case-1": fixture})
    assert any("invalid regex" in error for error in errors)


def test_lint_mutation_anchors_passes_on_valid_anchor(tmp_path: Path) -> None:
    _write_anchors(
        tmp_path,
        """
schema_version: 1
anchors:
  instruction_override:
    case_ref: demo-skill/case-1
    raw_pattern: "Ignore previous"
    raw_path: diff_excerpt
    unsafe_path: result_status
    unsafe_value: bad
""",
    )
    contract = {"adversarial_classes": {"instruction_override": {"mutation": "x", "case_refs": ["demo-skill/case-1"]}}}
    fixture = _golden_case(recorded_output={"result_status": "ok", "diff_excerpt": "Ignore previous instructions"})
    assert _lint_mutation_anchors(tmp_path, contract, golden_by_ref={"demo-skill/case-1": fixture}) == []


# --- _known_case_refs (fixtures + transcripts + golden + _global.yaml) -----


def _write_skill_registry(tmp_path: Path, skill_id: str) -> None:
    (tmp_path / "skills.yaml").write_text(
        f"""
schema_version: 1
skills:
  {skill_id}:
    invocation: ambient
    hosts:
      cursor:
        discovery: manual
      claude:
        install: true
      kiro:
        discovery: manual
    install:
      requires: []
    lint: {{}}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )


def test_known_case_refs_unions_fixtures_transcripts_golden_and_global_template(tmp_path: Path) -> None:
    _write_skill_registry(tmp_path, "demo-skill")

    fixtures_dir = tmp_path / "evals" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    (fixtures_dir / "case.yaml").write_text(
        "skill: demo-skill\ncase_id: fixture-case\nassertions:\n  - type: file_exists\n    path: SKILL.md\n",
        encoding="utf-8",
    )
    (fixtures_dir / "_global.yaml").write_text(
        "happy:\n  assertions:\n    - type: file_exists\n      path: SKILL.md\n"
        "adversarial:\n  assertions:\n    - type: file_exists\n      path: SKILL.md\n",
        encoding="utf-8",
    )

    transcripts_dir = tmp_path / "evals" / "transcripts"
    transcripts_dir.mkdir(parents=True)
    (transcripts_dir / "case.yaml").write_text(
        "skill: demo-skill\ncase_id: transcript-case\n"
        "events:\n  - type: tool_call\nassertions:\n  - type: file_exists\n    path: SKILL.md\n",
        encoding="utf-8",
    )

    golden_cases = [_golden_case(skill="demo-skill", case_id="golden-case")]

    refs, errors = _known_case_refs(tmp_path, golden_cases)
    assert errors == []
    assert refs == {
        "demo-skill/fixture-case",
        "demo-skill/transcript-case",
        "demo-skill/golden-case",
        "demo-skill/global-happy",
        "demo-skill/global-adversarial",
    }


def test_known_case_refs_reports_malformed_fixture(tmp_path: Path) -> None:
    fixtures_dir = tmp_path / "evals" / "fixtures"
    fixtures_dir.mkdir(parents=True)
    (fixtures_dir / "broken.yaml").write_text("case_id: missing-skill-field\n", encoding="utf-8")

    refs, errors = _known_case_refs(tmp_path, [])
    assert refs == set()
    assert any("skill and case_id are required" in error for error in errors)


# --- CLI: main() end-to-end against a broken synthetic repo -----------------


def _write_minimal_valid_repo(tmp_path: Path) -> None:
    golden_dir = tmp_path / "evals" / "golden" / "demo-skill"
    golden_dir.mkdir(parents=True)
    (golden_dir / "case.yaml").write_text(
        "skill: demo-skill\ncase_id: case-1\ntier: 3\ndescription: demo\n"
        "recorded_output:\n  result_status: ok\n  diff_excerpt: hello\n"
        "assertions:\n  - type: field_present\n    path: result_status\n"
        "contract_coverage: [result_status]\n",
        encoding="utf-8",
    )

    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "eval_contracts.yaml").write_text(
        "schema_version: 1\n"
        "dimension_coverage:\n  positive:\n    case_refs: [demo-skill/case-1]\n"
        "behavior_scenarios:\n  correct_invocation:\n    case_refs: [demo-skill/case-1]\n"
        "adversarial_classes:\n  instruction_override:\n    mutation: ignore instructions\n"
        "    case_refs: [demo-skill/case-1]\n"
        "untrusted_surfaces:\n  repository_documentation:\n    case_refs: [demo-skill/case-1]\n"
        "degraded_host_cases:\n  missing_observability:\n    case_refs: [demo-skill/case-1]\n"
        "golden_structural_assertions:\n  - result_status\n",
        encoding="utf-8",
    )
    (registry_dir / "mutation_anchors.yaml").write_text(
        "schema_version: 1\n"
        "anchors:\n  instruction_override:\n    case_ref: demo-skill/case-1\n"
        "    raw_pattern: hello\n    raw_path: diff_excerpt\n"
        "    unsafe_path: result_status\n    unsafe_value: bad\n",
        encoding="utf-8",
    )


def test_lint_contracts_passes_on_minimal_valid_synthetic_repo(tmp_path: Path) -> None:
    _write_minimal_valid_repo(tmp_path)
    assert lint_contracts(tmp_path) == []


def test_main_returns_one_and_prints_the_broken_ref(tmp_path: Path, capsys) -> None:
    _write_minimal_valid_repo(tmp_path)
    contracts_path = tmp_path / "scripts" / "registry" / "eval_contracts.yaml"
    contracts_path.write_text(
        contracts_path.read_text(encoding="utf-8").replace(
            "case_refs: [demo-skill/case-1]\nbehavior_scenarios",
            "case_refs: [demo-skill/typo-ref]\nbehavior_scenarios",
        ),
        encoding="utf-8",
    )

    exit_code = main(["--repo-root", str(tmp_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "demo-skill/typo-ref" in captured.err
