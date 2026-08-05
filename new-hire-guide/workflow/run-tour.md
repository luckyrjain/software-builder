---
workflow_version: 1.0
phase: run-tour
produces:
  - onboarding_tour
consumes:
  - new_hire
  - workspace_root
  - delivery_mode
---

# Run tour — resolve repos, invoke both skills, build the tour

## 1. Resolve the squad's repos via squad-map

Invoke **squad-map** over `workspace_root` using its own **auto-discover** input mode (its own
`SKILL.md` § Required inputs: "Auto-discover | 'Map squads for this workspace'") — this skill never
pre-filters the repo list, because filtering to the new hire's squad is exactly what this step is
finding out.

**Do not set `refresh: true`.** squad-map's own default (`refresh: false`) already "skip[s] re-query
when `SQUAD_MAP.md` exists and repo list unchanged" — reusing an existing, unstale `SQUAD_MAP.md` is
squad-map's own behavior, not new logic this skill needs to duplicate. If the caller explicitly asks for
a fresh mapping ("re-check ownership first"), pass `refresh: true` through unchanged.

squad-map's own live gates (Phase 0 MCP profile check, the `squad_path_segment` **HARD STOP** if
unconfigured) run exactly as they would for a direct squad-map invocation — this skill does not
pre-answer them (see [SKILL.md](../SKILL.md) § Workflow).

## 2. Filter `SQUAD_MAP.md` for the new hire's squad

Read squad-map's resulting `SQUAD_MAP.md` main table (`Repo | GitLab namespace | GitLab squad | Datadog
service | Datadog team | Confidence | Evidence`). A row matches when `new_hire.squad`, compared
**case-insensitively**, equals **either** the GitLab squad column **or** the Datadog team column — check
both, not just one, since a squad can be recorded correctly in only one lens (e.g. Datadog team tag
missing or LOW-confidence CODEOWNERS-only rows) and requiring both would under-match.

**Zero matches:** do not produce an empty tour. List the distinct squad names that actually appear in
`SQUAD_MAP.md`'s GitLab-squad and Datadog-team columns, and ask the user to confirm or correct
`new_hire.squad` — a typo or a squad-name variant (e.g. "Payments" vs. "payments-core") is far more
likely than a squad that genuinely owns zero repos yet. Do not proceed to step 3 until resolved or the
user explicitly confirms the squad has no repos yet (rare — record this in the tour instead of
attempting scope).

## 3. Invoke domain-comprehension scoped to the resolved repos

Invoke **domain-comprehension** with:

- `workspace_root` — unchanged, same workspace
- `delivery_mode` — `new_hire.delivery_mode` if the caller set one, else `QUICK` (default — a new hire
  wants fast orientation, not a multi-session engagement)
- `domain-config.yaml` `scope.seed_repos` — set to exactly the repo names matched in step 2 (per
  [domain-config-schema.md](../../domain-comprehension/reference/domain-config-schema.md) — `seed_repos`
  is "optional hints — agent still verifies," so domain-comprehension's own Session 0 census still runs
  normally, just filtered to this set)

domain-comprehension's own live gate (Session 0 step 11, "Scope & budget checkpoint... Ask user to
approve mechanical-analysis scope") runs exactly as it would for a direct invocation — this skill does
not pre-answer it.

If `workspace_root` already has a `manifest.yaml` from a prior, broader engagement, domain-comprehension
resolves its own mode per its own `RESUME`/`DELTA` rules — this skill does not override that; it only
supplies `scope.seed_repos`.

## 4. Build `ONBOARDING_TOUR.md`

Per [reference/tour-format.md](../reference/tour-format.md), using:

- `new_hire.name`, `new_hire.squad`, `new_hire.start_date`/`role` if given — welcome section
- The resolved repo list from step 2, each repo's one-line purpose from domain-comprehension's P0 census
  / `EXEC_SUMMARY.md`
- Squad ownership/contact evidence from `SQUAD_MAP.md`
- Links (not restated content) into `EXEC_SUMMARY.md` and the other domain-comprehension deliverables for
  anyone who wants more depth

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Onboarding tour | `ONBOARDING_TOUR.md` | Welcome section, repo list w/ purpose, squad contacts, links |
