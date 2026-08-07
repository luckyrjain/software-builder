# test-writer — Setup

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
| unit-test-creator, integration-test-creator, contract-test-creator, e2e-test-creator, and api-test-creator all installed | `make install-test-writer` chains all five automatically; see each skill's own `SETUP.md` for its own prerequisites |

No MCP, no repository access, and no execution capability of its own — every real prerequisite belongs
to whichever skill this router dispatches to.

## Config

No config file. `request`, `repo_root`, and an optional `level_hint` are passed at invocation time — see
[workflow/inputs.md](workflow/inputs.md). Every other field is passed through unchanged to the dispatched
skill.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [prompt-injection](../docs/skill-framework/shared/prompt-injection.md)
- [skill-routing](../docs/skill-framework/shared/skill-routing.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)
- [test-creation-principles](../docs/skill-framework/shared/test-creation-principles.md) — shared rules
  the five dispatch targets honor

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| test-writer prints its own framework-detection or target-selection output | Bug — this router has no detection/generation logic; check nothing in `workflow/delegate.md` re-implements a dispatched skill's own phase |
| Classify never asks, even on a genuinely ambiguous request | Check [reference/level-classification.md](reference/level-classification.md)'s "unambiguous defaults" section wasn't extended past its two listed cases |
| Report looks different from what the dispatched skill would produce standalone | Regression in relay behavior — check [workflow/delegate.md](workflow/delegate.md) §2 |
| "Command not found" / skill has nothing to dispatch to | Re-run `make install-test-writer` — it should chain all five dispatch-target installs; see Prerequisites above |
