# integration-test-creator — Setup

## Install

```bash
cd software-builder
make install-integration-test-creator
```

Installs to `~/.cursor/skills/integration-test-creator` and `~/.claude/skills/integration-test-creator` by
default. Restart Cursor; a new Claude Code session picks it up automatically.

### Claude Code only

```bash
cd software-builder
make install-claude-integration-test-creator
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/integration-test-creator.mdc` and
`.kiro/steering/integration-test-creator.md` point Cursor/Kiro at
`integration-test-creator/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read/write access to the target repository | Same repo-capable-agent access every skill in this library needs |
| The target repo's test command reachable in this session | Only if `run_tests` is left at its default `true` — set `run_tests: false` to draft tests without executing them (see [reference/gate-policy.md](reference/gate-policy.md)) |
| A way to stand up the real dependency (testcontainers/Docker, docker-compose, or an embedded convention already in the repo) | Only needed to actually run tests against a real dependency; its absence tags targets `NEEDS_INTEGRATION_ENV` rather than blocking the whole run (see [reference/gate-policy.md §5](reference/gate-policy.md#5-zero-orchestration-mechanism-detected)) |
| `ripgrep`/`grep`, standard POSIX tools | Used by `scripts/detect-integration-setup.sh`; no extra install beyond what a normal dev shell already has |

No MCP of its own, and no other skill is required to install alongside it — it composes with
**unit-test-creator**, **contract-test-creator**, **e2e-test-creator**, **pr-review**, and
**loop-task-implementer** only via the cross-skill handoffs in
[SKILL.md](SKILL.md#cross-skill-escalation), never as a hard install dependency.

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
bash integration-test-creator/scripts/detect-integration-setup.sh integration-test-creator/tests/fixtures/integration-detect/testcontainers-python
python3 -m pytest integration-test-creator/tests/test_detect_integration_setup.py -q
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Detection returns `NONE_DETECTED` on a repo you know has tests | Check the marker table in [reference/framework-detection.md](reference/framework-detection.md) — an unsupported ecosystem or a nonstandard config file location isn't detected yet; pass `test_framework_hint` and file a gap |
| `ORCHESTRATION: none` on a repo that clearly uses testcontainers | Check the orchestration marker table in [reference/framework-detection.md](reference/framework-detection.md) — a nonstandard manifest location isn't detected yet |
| Every target lands as `NEEDS_INTEGRATION_ENV` even though docker-compose is present | Confirm the compose file is at one of the recognized locations/names — see [reference/framework-detection.md](reference/framework-detection.md) |
| Skill keeps asking about framework choice on every run | `test_framework_hint` isn't being carried between turns, or names a candidate the scan doesn't actually find — check the exact printed `CANDIDATES` list |
| Report shows a target as passing but you never saw it run | Should never happen — see [reference/skill-contract.md](reference/skill-contract.md); file a bug |
| A generated test mocks the dependency instead of using the real one | Check `workflow/generate-tests.md` — this is the one thing this skill must never do; file a bug and re-run |
| A production bug the tests found isn't in the report | Check `workflow/report.md` §3 — every `WRITTEN_FAILING_PROD_BUG` target must get a `## Findings` line |
