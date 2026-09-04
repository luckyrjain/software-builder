from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.yaml_safety import load_unique_frontmatter
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _raw_manifest() -> dict:
    return load_canonical_manifest(ROOT)


def _route(prompt: str) -> str | None:
    result = dispatch_prompt(ROOT, load_registry(ROOT), prompt)
    assert result.status == "selected", result
    return result.owner


def test_planner_is_read_only_leaf() -> None:
    manifest = _raw_manifest()
    assert manifest["contracts"]["composition_runtime"]["skill_types"]["implementation-planner"] == "leaf"
    skill = manifest["skills"]["implementation-planner"]
    assert skill["risk_class"] == ["read-only"]
    assert skill["permissions"] == {
        "repository": "read",
        "external_actions": "none",
        "unattended": False,
        "merge": False,
    }
    assert manifest["contracts"]["platform"]["skill_permissions"]["implementation-planner"] == skill["permissions"]


def test_planner_has_no_child_invokes() -> None:
    assert load_registry(ROOT).skills["implementation-planner"].composition.invokes == []


def test_plan_is_canonical_proposed_state() -> None:
    manifest = _raw_manifest()
    runtime = manifest["contracts"]["composition_runtime"]
    assert runtime["artifact_ownership"]["implementation_plan"] == {
        "mode": "canonical",
        "owners": ["implementation-planner"],
    }
    platform = manifest["contracts"]["platform"]["artifact_runtime"]
    assert platform["state_semantics"]["implementation_plan"] == "proposed_state"
    assert platform["allowed_state_semantics"]["implementation_plan"] == ["proposed_state"]


def test_implementation_plan_v1_contract_fields() -> None:
    manifest = load_canonical_manifest(ROOT)
    composition = manifest["contracts"]["composition"]
    assert "implementation_plan" in composition["artifact_types"]
    assert composition["artifact_schemas"]["implementation_plan"]["fields"] == [
        "plan_set_id",
        "plan_id",
        "title",
        "readiness",
        "assessment_target",
        "target_repo",
        "external_dependencies",
        "source_refs",
        "tasks",
        "execution_waves",
        "sequencing_constraints",
        "verification_gates",
        "traceability",
    ]


def test_planner_skill_package_declares_read_only_contract() -> None:
    frontmatter = load_unique_frontmatter(ROOT / "implementation-planner" / "SKILL.md")
    skill_text = (ROOT / "implementation-planner" / "SKILL.md").read_text(encoding="utf-8")
    assert frontmatter["name"] == "implementation-planner"
    for required_text in (
        "host.report.write",
        "host.repository.read",
        "READY",
        "PARTIAL",
        "BLOCKED",
        "loop-task-implementer",
    ):
        assert required_text in skill_text


def test_loop_task_remains_implementation_prompt_owner() -> None:
    assert (
        _route("Implement this task, review the changes, fix issues, and repeat until zero issues.")
        == "loop-task-implementer"
    )


def test_decomposition_prompt_routes_to_planner() -> None:
    assert _route("Create a dependency-aware implementation plan with execution waves and traceability.") == "implementation-planner"


def test_planner_selection_never_grants_merge_authority() -> None:
    result = dispatch_prompt(ROOT, load_registry(ROOT), "Create an implementation plan and merge the resulting changes.")
    assert result.status == "selected"
    assert result.owner == "implementation-planner"
    permissions = _raw_manifest()["skills"]["implementation-planner"]["permissions"]
    assert permissions["merge"] is False
    assert permissions["external_actions"] == "none"
