---
workflow_version: 1.0
phase: run-tour
produces:
  - onboarding_tour
  - tour_output_dir
consumes:
  - new_hire
  - workspace_root
  - delivery_mode
---

# Run tour — resolve repos, invoke both skills, build the tour

Resolve `tour_output_dir` from inputs (default `{workspace_root}/../onboarding-tours/<slug>/` per
[inputs.md](inputs.md)). Create the directory if missing. **Write `ONBOARDING_TOUR.md` only under
`tour_output_dir`** — never inside an individual application repo. domain-comprehension and squad-map
deliverables remain at `workspace_root` unchanged.

## 1. Resolve the squad's repos via squad-map

Invoke **squad-map** over `workspace_root` using its own **auto-discover** input mode (its own
`SKILL.md` § Required inputs: "Auto-discover | 'Map squads for this workspace'") — this skill never
pre-filters the repo list, because filtering to the new hire's squad is exactly what this step is
finding out.

**Do not set `refresh: true`.** squad-map's own default (`refresh: false`) already "skip[s] re-query
when `SQUAD_MAP.md` exists and repo list unchanged" — reusing an existing, unstale `SQUAD_MAP.md` is
squad-map's own behavior, not new logic this skill needs to duplicate. If the caller explicitly asks for
a fresh mapping ("re-check ownership first"), pass `refresh: true` through unchanged. **Known limitation:**
squad-map's own staleness skip is keyed on the repo census being unchanged, not on GitLab-group/Datadog-
team reassignment — a repo whose team tag changed without the repo list itself changing could be missed
by a reused `SQUAD_MAP.md`. If a new hire's expected repo doesn't appear, suggest `refresh: true` before
concluding the squad owns nothing.

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

## 3. Invoke domain-comprehension — unscoped, never narrowed via `seed_repos`

Invoke **domain-comprehension** over the same `workspace_root`, with `delivery_mode` —
`new_hire.delivery_mode` if the caller set one, else `QUICK` (default — a new hire wants fast
orientation, not a multi-session engagement) — **exactly as a direct invocation would run it**, with no
`domain-config.yaml` `scope.seed_repos` override and no other scope narrowing.

**Do not narrow domain-comprehension's own census to the matched repos, even though `seed_repos` exists
for exactly this kind of purpose.** This was the original design and was reverted: `seed_repos` narrows
Session 0's own repo census, and domain-comprehension's Session 0b squad-map enrichment is a **mandatory,
non-optional subroutine** (see [cross-skill-escalation.md](../../docs/skill-framework/shared/cross-skill-escalation.md)
§ 1 — "Session 0b (subroutine, not optional)") that passes that narrowed census straight to squad-map as
its own `repos` input, per squad-map's documented [Embedded invocation (domain-comprehension)](../../squad-map/workflow/inputs.md#embedded-invocation-domain-comprehension)
contract. squad-map's own idempotency rule ([phase-1.md](../../squad-map/workflow/phase-1.md) §
"Idempotency & partial runs" — "**Scope shrink:** when the in-scope repo census is smaller than the prior
run..., move rows for repos no longer in scope to `SQUAD_MAP.md` § Out of scope (archived)" — and this
holds for **both** `refresh: true` and `refresh: false`) then archives every other squad's rows out of the
**same shared `SQUAD_MAP.md`** this skill just read in step 1 — silently corrupting a file every other
squad-map/who-owns-x-bot/pr-review caller depends on, for the sake of one onboarding tour. Curating to the
new hire's repos happens entirely in step 4 below, on domain-comprehension's own unscoped output — never
by narrowing what domain-comprehension itself analyzes or reports to squad-map.

If `workspace_root` already has a `manifest.yaml`, domain-comprehension resolves its own mode per its own
`RESUME`/`DELTA` rules, same as any direct invocation — this skill neither forces nor blocks that.

domain-comprehension's own live gate (Session 0 step 11, "Scope & budget checkpoint... Ask user to
approve mechanical-analysis scope," which only fires ahead of P0.5 — not guaranteed on every
`delivery_mode`, e.g. `QUICK`'s own definition stops before P0.5) runs exactly as it would for a direct
invocation, whenever domain-comprehension's own rules would trigger it — this skill does not pre-answer
it and does not need to, since nothing about this invocation differs from a direct one.

## 4. Build `ONBOARDING_TOUR.md` — curate domain-comprehension's full output down to the matched repos

Per [reference/tour-format.md](../reference/tour-format.md), using:

- `new_hire.name`, `new_hire.squad`, `new_hire.start_date`/`role` if given — welcome section
- **Filter** domain-comprehension's per-repo P0 census / `EXEC_SUMMARY.md` down to just the repo list
  matched in step 2 — domain-comprehension itself analyzed the whole workspace; this skill's curation
  step is what narrows the *tour*, not domain-comprehension's own scope or deliverables
- Squad ownership/contact evidence from `SQUAD_MAP.md`, **including cross-checking `SQUAD_MAP.md` §
  Conflicts for any matched repo** — a conflicted row (GitLab squad ≠ Datadog team) must be surfaced
  plainly in the tour per [tour-format.md](../reference/tour-format.md)'s "never resolved on the caller's
  behalf" rule, not silently picked one way
- Links (not restated content) into `EXEC_SUMMARY.md` and the other domain-comprehension deliverables for
  anyone who wants more depth — those deliverables cover the whole workspace, not just this tour's repos;
  say so rather than implying they're pre-filtered

## Required outputs

| Output | Location | Required fields |
|--------|----------|-----------------|
| Onboarding tour | `<tour_output_dir>/ONBOARDING_TOUR.md` | Welcome section, repo list w/ purpose, squad contacts, links |
