# new-hire-guide — Setup

## Ambient discovery is intended

This skill deliberately does **not** set `disable-model-invocation` in its frontmatter — the agent can
auto-apply it when you describe a new-hire onboarding request in natural language ("onboard Jane, she's
joining payments"), as well as an explicit invocation. This differs from `who-owns-x-bot` /
`pr-gatekeeper` / `incident-triage-agent` / `backlog-runner`, all of which disable ambient invocation
because they wrap unattended/webhook triggers with no human present to answer a live question — a human
is always present for this flow.

## Install

```bash
cd software-builder
make install-new-hire-guide
```

This chains `make install-domain-comprehension install-squad-map` first — new-hire-guide has no
comprehension or ownership logic of its own and is useless without both installed alongside it. Restart
Cursor so all three skills reload.

### Claude Code

`make install-new-hire-guide` above already installs this skill for Claude Code too (default installs to
both editors). For Claude Code **only**:

```bash
cd software-builder
make install-claude-new-hire-guide
```

No restart needed — a new Claude Code session picks it up. See
[claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/new-hire-guide.mdc` and
`.kiro/steering/new-hire-guide.md` point Cursor/Kiro at `new-hire-guide/SKILL.md` without an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| domain-comprehension installed and configured | Its own prerequisites apply — see [domain-comprehension/SETUP.md](../domain-comprehension/SETUP.md) (Node ≥ 22, understand-anything recommended) |
| squad-map installed and configured | Its own prerequisites apply — see [squad-map/SETUP.md](../squad-map/SETUP.md) (GitLab/Datadog MCP, or CODEOWNERS fallback) |
| Target workspace | Same `workspace_root` both wrapped skills would use — single repo, monorepo, or sibling git repos |

No MCP of its own — every MCP requirement is inherited from the two wrapped skills.

## Config

No config file of its own. `new_hire` is passed at invocation time (name + squad, not stored). All
workspace-level config (`domain-config.yaml`'s `ownership:`/`scope:` blocks, `squad-map-config.yaml`'s
`squad_path_segment`) is exactly whatever domain-comprehension/squad-map already need — configure those
per each skill's own `SETUP.md`, nothing new to configure here.

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocation in [reference/smoke-test.md](reference/smoke-test.md) against a
workspace where squad-map already resolves at least two repos to the same squad.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `ONBOARDING_TOUR.md` § Your repos is empty with no explanation | Should never happen — see [workflow/run-tour.md](workflow/run-tour.md) § 2 zero-match handling; file a bug if it does |
| Squad name matches zero rows | Not a bug — confirm the squad name against the list you're shown; check `SQUAD_MAP.md` directly if unsure it exists at all |
| `ONBOARDING_TOUR.md`'s § Your repos lists repos outside the new hire's squad | Bug — check `workflow/run-tour.md` § 4's curation step actually filtered domain-comprehension's output to the step-2 matched list; domain-comprehension's own run is **always unscoped** by design, so this must be caught at curation, not by narrowing domain-comprehension itself |
| `SQUAD_MAP.md` is missing rows for squads other than the new hire's after a run | **Serious — this is the scope-shrink regression** [workflow/run-tour.md](workflow/run-tour.md) § 3 exists to prevent; check no `domain-config.yaml scope.seed_repos` override was reintroduced anywhere in this skill's invocation of domain-comprehension |
| Skill doesn't fire on ambient chat | Confirm `disable-model-invocation` is **not** set in `SKILL.md` frontmatter (unlike the other four wrappers, it should be absent here) |
| Every repo purpose is UNKNOWN | Check domain-comprehension itself resolves those repos when asked directly — see [domain-comprehension/SETUP.md § Troubleshooting](../domain-comprehension/SETUP.md#troubleshooting) if present, else its smoke test |
