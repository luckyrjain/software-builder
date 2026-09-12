"""Tests for the host_adapter.py capability-family bridge.

`host.report.write` (a chat/artifact-output-only capability) used to be mapped onto the
same `write_repo` family as `host.repository.read_write`, so a report-only skill was
evaluated as if it needed full repository write access -- wrongly capped at whatever
support level a host declares for `write_repo` even on a host that can render report
output just fine. These tests pin the fix: `host.report.write` resolves to its own
`report_output` family, distinct from `write_repo`.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.host_adapter import CAPABILITIES, HOST_CAPABILITY_FAMILIES, HOSTS, capability_support

ROOT = Path(__file__).resolve().parents[2]


def test_report_write_capability_is_not_a_full_repo_write_family() -> None:
    assert "report_output" in CAPABILITIES
    assert HOST_CAPABILITY_FAMILIES["host.report.write"] == ("report_output",)
    assert HOST_CAPABILITY_FAMILIES["host.repository.read_write"] == ("read_repo", "write_repo")


def test_report_output_is_full_on_every_host() -> None:
    """None of report_output's semantics require repository write, so every host --
    including chatgpt/generic, whose write_repo is degraded -- can support it fully."""
    for host in sorted(HOSTS):
        assert capability_support(ROOT, host, "report_output") == "full"
