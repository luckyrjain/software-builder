# test-writer — Setup


## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-09 |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | None (router only — dispatches to test-creation skills) |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.
## Install

```bash
cd software-builder
make install-test-writer
```

Chains `make install-unit-test-creator install-integration-test-creator install-contract-test-creator
install-e2e-test-creator install-api-test-creator` first — test-writer has no detection or generation
logic of its own and is useless without all five dispatch targets installed alongside it. Restart Cursor
so every skill reloads.

### Claude Code only

```bash
cd software-builder
make install-claude-test-writer
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/test-writer.mdc` and `.kiro/steering/test-writer.md` point
Cursor/Kiro at `test-writer/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Repository read access | Required to validate that `repo_root` resolves to a readable repository scope; test-writer does not inspect source code to classify the level |
| unit-test-creator, integration-test-creator, contract-test-creator, e2e-test-creator, and api-test-creator all installed | `make install-test-writer` chains all five automatically; see each skill's own `SETUP.md` for its own prerequisites |

No MCP or test-execution capability is required by test-writer itself. Beyond the repository-read scope
check above, framework detection, source inspection, test generation, test execution, and write
capabilities belong to the specialists it dispatches.

## Config

No config file. `request`, `repo_root`, and an optional `level_hint` are passed at invocation time — see
[workflow/inputs.md](workflow/inputs.md). Ordinary specialist-owned fields are passed through unchanged to
every planned specialist. Framework-owned `execution_context` is advanced independently for each child
dispatch according to the inherited runtime recursion contract; it is not copied unchanged.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [prompt-injection](../docs/skill-framework/shared/prompt-injection.md)
- [skill-routing](../docs/skill-framework/shared/skill-routing.md)
- [runtime-contract recursion protection](../docs/skill-framework/shared/runtime-contract.md#8-recursion-protection)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- [test-creation-principles](../docs/skill-framework/shared/test-creation-principles.md) — shared rules
  the five dispatch targets honor

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| test-writer prints its own framework-detection or target-selection output | Bug — this router has no detection/generation logic; check nothing in `workflow/delegate.md` re-implements a dispatched skill's own phase |
| Classify never asks, even on a genuinely ambiguous request | Check [reference/level-classification.md](reference/level-classification.md)'s ambiguity rules; do not invent an unlisted default |
| Only one specialist runs for an explicitly complementary multi-level request | Check Classify/Delegate for stale single-dispatch logic or destructive `level_hint` handling |
| Report looks different from what the dispatched skill would produce standalone | Regression in relay behavior — check [workflow/delegate.md](workflow/delegate.md) §§2–3 |
| Child dispatch reuses the parent's depth/visited state unchanged | Regression in recursion protection — check [workflow/delegate.md](workflow/delegate.md) §2 and the shared runtime contract |
| "Command not found" / skill has nothing to dispatch to | Re-run `make install-test-writer` — it should chain all five dispatch-target installs; see Prerequisites above |
