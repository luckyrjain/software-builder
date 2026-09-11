# architecture-remediation-loop — Setup

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-09-11 |
| **Review cadence** | Quarterly — or when any composed skill's own contract changes |
| **External services** | None of its own — inherits whatever each composed skill requires |

See [setup-freshness.md](../../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Install

```bash
cd software-builder
make install-architecture-remediation-loop
```

This chains install of **codebase-architecture-review**, **engineering-decision-discovery**,
**module-design**, **loop-task-implementer**, and **production-readiness-review** — this skill has no
review, grilling, design, implementation, or PR logic of its own and is useless without all five installed
alongside it. Restart Cursor so every skill reloads.

### Claude Code

```bash
cd software-builder
make install-claude-architecture-remediation-loop
```

No restart needed. See [claude-code-setup.md](../../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/architecture-remediation-loop.mdc` and
`.kiro/steering/architecture-remediation-loop.md` point Cursor/Kiro at
`skills/architecture-remediation-loop/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| codebase-architecture-review installed and configured | Read-only repository access — see its own `SETUP.md` |
| engineering-decision-discovery installed and configured | Read-only repository access — see its own `SETUP.md` |
| module-design installed and configured | Read-only repository access — see its own `SETUP.md` |
| loop-task-implementer installed and configured | Repository/git write access, isolation primitive (subagent/fresh-session/worktree) — see [loop-task-implementer/reference/mcp-capabilities.md](../loop-task-implementer/reference/mcp-capabilities.md) |
| production-readiness-review installed and configured | Composes pr-review plus applicable specialist reviews — see its own `SETUP.md` |

## Directory map

```
architecture-remediation-loop/
  SKILL.md                 # Orchestrator (≤180 lines)
  examples.md
  workflow/                # Inputs → Discover → Disposition → Remediate → Converge
  reference/                # Candidate ledger, PR-batching policy, convergence gates, report format, smoke/pressure tests
```

## Config

| Setting | Where | Purpose |
|---------|-------|---------|
| `review_scope` | Caller input, per run | Bounded paths/subsystem/question — never the whole repository at once |
| `max_cycles` | Caller input, optional | Outer convergence-loop hard cap, default 5 |
| `max_candidates_per_cycle` | Caller input, optional | Per-cycle ledger growth cap, default 20 — start conservative on a first run |

## Framework links

- [skill-framework README](../../docs/skill-framework/README.md)
- [cross-skill-escalation](../../docs/skill-framework/shared/cross-skill-escalation.md)
- [prompt-injection](../../docs/skill-framework/shared/prompt-injection.md)
- [safe-output](../../docs/skill-framework/shared/safe-output.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a small
bounded `review_scope` you control, with a low `max_cycles`.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Loop never converges after several cycles | Check `architecture_remediation_report.stopped_reason` — most likely `MAX_CYCLES_REACHED`; raise `max_cycles` only once you've confirmed the ledger is actually shrinking, not oscillating |
| Same candidate reappears every cycle | Check Discover's deduplication step — an `ACCEPT`ed but not-yet-`COMPLETED` row should be `DUPLICATE`, not a fresh candidate; see [reference/pressure-tests.md](reference/pressure-tests.md) |
| A batch keeps escalating | Check the candidate's provisional classification in [reference/pr-batching-policy.md](reference/pr-batching-policy.md) — it likely belongs in a dedicated batch, not grouped |
| Anything got merged | This should never happen — if it did, treat it as a bug in the invocation (this skill has no input path for `autonomous_merge_authorized: true`), not expected behavior |
