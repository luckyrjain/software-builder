# new-hire-guide

**Personalized onboarding tour** for a new engineer joining a squad. A thin composition wrapper around
**squad-map** (resolves the squad's repos) and **domain-comprehension** (scoped comprehension over just
those repos) — no ownership or comprehension logic of its own, just the roster input and the curated
`ONBOARDING_TOUR.md` packaging.

Unlike `who-owns-x-bot`/`pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`, this skill does **not**
set `disable-model-invocation` — it's meant to auto-invoke from ambient chat ("onboard Jane, she's joining
payments") since a human is always present for this flow, unlike those four unattended/webhook wrappers.

## What it does

1. **Takes a `new_hire`** — name + squad (the "org-chart/team-assignment input" neither underlying skill
   has).
2. **Resolves the squad's repos** — reads squad-map's own `SQUAD_MAP.md` (auto-discovering it fresh if
   none exists), filtering for rows where the given squad matches the GitLab-squad or Datadog-team column.
3. **Runs domain-comprehension scoped to just those repos** — `QUICK` mode by default, via
   `domain-config.yaml`'s existing `scope.seed_repos` field (no new domain-comprehension logic).
4. **Both wrapped skills' own live questions surface normally** — this skill never scripts an answer to
   squad-map's `squad_path_segment` HARD STOP or domain-comprehension's Session 0 scope/budget checkpoint;
   the person who invoked this skill answers them, same as running either skill directly.
5. **Writes `ONBOARDING_TOUR.md`** — welcome section, resolved repo list with one-line purpose, squad
   contacts, links into the full domain-comprehension deliverables. Curates and links; never restates.

## When to use

| Use new-hire-guide | Use instead |
|---------------------|--------------|
| "Onboard Jane, she's joining payments" | "Who owns the payments service?" → **squad-map** directly |
| First-week orientation scoped to one person's repos | Full org-wide domain map → **domain-comprehension** directly |

## Invocation examples

```
new_hire: {name: Jane, squad: payments}, workspace_root: ./services
```

If `payments` matches zero rows in `SQUAD_MAP.md`, you're asked to confirm the squad name against the
list of squads that actually appear there — never a silent empty tour.

## What you get

`ONBOARDING_TOUR.md` at `workspace_root` — format spec: [reference/tour-format.md](reference/tour-format.md).
Plus domain-comprehension's and squad-map's own normal deliverables (`EXEC_SUMMARY.md`, `SQUAD_MAP.md`,
etc.) from the scoped/auto-discover runs — those are the wrapped skills' own artifacts.

## Install

```bash
cd ai-skills
make install-new-hire-guide
```

Restart Cursor. Requires **domain-comprehension** and **squad-map** installed too (the make target chains
both automatically). MCP setup is each wrapped skill's own — see
[domain-comprehension/SETUP.md](../domain-comprehension/SETUP.md) and
[squad-map/SETUP.md](../squad-map/SETUP.md).

## Related skills

- **squad-map** — does the actual squad-to-repo resolution; this skill only reads its output
- **domain-comprehension** — does the actual comprehension analysis; this skill only scopes and curates it
- **who-owns-x-bot** — a different single-shot wrapper around squad-map, for automated no-follow-up
  callers, not an onboarding tour

Agent instructions: [SKILL.md](SKILL.md).
