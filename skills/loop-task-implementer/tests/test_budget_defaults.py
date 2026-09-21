from pathlib import Path
import re

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/loop-task-implementer"
BACKLOG = ROOT / "skills/backlog-runner"


def _budgets():
    return yaml.safe_load((SKILL / "reference/state-schema.yaml").read_text(encoding="utf-8"))["budgets"]


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_per_task_budgets_have_non_null_positive_integer_defaults():
    budgets = _budgets()
    for key in ("max_task_elapsed_minutes", "max_task_tokens"):
        value = budgets[key]
        assert isinstance(value, int) and not isinstance(value, bool) and value > 0, key


@pytest.mark.parametrize(
    "path",
    [
        SKILL / "workflow/orchestrator.md",
        SKILL / "SETUP.md",
        SKILL / "SKILL.md",
    ],
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_every_loop_task_implementer_doc_states_the_schema_defaults(path):
    budgets = _budgets()
    text = _text(path)
    assert f"{budgets['max_task_tokens']:,}" in text, "the token default is missing or differs from state-schema.yaml"
    assert f"{budgets['max_task_elapsed_minutes']} minutes" in text or f"`{budgets['max_task_elapsed_minutes']}`" in text
    assert "unlimited" in text or "never unbounded" in text


def test_orchestrator_says_unset_is_never_unbounded_and_names_the_explicit_opt_out():
    text = _text(SKILL / "workflow/orchestrator.md")
    assert "never\n  treated as unbounded" in text or "never treated as unbounded" in text
    assert re.search(r"explicit value\s+`unlimited`", text)
    assert "--max-tokens" in text and "--max-minutes" in text  # the resolved caps reach the budget command


@pytest.mark.parametrize(
    "path",
    [
        BACKLOG / "workflow/inputs.md",
        BACKLOG / "SKILL.md",
        BACKLOG / "SETUP.md",
        BACKLOG / "reference/queue-policy.md",
    ],
    ids=lambda p: str(p.relative_to(ROOT)),
)
def test_every_backlog_runner_doc_states_the_same_session_defaults(path):
    text = _text(path)
    assert re.search(r"\b8 ?(hours|h)\b", text), "the 8-hour deadline default is missing or changed"
    assert f"{_budgets()['max_task_tokens']:,}" in text, "the per-task token figure behind the session default is missing"
    assert "unlimited" in text
    for stale in ("None — no wall-clock stop", "None — no session-level token ceiling"):
        assert stale not in text


def test_the_morning_summary_format_and_example_carry_the_budgets_line():
    assert "**Budgets:**" in _text(BACKLOG / "reference/morning-summary-format.md")
    assert "**Budgets:**" in _text(BACKLOG / "examples.md")


def test_cost_optimization_planner_does_not_claim_backlog_runners_defaults():
    text = _text(ROOT / "skills/cost-optimization-sprint-planner/SKILL.md")
    assert "Same optional circuit breakers as backlog-runner" not in text
