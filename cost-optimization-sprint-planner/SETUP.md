# cost-optimization-sprint-planner — Setup

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` — a human is present for this flow
(same reasoning as `release-readiness-checker`, unlike `backlog-runner`), so ambient chat invocation is
intended. See [SKILL.md](SKILL.md) § "Why a gate policy AND a sweep policy" for the two pieces of new
logic this skill adds on top of k8s-overprovisioning-datadog's own analysis.

## Install

```bash
cd software-builder
make install-cost-optimization-sprint-planner
```

This chains `make install-k8s-overprovisioning install-squad-map` first — this skill has no rightsizing
logic of its own and its output is meaningless without k8s-overprovisioning-datadog installed and
configured. Restart Cursor so all three skills reload.

### Claude Code

`make install-cost-optimization-sprint-planner` above already installs this skill for Claude Code too
(default installs to both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-cost-optimization-sprint-planner
```

No restart needed. See [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/cost-optimization-sprint-planner.mdc` and
`.kiro/steering/cost-optimization-sprint-planner.md` point Cursor/Kiro at
`cost-optimization-sprint-planner/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| k8s-overprovisioning-datadog installed and configured | Its own prerequisites apply, including Datadog MCP — see [k8s-overprovisioning-datadog/SETUP.md](../k8s-overprovisioning-datadog/SETUP.md) |
| squad-map installed and configured | Optional — a candidate deployment without a `SQUAD_MAP.md`/`ownership.datadog.service_aliases` match still rolls up, joined as `squad: UNKNOWN` — see [squad-map/SETUP.md](../squad-map/SETUP.md) |
| Datadog MCP | Required directly by this skill too — the optional namespace pre-filter (`sweep_scope.namespace_prefilter`) runs its own waste-ranking queries, not delegated through k8s-overprovisioning-datadog |

No scripts of its own — unlike migration-program-manager, k8s-overprovisioning-datadog has no CLI to
wrap; this skill is pure markdown-workflow, like release-readiness-checker.

## Config

No config file of its own. `sweep_scope` and `cost_rate` are passed at invocation time — see
[workflow/inputs.md](workflow/inputs.md). There is no default `cost_rate` (see
[SKILL.md](SKILL.md) § Required inputs) — an org-specific $/core and $/GiB rate is an operational
decision this skill won't guess; pick your own real rate (or your platform team's) before running a
sweep, or every deployment without CCM cost data will report `monthly_savings_total: 0` rather than a
fabricated figure.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against ≥2 real
deployments.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Cost-rate question repeats per deployment | Something is re-deriving it mid-sweep instead of resolving it once at Run sweep § 0 — see [reference/gate-policy.md § Cost-rate gate](reference/gate-policy.md#cost-rate-gate-resolved-once-sweep-wide-before-the-loop-starts) |
| A deployment always joins as `squad: UNKNOWN` despite a real `SQUAD_MAP.md` | Check the graph's `metadata.service` matches `SQUAD_MAP.md`'s `Datadog service` column exactly (exact-match, no fuzzy matching — `metadata.service` can legitimately differ from the deployment's own `kube_deployment` tag), or supply `squad_map_config_path` (see `workflow/inputs.md`) so the `ownership.datadog.service_aliases` reverse lookup can run at all — without it, that fallback is skipped entirely |
| Every deployment shows `$0` monthly savings | Check `cost_rate` was actually supplied — a missing `cost_rate` is a HARD STOP at Inputs, not a silent `$0` default; if `cost_rate` was supplied and every deployment is still `$0`, check whether they're all genuinely `KEEP_CONFIGURATION` (a real, valid outcome) before assuming a bug |
| Sweep stops after only a few deployments | Check `stopped_reason` in the report header — `MAX_DEPLOYMENTS_REACHED`/`DEADLINE_REACHED`/`TOKEN_BUDGET_EXHAUSTED` are expected circuit breakers, not errors; re-run with a higher `max_deployments_per_run` or no `deadline` to cover the rest |
