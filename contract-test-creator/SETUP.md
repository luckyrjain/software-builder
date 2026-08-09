# contract-test-creator — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | Pact Broker (optional, repo-specific) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Install

```bash
cd software-builder
make install-contract-test-creator
```

Installs to `~/.cursor/skills/contract-test-creator` and `~/.claude/skills/contract-test-creator` by
default. Restart Cursor; a new Claude Code session picks it up automatically.

### Claude Code only

```bash
cd software-builder
make install-claude-contract-test-creator
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/contract-test-creator.mdc` and
`.kiro/steering/contract-test-creator.md` point Cursor/Kiro at `contract-test-creator/SKILL.md` without an
install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read/write access to the target repository | Same repo-capable-agent access every skill in this library needs |
| The target repo's test command reachable in this session | Only if `run_tests` is left at its default `true` — set `run_tests: false` to draft tests without executing them (see [reference/gate-policy.md](reference/gate-policy.md)) |
| A real running provider reachable, for a `role: provider` verification run | Only when `run_tests: true` — draft with `run_tests: false` if this session can't reach it |
| Pact Broker credentials/network access, if the repo has `broker_configured: yes` | Only needed to actually publish/fetch pacts during verification; detection itself never requires broker access |
| `ripgrep`/`grep`, standard POSIX tools | Used by `scripts/detect-pact-tooling.sh`; no extra install beyond what a normal dev shell already has |

No MCP of its own, and no other skill is required to install alongside it — it composes with
**integration-test-creator**, **unit-test-creator**, and **loop-task-implementer** only via the
cross-skill handoffs in [SKILL.md](SKILL.md#cross-skill-escalation), never as a hard install dependency.

## Config

No config file. Every input (`target` including `role`, `repo_root`, `run_tests`, …) is passed at
invocation time — see [workflow/inputs.md](workflow/inputs.md).

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [test-creation-principles](../docs/skill-framework/shared/test-creation-principles.md)
- [prompt-injection](../docs/skill-framework/shared/prompt-injection.md)
- [skill-routing](../docs/skill-framework/shared/skill-routing.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).

```bash
bash contract-test-creator/scripts/detect-pact-tooling.sh contract-test-creator/tests/fixtures/pact-detect/python-provider-local
python3 -m pytest contract-test-creator/tests/test_detect_pact_tooling.py -q
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Detection returns `NONE_DETECTED` on a repo you know has Pact configured | Check the marker table in [reference/framework-detection.md](reference/framework-detection.md) — an unsupported ecosystem or a nonstandard manifest location isn't detected yet; pass `test_framework_hint` and file a gap |
| Skill keeps asking which Pact library to use on every run | `test_framework_hint` isn't being carried between turns, or names a candidate the scan doesn't actually find — check the exact printed `CANDIDATES` list |
| Skill keeps asking for `role` on every run | `target.role` isn't being carried between turns — it must be supplied on the invocation, it is never inferred or cached from a prior run's tooling detection |
| Report shows a target as passing but you never saw it run | Should never happen — see [reference/skill-contract.md](reference/skill-contract.md) §7; file a bug |
| Generated interaction shape looks fabricated / too generic | Check `workflow/generate-tests.md` §3 actually found a real call site, client method, or schema file — if none exists the target should be `NEEDS_OBSERVED_INTERACTION`, not a guess |
| A provider verification failure isn't in the report | Check `workflow/report.md` §3 — every `WRITTEN_FAILING_PROD_BUG` target must get a `## Findings` line |
