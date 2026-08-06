# weekly-squad-digest — Setup

## Ambient discovery is deliberately disabled

Like backlog-runner, this skill sets `disable-model-invocation: true` — it does not auto-apply from a
human's natural-language chat turn. It's meant to be invoked explicitly, on a schedule, by the automation
described below. A human asking "what's our migration status" or "where's the cost waste" should keep
routing to **migration-program-manager** or **cost-optimization-sprint-planner** directly — those already
handle the single-source, on-demand case; this skill exists only for the combined scheduled digest.

## Install

```bash
cd ai-skills
make install-weekly-squad-digest
```

This chains `make install-migration-program-manager install-cost-optimization-sprint-planner` first —
this skill has no aggregation logic of its own and produces an empty digest without at least one of the
two rollup files already existing. Restart Cursor so all three skills reload.

### Claude Code

```bash
cd ai-skills
make install-claude-weekly-squad-digest
```

No restart needed. See [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/weekly-squad-digest.mdc` and
`.kiro/steering/weekly-squad-digest.md` point Cursor/Kiro at `weekly-squad-digest/SKILL.md` without an
install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| migration-program-manager already run at least once | Produces `migration_program_rollup.json` — see [migration-program-manager/SETUP.md](../migration-program-manager/SETUP.md) |
| cost-optimization-sprint-planner already run at least once | Produces `cost_optimization_sprint_rollup.json` — see [cost-optimization-sprint-planner/SETUP.md](../cost-optimization-sprint-planner/SETUP.md) |
| A scheduler | Cron, a scheduled CI/CD job, or equivalent — see § Integration contract |

No MCP of its own — this skill never queries GitLab, Datadog, or any other MCP server directly, and
never invokes either producing skill live.

## Integration contract (for whoever builds the scheduling trigger and delivery)

This repo ships **agent instructions**, not a running scheduler or a Slack-posting bot — same boundary as
every other trigger-driven skill in this repo. The handler you build:

1. Registers a weekly (or whatever cadence fits) scheduled job that starts an agent session with this
   skill installed, **after** that same schedule has already run migration-program-manager and
   cost-optimization-sprint-planner so their rollup files are current.
2. Passes `rollup_manifest` (the two rollup file paths) and, optionally, `staleness_warning_days` — see
   [workflow/inputs.md](workflow/inputs.md).
3. **Delivers the returned `WEEKLY_SQUAD_DIGEST.md` to wherever § Config points.** This skill's own
   output is one combined markdown document — it does **not** compute a per-squad channel routing table
   or post to Slack itself. If you want true per-squad channel delivery (e.g. `payments` squad's section
   posted to `#payments-eng`), your handler is where that squad→channel mapping has to live — no skill in
   this repo (including squad-map) has one today; see the
   [design spec § Correcting two claims](../docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md#correcting-two-claims-before-designing-against-them)
   for why this skill doesn't assume one exists. A single combined post/document is the simpler, fully
   precedented option (same as backlog-runner's own morning summary).

## Config

| Setting | Where | Purpose |
|---------|-------|---------|
| `rollup_manifest` | Handler config | Paths to the two rollup JSON files — configure once per environment, not per run |
| `staleness_warning_days` | Handler config, optional | Default 14 — how old a rollup item can be before the digest flags it |
| Notification target(s) | Handler config | Where the digest gets routed — one target for a combined post, or your own squad→channel logic if you build it (see § Integration contract) |

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against real
rollup files produced by migration-program-manager's and cost-optimization-sprint-planner's own smoke
tests.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Digest is empty or missing a whole rollup's items | Check the Rollup gaps section — a missing/unreadable rollup file is reported there, never silently treated as "nothing to report" |
| Every item is flagged stale | Check the handler's schedule actually runs migration-program-manager/cost-optimization-sprint-planner before this skill each cycle — a stale rollup file means the upstream skill didn't run recently, not a bug in this skill |
| A squad's Migration status or Cost optimization sub-section says "No items in this rollup for this squad" | Expected when that squad genuinely has nothing in one rollup — not an error; compare against that rollup's own full output if you want to confirm |
| Two items for the same service show different squads across sub-sections | Each rollup computed `squad` independently (different join mechanisms) — this is a real disagreement worth investigating in the producing skills, not something this skill reconciles |
