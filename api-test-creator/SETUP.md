# api-test-creator — Setup

## Install

```bash
cd software-builder
make install-api-test-creator
```

Installs to `~/.cursor/skills/api-test-creator` and `~/.claude/skills/api-test-creator` by default.
Restart Cursor; a new Claude Code session picks it up automatically.

### Claude Code only

```bash
cd software-builder
make install-claude-api-test-creator
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/api-test-creator.mdc` and
`.kiro/steering/api-test-creator.md` point Cursor/Kiro at `api-test-creator/SKILL.md` without an install
step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Read/write access to the target repository | Same repo-capable-agent access every skill in this library needs |
| A real, reachable running API instance | Only if `run_tests` is left at its default `true` — set `run_tests: false` to draft requests without running them (see [reference/gate-policy.md](reference/gate-policy.md)) |
| `newman` reachable in this session (or installable via `npx newman`) | Only when `run_tests: true`; requests are still written and marked `UNVERIFIED` without it |
| `ripgrep`/`grep`, standard POSIX tools, `find` | Used by `scripts/detect-postman-tooling.sh`; no extra install beyond what a normal dev shell already has |

No MCP of its own, and no other skill is required to install alongside it — it composes with
**unit-test-creator**, **integration-test-creator**, **contract-test-creator**, **e2e-test-creator**, and
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
bash api-test-creator/scripts/detect-postman-tooling.sh api-test-creator/tests/fixtures/postman-detect/single-collection
python3 -m pytest api-test-creator/tests/test_detect_postman_tooling.py -q
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Detection returns `NONE_DETECTED` on a repo you know has a Postman collection | Check the marker table in [reference/framework-detection.md](reference/framework-detection.md) — a nonstandard file extension or an excluded path isn't detected yet; pass `test_framework_hint` and file a gap |
| Skill keeps asking which collection to use on every run | `test_framework_hint` isn't being carried between turns, or names a candidate the scan doesn't actually find — check the exact printed `CANDIDATES` list |
| Report shows a target as passing but you never saw it run | Should never happen — see [reference/skill-contract.md](reference/skill-contract.md) §7; file a bug |
| Generated request/response looks fabricated / too generic | Check `workflow/generate-tests.md` §1 actually found a real route-handler match, spec entry, or catalog corroboration — if none exists the target should be `NEEDS_OBSERVED_ENDPOINT`, not a guess |
| A production-bug finding isn't in the report | Check `workflow/report.md` §3 — every `WRITTEN_FAILING_PROD_BUG` target must get a `## Findings` line |
| Every target comes back `NEEDS_API_ENV` unexpectedly | Confirm this session can actually reach the API (local start command ran, staging URL resolves) before re-running — see [reference/gate-policy.md §6](reference/gate-policy.md#6-no-reachable-api-instance) |
