# unit-test-creator — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | None (local test runners) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Install

```bash
cd software-builder
make install-unit-test-creator
```

Installs to `~/.cursor/skills/unit-test-creator` and `~/.claude/skills/unit-test-creator` by default.
Restart Cursor; a new Claude Code session picks it up automatically.

### Claude Code only

```bash
cd software-builder
make install-claude-unit-test-creator
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/unit-test-creator.mdc` and
`.kiro/steering/unit-test-creator.md` point Cursor/Kiro at `unit-test-creator/SKILL.md` without an
install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read/write access to the target repository | Same repo-capable-agent access every skill in this library needs |
| The target repo's test command reachable in this session | Only if `run_tests` is left at its default `true` — set `run_tests: false` to draft tests without executing them (see [reference/gate-policy.md](reference/gate-policy.md)) |
| `ripgrep`/`grep`, standard POSIX tools | Used by `scripts/detect-test-framework.sh`; no extra install beyond what a normal dev shell already has |

No MCP of its own, and no other skill is required to install alongside it — it composes with
**test-writer** (as a dispatch target), **integration-test-creator** (escalation for a target that
needs a real dependency), **pr-review**, and **loop-task-implementer** only via the cross-skill
handoffs in [SKILL.md](SKILL.md#cross-skill-escalation), never as a hard install dependency.

## Config

No config file. Every input (`target`, `repo_root`, `run_tests`, …) is passed at invocation time — see
[workflow/inputs.md](workflow/inputs.md).

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [test-creation-principles](../docs/skill-framework/shared/test-creation-principles.md)
- [prompt-injection](../docs/skill-framework/shared/prompt-injection.md)
- [skill-routing](../docs/skill-framework/shared/skill-routing.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).

```bash
bash unit-test-creator/scripts/detect-test-framework.sh unit-test-creator/tests/fixtures/test-framework-detect/python-pytest
python3 -m pytest unit-test-creator/tests/test_detect_test_framework.py -q
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Detection returns `NONE_DETECTED` on a repo you know has tests | Check the marker table in [reference/framework-detection.md](reference/framework-detection.md) — an unsupported ecosystem or a nonstandard config file location isn't detected yet; pass `test_framework_hint` and file a gap |
| Skill keeps asking about framework choice on every run | `test_framework_hint` isn't being carried between turns, or names a candidate the scan doesn't actually find — check the exact printed `CANDIDATES` list |
| Report shows a target as passing but you never saw it run | Should never happen — see [reference/skill-contract.md](reference/skill-contract.md) §6; file a bug |
| Generated tests don't match the repo's existing style | Check `workflow/detect-conventions.md` §4 actually read 1–2 existing test files for layout/mock style, not just the framework name |
| A "unit" test reaches a real network call or database | Check `workflow/generate-tests.md` §3 — every external dependency must be mocked; if it genuinely can't be, that's `UNTESTABLE_WITHOUT_FIXTURE`, not a real network call |
| A production bug the tests found isn't in the report | Check `workflow/report.md` §3 — every `WRITTEN_FAILING_PROD_BUG` target must get a `## Findings` line |
