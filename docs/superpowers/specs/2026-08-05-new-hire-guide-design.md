# new-hire-guide: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #5 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P1, "New-Hire Guide — domain-comprehension + squad-map → personalized onboarding tour for a new
engineer's assigned repos/services. Needs an org-chart or team-assignment input (who's joining, which
squad) that doesn't exist in either skill today — that's the new part."

## Problem

A new engineer joins a squad and needs a fast, curated orientation to *their* repos/services — not the
full multi-session domain-comprehension pipeline over the whole org, and not squad-map's ownership table
on its own (useful for "who owns X," not for "what does my new squad's stuff actually do"). Today someone
has to manually figure out which repos the new hire's squad owns, then hand-run domain-comprehension
scoped to just those.

## What's already there vs. genuinely new — researched, not assumed

Both underlying skills already do almost everything this needs, once you know *which repos* to point them
at:

| Capability | Exists today? |
|---|---|
| Map a squad name to the repos it owns | **Partially.** squad-map is repo-first (`SQUAD_MAP.md`'s main table is `Repo → GitLab squad, Datadog team`), not squad-first — there's no "given a squad, list its repos" input mode. But the *data* to answer that (once `SQUAD_MAP.md` exists for the workspace) supports filtering the existing table by squad column — no new squad-map logic needed, just a read of its existing output. |
| Scope domain-comprehension to a specific repo subset | **Yes.** `domain-config.yaml`'s `scope.seed_repos` ([domain-config-schema.md](../../domain-comprehension/reference/domain-config-schema.md) line 18) already exists exactly for this — Session 0 step 3 ("Scope filter") already applies it. |
| Squad enrichment during a comprehension run | **Yes**, already delegated to squad-map at Session 0b ([session-0b.md](../../domain-comprehension/workflow/session-0b.md)) — no new integration needed. |
| A roster / "who's joining, which squad" input concept | **No — confirmed absent anywhere in this repo.** Exhaustive grep for roster/org-chart/new-hire/team-assignment concepts across the whole repo turns up nothing outside this roadmap doc itself. **This is the one genuinely new thing.** |
| A curated "onboarding tour" output distinct from the full deliverable set | **No** — `EXEC_SUMMARY.md` etc. are written for a domain engagement, not a first-week reading list for one person. **Genuinely new**, but thin: a packaging/selection step over deliverables that already exist. |

## Approach

`new-hire-guide` is a **thin composition wrapper** — same spirit as `who-owns-x-bot` (item #1: "no new
logic, [wrapped skill] already produces exactly this answer"), not a heavy orchestration layer like
`pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`. It:

1. Takes one genuinely new input: `new_hire` (name, squad, optional start date / role) — the "org-chart or
   team-assignment input" the roadmap calls out. Nothing else about it is new.
2. Resolves the new hire's squad to a repo list: reuse an existing `SQUAD_MAP.md` at the target
   `workspace_root` if one is fresh enough (per squad-map's own staleness convention — see
   [SETUP.md](../../new-hire-guide/SETUP.md)); otherwise invoke **squad-map** fresh over the workspace.
   Filter its main table for rows where **either** the GitLab squad **or** the Datadog team column matches
   the new hire's squad name (case-insensitive) — a squad can appear under a differently-cased or
   differently-worded name in either source; matching only one column would silently miss repos where
   only the other lens recorded that squad.
3. **Zero-match handling:** if no `SQUAD_MAP.md` row matches the given squad name, this is **not** a
   silent empty tour — report the squad names that *do* exist in `SQUAD_MAP.md` and ask the user to
   confirm/correct the squad name (typo is far more likely than "this squad genuinely owns nothing yet").
4. Invokes **domain-comprehension** with `delivery_mode: QUICK` by default (a new hire wants fast
   orientation, not a multi-session engagement — same default-to-QUICK reasoning domain-comprehension
   itself already applies for first-time engagements) and `domain-config.yaml` `scope.seed_repos` set to
   the resolved repo list. `FULL` is available if the user asks for deeper detail.
5. **Both wrapped skills' own live gates run normally, unscripted** — this skill does **not** get a
   `pr-gatekeeper`-style gate-policy file. Unlike `pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`,
   which wrap a webhook- or schedule-triggered flow with no human present to answer a live question,
   `new-hire-guide` is invoked by a person (onboarding coordinator, buddy, manager) who is present in the
   conversation and can answer domain-comprehension's Session 0 scope/budget checkpoint and squad-map's
   `squad_path_segment` HARD STOP exactly as they would answer them running either skill directly. Scripting
   deterministic answers here would remove a human's real choice for no reason — there's no unattended
   context that requires it, unlike the other three wrappers.
6. Packages the result as **`ONBOARDING_TOUR.md`** (new deliverable) — this skill's one genuinely new
   output: a welcome section naming the new hire and squad, the resolved repo list with each repo's
   one-line purpose (from domain-comprehension's P0 census / `EXEC_SUMMARY.md`), squad ownership/contacts
   (from `SQUAD_MAP.md`), and links into the full domain-comprehension deliverables for anyone who wants
   more depth. It does not duplicate `EXEC_SUMMARY.md`'s content, only curates and links to it.

## Non-goals (explicitly out of scope)

- **No new squad-map logic.** Squad-first filtering is done by this skill reading `SQUAD_MAP.md`'s
  existing output, not by adding a new query mode to squad-map itself (contrast with item #6, which *does*
  need a new domain-comprehension mode because no existing mode does proposal-vs-manifest comparison at
  all — here, filtering an existing table by column is not new logic).
- **No gate-policy override file** — see point 5 above. If a future item needs new-hire-guide to run
  unattended (e.g. auto-triggered from an HRIS webhook on a new hire's start date), that's a materially
  different trust/trigger decision left for a future extension, the same way pr-gatekeeper deferred
  auto-fix hand-off.
- **No roster data source integration** (Workday, BambooHR, etc.) — `new_hire` is a **direct input to this
  skill's invocation** (typed by the person invoking it), not fetched from an external HRIS. Building a
  live roster-system integration is out of scope; this only defines the input's shape.
- **No modification to domain-comprehension or squad-map's own internals** — pure composition, exactly
  like `who-owns-x-bot`/`incident-triage-agent`.

## Interface contract

**Input:**

| Field | Required | Notes |
|-------|----------|-------|
| `new_hire.name` | Yes | For the tour's welcome section only — not used in any lookup |
| `new_hire.squad` | Yes | Matched case-insensitively against `SQUAD_MAP.md`'s GitLab-squad **or** Datadog-team column |
| `workspace_root` | Yes | Same resolution as domain-comprehension/squad-map's own `workspace_root` input |
| `delivery_mode` | No | Default `QUICK`; `FULL` available on request — passed through to domain-comprehension unchanged |

**Output:** `ONBOARDING_TOUR.md` at `workspace_root`, plus whatever domain-comprehension/squad-map
deliverables their own QUICK/FULL run already produces (unchanged, not duplicated).

## Acceptance criteria

- `new-hire-guide/SKILL.md` exists, ≤ 180 lines. **`disable-model-invocation` is NOT set** — this skill
  ambiently triggers on new-hire-onboarding-shaped requests, which don't collide with domain-comprehension's
  or squad-map's own trigger phrases (confirmed: neither's `description` frontmatter mentions onboarding
  or new-hire language).
- Given a new hire's squad matches N rows in `SQUAD_MAP.md` (by either column), domain-comprehension runs
  scoped to exactly those N repos via `seed_repos` — not the whole workspace.
- Given the squad name matches zero rows, the run stops and asks for confirmation, listing the squads that
  do exist — never produces an empty/silent tour.
- Given `SQUAD_MAP.md` doesn't exist yet at `workspace_root`, squad-map is invoked fresh, including its own
  live `squad_path_segment` HARD STOP if unconfigured — this skill does not pre-answer it.
- `ONBOARDING_TOUR.md` never restates content that already lives in `EXEC_SUMMARY.md`/`SQUAD_MAP.md`
  wholesale — it curates and links, consistent with domain-comprehension's own "markdown deliverables,
  not duplicated" convention.
- `make lint-new-hire-guide` and `make lint-framework` pass; skill wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md` (with an explicit disambiguation row —
  see below), `cross-skill-escalation.md`, `prompt-injection.md`, `phase-glossary.md` (this skill *does*
  introduce a new artifact/checkpoint shape unlike backlog-runner, so — unlike backlog-runner — it does
  **not** inherit an exemption), `CHANGELOG.md`.

## Routing disambiguation (for skill-routing.md)

| Request shape | Routes to |
|---|---|
| "Onboard Jane, she's joining the payments squad" / "new-hire tour for X" | **new-hire-guide** |
| "Who owns the payments service?" | **squad-map** (unchanged) |
| "Map the payments domain" / full comprehension | **domain-comprehension** (unchanged) |

## Implementation plan

1. `new-hire-guide/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `workflow/inputs.md` (parse `new_hire`, `workspace_root`, `delivery_mode`; untrusted-content note — the
   `new_hire.name`/`squad` fields are caller-supplied data, not instructions, same guard class as every
   other wrapper) and `workflow/run-tour.md` (resolve squad → repos, invoke squad-map if needed, invoke
   domain-comprehension scoped, build `ONBOARDING_TOUR.md`).
3. `reference/phase-index.md`, `lazy-load-index.md`, `smoke-test.md`, `tour-format.md` (normative
   `ONBOARDING_TOUR.md` structure + squad-column-matching rule + zero-match handling).
4. `.cursor/rules/new-hire-guide.mdc`, `.kiro/steering/new-hire-guide.md`.
5. `Makefile`: `install-new-hire-guide` (chains `install-domain-comprehension install-squad-map`),
   `install-claude-new-hire-guide`, `lint-new-hire-guide`, added to `.PHONY`/`lint:` deps and to
   `lint-framework`'s 4 hardcoded per-skill loops from the start.
6. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the established pattern.
7. `docs/skill-framework/shared/skill-routing.md` (routing table row + disambiguation rows above),
   `cross-skill-escalation.md`, `prompt-injection.md`, `phase-glossary.md` (new artifact:
   `ONBOARDING_TOUR.md` — glossary entry, since this skill is not exempt the way backlog-runner is).
8. Root `CHANGELOG.md` + `new-hire-guide/CHANGELOG.md`: initial release entry.
9. `make lint` green; deep review pass(es), fixing to 0 issues each round; commit.
