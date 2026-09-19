from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/loop-task-implementer"
SCRIPT = SKILL / "scripts/run_log.py"

RUN_ID = "run-2026-09-19-a1"


def _load():
    spec = importlib.util.spec_from_file_location("loop_run_log_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def run_log():
    return _load()


@pytest.fixture()
def log_dir(tmp_path):
    return tmp_path / "runs"


def _append(run_log, log_dir, event="run_started", actor="orchestrator", **kwargs):
    return run_log.append_event(log_dir, RUN_ID, event, actor, **kwargs)


def _cli(*args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, **(env or {})},
    )


# --- append + chain ---------------------------------------------------------------------------


def test_first_record_starts_the_chain(run_log, log_dir):
    record = _append(run_log, log_dir)
    assert record["schema_version"] == 1
    assert record["seq"] == 1
    assert record["run_id"] == RUN_ID
    assert record["prev_hash"] == "0" * 64
    assert re.fullmatch(r"[0-9a-f]{64}", record["hash"])


def test_records_chain_by_hash_and_sequence(run_log, log_dir):
    first = _append(run_log, log_dir)
    second = _append(run_log, log_dir, event="task_selected")
    assert second["seq"] == 2
    assert second["prev_hash"] == first["hash"]
    assert run_log.verify_log(log_dir, RUN_ID).ok


def test_log_file_is_private_and_outside_any_repo_by_default(run_log, log_dir):
    _append(run_log, log_dir)
    path = run_log.log_path(log_dir, RUN_ID)
    assert (path.stat().st_mode & 0o777) == 0o600
    assert (log_dir.stat().st_mode & 0o777) == 0o700


