# e2e-test-creator — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | Browser driver + reachable app URL (local/CI) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Install

```bash
cd software-builder
make install-e2e-test-creator
```

Installs to `~/.cursor/skills/e2e-test-creator` and `~/.claude/skills/e2e-test-creator` by default.
Restart Cursor; a new Claude Code session picks it up automatically.

### Claude Code only

```bash
cd software-builder
make install-claude-e2e-test-creator
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/e2e-test-creator.mdc` and
`.kiro/steering/e2e-test-creator.md` point Cursor/Kiro at `e2e-test-creator/SKILL.md` without an install
step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read/write access to the target repository | Same repo-capable-agent access every skill in this library needs |
| A reachable running instance of the target app | Locally started, a staging URL, or a preview deployment — required to write real user-visible assertions and to run the generated tests; gate as `NEEDS_BROWSER_ENV` when none exists (see [reference/gate-policy.md](reference/gate-policy.md)) |
| The target repo's e2e test command reachable in this session | Only if `run_tests` is left at its default `true` — set `run_tests: false` to draft tests without executing them |
| `ripgrep`/`grep`, standard POSIX tools | Used by `scripts/detect-e2e-tooling.sh`; no extra install beyond what a normal dev shell already has |

No MCP of its own, and no other skill is required to install alongside it — it composes with
**integration-test-creator**, **unit-test-creator**, **contract-test-creator**, **loop-task-implementer**,
and **pr-review** only via the cross-skill handoffs in
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
bash e2e-test-creator/scripts/detect-e2e-tooling.sh e2e-test-creator/tests/fixtures/e2e-detect/playwright-repo
python3 -m pytest e2e-test-creator/tests/test_detect_e2e_tooling.py -q
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Detection returns `NONE_DETECTED` on a repo you know has Playwright/Cypress configured | Check the marker table in [reference/framework-detection.md](reference/framework-detection.md) — a nonstandard config file location isn't detected yet; pass `test_framework_hint` and file a gap |
| Skill keeps asking about browser tooling on every run | `test_framework_hint` isn't being carried between turns, or names a candidate the scan doesn't actually find — check the exact printed `CANDIDATES` list |
| Every journey comes back `NEEDS_BROWSER_ENV` | No reachable app instance was supplied this session — see [reference/gate-policy.md](reference/gate-policy.md) § NEEDS_BROWSER_ENV; supply a local start command, staging URL, or preview deployment |
| Report shows a journey as passing but you never saw it run | Should never happen — see [reference/skill-contract.md](reference/skill-contract.md); file a bug |
| Generated tests assert on CSS class names instead of visible text/role | Check `workflow/generate-tests.md` actually followed the repo's own selector convention, or defaulted to role/accessible-name selectors per [reference/test-quality-deltas.md](reference/test-quality-deltas.md) |
| A production bug the tests found isn't in the report | Check `workflow/report.md` — every `WRITTEN_FAILING_PROD_BUG` journey must get a `## Findings` line |
