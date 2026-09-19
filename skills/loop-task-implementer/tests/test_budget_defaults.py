from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/loop-task-implementer"
BACKLOG = ROOT / "skills/backlog-runner"


def _budgets():
    schema = yaml.safe_load((SKILL / "reference/state-schema.yaml").read_text(encoding="utf-8"))
    return schema["budgets"]


def test_per_task_budgets_have_non_null_positive_defaults():
    budgets = _budgets()
    for key in ("max_task_elapsed_minutes", "max_task_tokens"):
        value = budgets[key]
        assert isinstance(value, int) and not isinstance(value, bool), key
        assert value > 0, key


def test_orchestrator_documents_the_same_defaults_as_the_schema():
    budgets = _budgets()
    text = (SKILL / "workflow/orchestrator.md").read_text(encoding="utf-8")
    assert f"default `{budgets['max_task_elapsed_minutes']} minutes`" in text
    assert f"default `{budgets['max_task_tokens']:,}`" in text
    assert "`unlimited`" in text
    assert "unset budget is never" in text


def test_backlog_runner_session_budgets_are_never_unbounded_by_default():
    inputs = (BACKLOG / "workflow/inputs.md").read_text(encoding="utf-8")
    assert "None — no wall-clock stop" not in inputs
    assert "None — no session-level token ceiling" not in inputs
    assert "start" in inputs and "8 hours" in inputs
    assert f"{_budgets()['max_task_tokens']:,}" in inputs
    assert "`unlimited`" in inputs