def test_default_log_dir_is_home_based_not_cwd(run_log, monkeypatch, tmp_path):
    monkeypatch.delenv("SOFTWARE_BUILDER_RUN_LOG_DIR", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert run_log.resolve_log_dir(None) == tmp_path / "home" / ".software-builder" / "runs"


def test_environment_cannot_redirect_the_log_dir(run_log, monkeypatch, tmp_path):
    monkeypatch.setenv("SOFTWARE_BUILDER_RUN_LOG_DIR", str(tmp_path / "hostile"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
    assert run_log.resolve_log_dir(None) == tmp_path / "home" / ".software-builder" / "runs"


# --- input validation -------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["", ".", "..", "-rf", "a/b", "a\\b", "x" * 129, "a b", "a;b", "a\x00b"])
def test_run_id_must_be_a_safe_slug(run_log, log_dir, bad):
    with pytest.raises(ValueError):
        run_log.append_event(log_dir, bad, "run_started", "orchestrator")


def test_unknown_event_and_actor_are_rejected(run_log, log_dir):
    with pytest.raises(ValueError):
        _append(run_log, log_dir, event="made_up_event")
    with pytest.raises(ValueError):
        _append(run_log, log_dir, actor="somebody")


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": -1},
        {"input_tokens": True},
        {"input_tokens": 1.5},
        {"elapsed_seconds": float("inf")},
        {"cost_usd": -0.01},
        {"unknown_field": 1},
        "not-a-dict",
    ],
)
def test_usage_is_validated(run_log, log_dir, usage):
    with pytest.raises(ValueError):
        _append(run_log, log_dir, usage=usage)


def test_data_must_be_json_and_bounded(run_log, log_dir):
    with pytest.raises(ValueError):
        # each string is truncated on its own, so exceeding the record cap takes many fields
        _append(run_log, log_dir, data={f"k{i}": "x" * 4000 for i in range(10)})
    with pytest.raises(ValueError):
        _append(run_log, log_dir, data={"bad": object()})
    with pytest.raises(ValueError):
        _append(run_log, log_dir, data={"bad key": 1})


def test_symlinked_log_file_is_refused(run_log, log_dir, tmp_path):
    log_dir.mkdir(mode=0o700)
    target = tmp_path / "elsewhere.jsonl"
    target.write_text("")
    os.symlink(target, run_log.log_path(log_dir, RUN_ID))
    with pytest.raises((OSError, ValueError)):  # refused by the containment check or O_NOFOLLOW
        _append(run_log, log_dir)
    assert target.read_text() == ""

@pytest.mark.parametrize("bad", ["relative/dir", "~nope/../x", "/tmp/ok/../escape"])
def test_log_dir_must_be_absolute_without_dotdot(run_log, bad):
    with pytest.raises(ValueError):
        run_log.resolve_log_dir(bad)


def test_log_dir_inside_the_current_repo_is_refused(run_log, tmp_path, monkeypatch):
    repo = tmp_path / "target-repo"
    (repo / ".git").mkdir(parents=True)
    (repo / "src").mkdir()
    monkeypatch.chdir(repo / "src")
    with pytest.raises(ValueError, match="outside the repository"):
        run_log.resolve_log_dir(str(repo / ".run-logs"))
    assert run_log.resolve_log_dir(str(tmp_path / "elsewhere")) == tmp_path / "elsewhere"


def test_symlinked_log_directory_is_refused(run_log, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    link = tmp_path / "runs"
    os.symlink(outside, link)
    with pytest.raises(OSError, match="symlinked log directory"):
        run_log.append_event(link, RUN_ID, "run_started", "orchestrator")
    assert list(outside.iterdir()) == []


# --- redaction --------------------------------------------------------------------------------


def test_secrets_are_redacted_before_they_reach_disk(run_log, log_dir):
    token = "ghp_" + "a1B2c3D4" * 4 + "a1B2"  # 36 chars after the prefix, the shape redaction.py matches
    record = _append(
        run_log,
        log_dir,
        event="builder_returned",
        actor="builder",
        data={"note": f"pushed using {token}", "nested": {"header": f"Authorization: Bearer {token}"}},
    )
    on_disk = run_log.log_path(log_dir, RUN_ID).read_text()
    assert token not in on_disk
    assert token not in json.dumps(record)
    assert record["redactions"], "redaction hits must be recorded, not silent"
    assert run_log.verify_log(log_dir, RUN_ID).ok


def test_long_strings_are_truncated_not_dumped(run_log, log_dir):
    record = _append(run_log, log_dir, data={"diff": "y" * 9000})
    assert len(record["data"]["diff"]) < 5000
    assert record["data"]["diff"].endswith("[truncated]")


# --- verify -----------------------------------------------------------------------------------


def _lines(run_log, log_dir):
    return run_log.log_path(log_dir, RUN_ID).read_text().splitlines()


def test_verify_detects_an_edited_record(run_log, log_dir):
    _append(run_log, log_dir)
    _append(run_log, log_dir, event="task_selected", data={"task_id": "T-1"})
    path = run_log.log_path(log_dir, RUN_ID)
    lines = _lines(run_log, log_dir)
    path.write_text("\n".join([lines[0], lines[1].replace("T-1", "T-2")]) + "\n")
    result = run_log.verify_log(log_dir, RUN_ID)
    assert not result.ok
    assert any("hash" in error for error in result.errors)


def test_verify_detects_a_deleted_record(run_log, log_dir):
    for event in ("run_started", "task_selected", "builder_dispatched"):
        _append(run_log, log_dir, event=event)
    path = run_log.log_path(log_dir, RUN_ID)
    lines = _lines(run_log, log_dir)
    path.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert not run_log.verify_log(log_dir, RUN_ID).ok


def test_verify_rejects_garbage_and_missing_logs(run_log, log_dir):
    assert not run_log.verify_log(log_dir, RUN_ID).ok  # nothing to verify is not a pass
    _append(run_log, log_dir)
    path = run_log.log_path(log_dir, RUN_ID)
    path.write_text(path.read_text() + "not json\n")
    assert not run_log.verify_log(log_dir, RUN_ID).ok


def test_append_refuses_to_extend_a_broken_chain(run_log, log_dir):
    _append(run_log, log_dir)
    path = run_log.log_path(log_dir, RUN_ID)
    path.write_text(path.read_text().replace("run_started", "task_selected"))
    with pytest.raises(ValueError):
        _append(run_log, log_dir, event="task_selected")


# --- summarize + budget -----------------------------------------------------------------------


def _seed_usage(run_log, log_dir):
    _append(run_log, log_dir, ts="2026-09-19T10:00:00.000Z")
    _append(
        run_log,
        log_dir,
        event="builder_returned",
        actor="builder",
        usage={"input_tokens": 1000, "output_tokens": 500, "elapsed_seconds": 60, "cost_usd": 0.25},
        ts="2026-09-19T10:10:00.000Z",
    )
    _append(
        run_log,
        log_dir,
        event="review_returned",
        actor="reviewer",
        usage={"input_tokens": 400, "output_tokens": 100},
        ts="2026-09-19T10:20:00.000Z",
    )


def test_summarize_totals_usage_by_actor(run_log, log_dir):
    _seed_usage(run_log, log_dir)
    summary = run_log.summarize_log(log_dir, RUN_ID, now="2026-09-19T10:30:00.000Z")
    assert summary["events"] == 3
    assert summary["usage"]["total_tokens"] == 2000
    assert summary["usage"]["cost_usd"] == pytest.approx(0.25)
    assert summary["by_actor"]["builder"]["total_tokens"] == 1500
    assert summary["by_actor"]["reviewer"]["total_tokens"] == 500
    assert summary["elapsed_minutes"] == pytest.approx(30.0)
    assert summary["chain_head"] == run_log.verify_log(log_dir, RUN_ID).head


def test_budget_defaults_match_the_state_schema(run_log):
    schema = yaml.safe_load((SKILL / "reference/state-schema.yaml").read_text())
    assert run_log.DEFAULT_MAX_TASK_TOKENS == schema["budgets"]["max_task_tokens"]
    assert run_log.DEFAULT_MAX_TASK_MINUTES == schema["budgets"]["max_task_elapsed_minutes"]


def test_budget_breach_on_tokens(run_log, log_dir):
    _seed_usage(run_log, log_dir)
    verdict = run_log.check_budget(log_dir, RUN_ID, max_tokens=2000, max_minutes=180, now="2026-09-19T10:30:00.000Z")
    assert verdict["exceeded"] == ["tokens"]  # reaching the cap counts, per the orchestrator rule


def test_budget_breach_on_elapsed_time(run_log, log_dir):
    _seed_usage(run_log, log_dir)
    verdict = run_log.check_budget(log_dir, RUN_ID, max_tokens=None, max_minutes=30, now="2026-09-19T10:30:00.000Z")
    assert verdict["exceeded"] == ["elapsed_minutes"]


def test_budget_ok_and_unlimited_is_explicit(run_log, log_dir):
    _seed_usage(run_log, log_dir)
    ok = run_log.check_budget(log_dir, RUN_ID, max_tokens=10_000, max_minutes=60, now="2026-09-19T10:30:00.000Z")
    assert ok["exceeded"] == []
    unlimited = run_log.check_budget(
        log_dir, RUN_ID, max_tokens=None, max_minutes=None, now="2026-09-19T10:30:00.000Z"
    )
    assert unlimited["exceeded"] == []
    assert sorted(unlimited["unlimited"]) == ["elapsed_minutes", "tokens"]


# --- CLI --------------------------------------------------------------------------------------


def test_cli_append_verify_summarize_round_trip(log_dir):
    common = ["--run-id", RUN_ID, "--log-dir", str(log_dir)]
    appended = _cli("append", *common, "--event", "run_started", "--actor", "orchestrator", "--data-json", '{"task":"T-1"}')
    assert appended.returncode == 0, appended.stderr
    assert json.loads(appended.stdout)["seq"] == 1
    usage = '{"input_tokens": 10, "output_tokens": 5}'
    assert _cli("append", *common, "--event", "builder_returned", "--actor", "builder", "--usage-json", usage).returncode == 0
    verified = _cli("verify", *common)
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["events"] == 2
    summary = _cli("summarize", *common)
    assert summary.returncode == 0
    assert json.loads(summary.stdout)["usage"]["total_tokens"] == 15


def test_cli_budget_exit_codes(log_dir):
    common = ["--run-id", RUN_ID, "--log-dir", str(log_dir)]
    usage = '{"input_tokens": 100, "output_tokens": 0}'
    assert _cli("append", *common, "--event", "builder_returned", "--actor", "builder", "--usage-json", usage).returncode == 0
    assert _cli("budget", *common, "--max-tokens", "1000").returncode == 0
    breached = _cli("budget", *common, "--max-tokens", "100")
    assert breached.returncode == 1
    assert json.loads(breached.stdout)["exceeded"] == ["tokens"]


def test_cli_budget_defaults_apply_when_flags_are_omitted(log_dir):
    common = ["--run-id", RUN_ID, "--log-dir", str(log_dir)]
    usage = '{"input_tokens": 3000000, "output_tokens": 0}'
    assert _cli("append", *common, "--event", "builder_returned", "--actor", "builder", "--usage-json", usage).returncode == 0
    breached = _cli("budget", *common)
    assert breached.returncode == 1  # the 2,000,000-token default, not "unbounded"
    assert _cli("budget", *common, "--max-tokens", "unlimited").returncode == 0


@pytest.mark.parametrize(
    "args",
    [
        [],
        ["--help"],
        ["frobnicate"],
        ["append", "--run-id", "../x", "--event", "run_started", "--actor", "orchestrator"],
        ["append", "--run-id", RUN_ID, "--event", "nope", "--actor", "orchestrator"],
        ["append", "--run-id", RUN_ID, "--event", "run_started", "--actor", "orchestrator", "--data-json", "{not json"],
        ["verify", "--run-id", RUN_ID],
        ["budget", "--run-id", RUN_ID, "--max-tokens", "-5"],
    ],
)
def test_cli_fails_closed_never_exit_zero_on_bad_input(args, log_dir):
    result = _cli(*args, "--log-dir", str(log_dir)) if args and not args[0].startswith("-") else _cli(*args)
    assert result.returncode in (1, 2)


def test_cli_verify_exit_1_on_tamper(log_dir):
    common = ["--run-id", RUN_ID, "--log-dir", str(log_dir)]
    _cli("append", *common, "--event", "run_started", "--actor", "orchestrator", "--data-json", '{"task":"T-1"}')
    path = log_dir / f"{RUN_ID}.jsonl"
    path.write_text(path.read_text().replace("T-1", "T-9"))
    assert _cli("verify", *common).returncode == 1


# --- docs and wiring stay in sync -------------------------------------------------------------


def test_reference_documents_every_event_and_actor(run_log):
    text = (SKILL / "reference/run-log.md").read_text(encoding="utf-8")
    for event in run_log.EVENTS:
        assert f"`{event}`" in text, event
    for actor in run_log.ACTORS:
        assert f"`{actor}`" in text, actor


def test_orchestrator_and_schema_point_at_the_run_log():
    orchestrator = (SKILL / "workflow/orchestrator.md").read_text(encoding="utf-8")
    assert "scripts/run_log.py" in orchestrator
    assert "reference/run-log.md" in orchestrator
    schema = yaml.safe_load((SKILL / "reference/state-schema.yaml").read_text(encoding="utf-8"))
    assert set(schema["run_log"]) >= {"run_id", "path", "chain_head"}
