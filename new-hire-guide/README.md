# new-hire-guide

**Personalized onboarding tour** for a new engineer joining a squad. A thin composition wrapper around
**squad-map** (resolves the squad's repos) and **domain-comprehension** (run unscoped, curated down to
just those repos afterward — see below for why it's *not* scoped via domain-comprehension's own
`seed_repos` field) — no ownership or comprehension logic of its own, just the roster input, the
squad-to-repos resolution, and the curated `ONBOARDING_TOUR.md` packaging.

Unlike `who-owns-x-bot`/`pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`, this skill does **not**
set `disable-model-invocation` — it's meant to auto-invoke from ambient chat ("onboard Jane, she's joining
payments") since a human is always present for this flow, unlike those four unattended/webhook wrappers.

## What it does

1. **Takes a `new_hire`** — name + squad (the "org-chart/team-assignment input" neither underlying skill
   has), plus optional `start_date` and `role` rendered into the welcome section when given (never used in
   any lookup or scope decision).
2. **Resolves the squad's repos** — reads squad-map's own `SQUAD_MAP.md` (auto-discovering it fresh if
   none exists), filtering for rows where the given squad matches the GitLab-squad or Datadog-team column.
3. **Runs domain-comprehension unscoped** — `QUICK` mode by default, exactly as a direct invocation would
   run it, **no `domain-config.yaml scope.seed_repos` override**. This was tried and reverted: narrowing
   domain-comprehension's own census cascades into its mandatory Session 0b squad-map delegation, which
   would trigger squad-map's own scope-shrink archival and silently corrupt the **shared**
   `SQUAD_MAP.md` other squads/skills depend on. See [SKILL.md](SKILL.md) and
   [workflow/run-tour.md](workflow/run-tour.md) § 3 for the full explanation.
4. **Both wrapped skills' own live questions surface normally, whenever their own rules would trigger
   them** — this skill never scripts an answer to squad-map's `squad_path_segment` HARD STOP or
   domain-comprehension's Session 0 scope/budget checkpoint; the person who invoked this skill answers
   them, same as running either skill directly, because nothing about the invocation differs from a direct
   one.
5. **Curates `ONBOARDING_TOUR.md`** from domain-comprehension's full output — welcome section, the matched
   repo list with one-line purpose (filtered down from the whole-workspace census), squad contacts, links
   into the full domain-comprehension deliverables. Curates and links; never restates.

## When to use

new-hire-guide is for "Onboard Jane, she's joining payments" — a first-week orientation curated to one
**named** person's assigned repos. "Who owns the payments service?" with no person named routes to
**squad-map** directly, and "help me onboard to the payments subsystem" with no person named routes to
**domain-comprehension** directly — that phrase genuinely overlaps with domain-comprehension's own
"subsystem onboarding" trigger, and whether a person is named is the disambiguator. This skill never
computes squad ownership or comprehension logic itself; both stay squad-map's and domain-comprehension's
own. Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Invocation examples

```
new_hire: {name: Jane, squad: payments}, workspace_root: ./services
```

If `payments` matches zero rows in `SQUAD_MAP.md`, you're asked to confirm the squad name against the
list of squads that actually appear there — never a silent empty tour.

## What you get

`ONBOARDING_TOUR.md` at `workspace_root` — format spec: [reference/tour-format.md](reference/tour-format.md).
Plus domain-comprehension's and squad-map's own normal, **unscoped, whole-workspace** deliverables
(`EXEC_SUMMARY.md`, `SQUAD_MAP.md`, etc.) — those are the wrapped skills' own artifacts, not narrowed or
duplicated by this skill.

## Install

```bash
cd software-builder
make install-new-hire-guide
```

Restart Cursor. Requires **domain-comprehension** and **squad-map** installed too (the make target chains
both automatically). MCP setup is each wrapped skill's own — see
[domain-comprehension/SETUP.md](../domain-comprehension/SETUP.md) and
[squad-map/SETUP.md](../squad-map/SETUP.md).

## Related skills

- **squad-map** — does the actual squad-to-repo resolution; this skill only reads its output
- **domain-comprehension** — does the actual comprehension analysis, run unscoped; this skill only curates its output down to the new hire's repos
- **who-owns-x-bot** — a different single-shot wrapper around squad-map, for automated no-follow-up
  callers, not an onboarding tour

Agent instructions: [SKILL.md](SKILL.md).
