# weekly-squad-digest: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #11 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P2, "Weekly Squad Digest — scheduled per-squad Slack post combining k8s-overprovisioning-datadog
(overprovisioned services), mysql-to-postgres-sql (pending migrations), and squad-map (routing to the
right channel). Shares the aggregation infrastructure #8 and #10 would need — worth building after those
two land rather than before, so the aggregation layer is designed once, not three times." Implements the
consumer side of [org-rollup-schema.md](../../skill-framework/shared/org-rollup-schema.md), designed in
Phase 4, now producing side for both adapters via
[migration-program-manager](../../../migration-program-manager/SKILL.md) (item #8) and
[cost-optimization-sprint-planner](../../../cost-optimization-sprint-planner/SKILL.md) (item #10).

## Problem

Both rollup skills already write a squad-grouped `org_rollup_item` JSON file — but nobody has one
combined view across both, and nobody gets it without remembering to run two separate skills.

## Correcting two claims before designing against them

Two sources make a claim this skill's design research found is **not backed by any real mechanism**:

1. **The roadmap item's own wording** — "scheduled per-squad Slack post... squad-map (routing to the
   right channel)" — implies squad-map has a squad→channel routing mechanism.
2. **[org-rollup-aggregation-layer-design.md](2026-08-05-org-rollup-aggregation-layer-design.md)** (Phase
   4, written before this skill existed) goes further, stating as settled fact: *"#11 Weekly Squad Digest
   groups both #8's and #10's rollup items by squad, routes to the channel squad-map's own `Datadog
   team`/`GitLab squad` implies (that routing convention is squad-map's own, reused unchanged, same
   pattern as who-owns-x-bot/incident-triage-agent's ownership lookups)."**

**Neither claim holds up.** `squad-map/templates/SQUAD_MAP.md`'s columns are `Repo | GitLab namespace |
GitLab squad | Datadog service | Datadog team | Confidence | Evidence` — two ownership **name** fields,
no channel, contact, webhook, or any delivery-routing column anywhere in `SQUAD_MAP.md`,
`config-schema.md`, or `squad-mapping.md`. squad-map's own `SKILL.md` states it produces "no Jira/Slack/
canvas write-back" at all. The two cited precedents don't establish a squad→channel table either:
who-owns-x-bot's `SETUP.md` has one hardcoded `fallback_contact` string, not a per-squad map;
incident-triage-agent's `SETUP.md` has one configured "notification target," delivered by an external
webhook handler, explicitly *"this skill's own output is just text, the handler does the actual
delivery."* **No skill in this repo has ever implemented true per-squad channel delivery** — every
`disable-model-invocation: true` skill in this repo (backlog-runner, incident-triage-agent, who-owns-x-bot)
produces one markdown/text artifact and hands delivery to an external handler documented in that skill's
own `SETUP.md`, never a live Slack API call the skill makes itself, and never a per-recipient fan-out the
skill computes.

**This design follows the actually-established pattern, not the unbacked claim:** produce **one**
squad-grouped markdown digest (mirroring migration-program-manager's/cost-optimization-sprint-planner's
own per-squad report sectioning), with per-squad-channel delivery left to an external handler this
skill's `SETUP.md` documents as an integration point — not built by this skill, and not assumed to already
exist in squad-map.

## What's already there vs. genuinely new — researched, not assumed

| Capability | Exists today? |
|---|---|
| `migration_program_rollup.json` — per-item `service, squad, squad_confidence, source_skill, metric_type, status, priority, value, evidence_ref, last_updated, staleness_days` | **Yes** — migration-program-manager, unchanged. `staleness_days` is that skill's own schema extension, not part of the shared base shape |
| `cost_optimization_sprint_rollup.json` — same base 10 fields, `metric_type: k8s_waste`, no `staleness_days` equivalent | **Yes** — cost-optimization-sprint-planner, unchanged |
| Grouping `org_rollup_item`s by squad | **Yes, schema-specified** — [org-rollup-schema.md § 5](../../skill-framework/shared/org-rollup-schema.md#5-grouping-consuming-skills-own-their-own-ranking) — but explicitly leaves ranking/sorting within a squad to each consumer |
| Reading **two already-computed rollup files** and combining them without re-deriving `squad`/`squad_confidence`/`status` | **No** — confirmed the first skill in the repo to do this; migration-program-manager and cost-optimization-sprint-planner both *produce* a rollup for a future consumer, neither *consumes* one |
| A squad→channel delivery mechanism | **No** — see § Correcting two claims above; not built here either, left to an external handler |
| Scheduled, `disable-model-invocation: true`, scope-only required inputs (no schedule config inside the skill) | **Precedent exists** — backlog-runner's exact pattern, reused not reinvented |

## Approach

`weekly-squad-digest` is a **pure read-only consumer of two already-computed rollup files** — it never
invokes migration-program-manager, cost-optimization-sprint-planner, or squad-map live, the same
never-invoke-live principle migration-program-manager itself established (see its own SKILL.md § "Why no
gate policy"):

1. Takes a `rollup_manifest` — `{migration_rollup_path?, cost_rollup_path?}`, **HARD STOP if neither is
   set** (same OR-condition pattern cost-optimization-sprint-planner's `sweep_scope` already uses).
   Either path missing on disk is a gap, not a HARD STOP for the other — reported honestly, per
   migration-program-manager's own "one workspace's gap never blocks the others" precedent.
2. Reads both files as flat `org_rollup_item` arrays. **Never re-derives `squad`/`squad_confidence`** —
   both are already computed by the producing skill; this skill only groups and renders.
3. Groups by `squad`; `UNKNOWN` squad group always last (same convention as both producing skills).
   **Within a squad, splits by `metric_type`** (`pg_migration_gate` / `k8s_waste`) into two
   sub-sections — their `value` shapes are structurally different and not directly comparable (a gate
   status vs. a dollar figure), so this skill never invents a combined cross-metric ranking or score;
   each sub-section keeps its own producing skill's own sort order (migration: blocked → stalled, ranked
   by `staleness_days` descending within that bucket → in_progress → done; cost:
   `monthly_savings_total` descending) rather than reinventing one.
4. Computes each item's **staleness**, preferring migration's own `staleness_days` field when present
   (key exists, regardless of value — `staleness_days: 0` still counts) since it genuinely varies per
   service, falling back to a `last_updated`-derived age only when that key is absent; cost items (no
   `staleness_days` equivalent) always use a `last_updated`-derived age. An item past
   `staleness_warning_days` (optional, default 14) is flagged with a note to re-run the producing
   skill — worded differently depending on which source computed it, since `last_updated` is stamped at
   aggregation-run time (not per-service) for migration items while `staleness_days` genuinely is. This is
   display-only, never a HARD STOP or a decision gate — unlike migration-program-manager's
   `staleness_threshold_days` (which changes a computed `status`), this skill never recomputes anyone's
   `status`, so a sensible default is safe here rather than an operational decision this skill can't
   guess.
5. Writes **`WEEKLY_SQUAD_DIGEST.md`** — the terminal artifact in this rollup chain; no further JSON
   output, since nothing downstream is documented as consuming a third rollup shape.

## Non-goals (explicitly out of scope)

- **No per-squad channel delivery.** See § Correcting two claims. `SETUP.md` documents this skill's
  markdown output as the integration point for an external handler to deliver per-squad, the same way
  backlog-runner's morning summary and incident-triage-agent's triage doc both work — never a live Slack
  API call this skill makes itself.
- **No live invocation of migration-program-manager, cost-optimization-sprint-planner, or squad-map.**
  A missing/stale rollup file is reported as a gap; this skill never triggers a fresh run to fill it.
- **No cross-metric ranking or combined score.** `pg_migration_gate` and `k8s_waste` items are rendered
  in separate sub-sections per squad, never merged into one ranked list — their `value` shapes aren't
  comparable, and inventing a blended score would be exactly the kind of new analysis logic the roadmap
  item's own text says this skill should NOT add ("shares the aggregation infrastructure... the new part
  is [not] new analysis logic").
- **No schedule configuration inside the skill.** Same as backlog-runner: the actual cron/trigger lives
  in an external handler documented in `SETUP.md`; this skill's own required inputs are scope only
  (which rollup files to read), never a schedule expression.
- **No live scheduling infrastructure** — same "agent instructions, not infrastructure" boundary as every
  other item.

## Interface contract

**Input:**

| Field | Required | Notes |
|-------|----------|-------|
| `rollup_manifest` | Yes | `{migration_rollup_path?, cost_rollup_path?}` — **HARD STOP if neither is set** |
| `staleness_warning_days` | No | Default 14 — display-only, never a status-changing gate |

**Output:** `WEEKLY_SQUAD_DIGEST.md` — see
[reference/report-format.md](../../../weekly-squad-digest/reference/report-format.md).

## Acceptance criteria

- `weekly-squad-digest/SKILL.md` exists, ≤ 180 lines.
- Given both rollup paths, every item from both files appears in the digest, grouped by squad then by
  `metric_type` — none silently dropped.
- Given only one rollup path, the digest still renders — the other rollup's absence is a reported gap,
  not a HARD STOP for the whole run.
- `squad`/`squad_confidence`/`status`/`priority` are surfaced exactly as each producing skill computed
  them — never re-derived, re-labeled, or re-scored.
- An item past `staleness_warning_days` is flagged with its age and a pointer to re-run the producing
  skill — never silently presented as fresh.
- `disable-model-invocation: true` set, same as backlog-runner — never auto-triggers from ambient chat.
- `make lint-weekly-squad-digest` and `make lint-framework` pass; skill wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `cross-skill-escalation.md`,
  `prompt-injection.md`, `phase-glossary.md`, `CHANGELOG.md`.

## Implementation plan

1. `weekly-squad-digest/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `workflow/inputs.md` (parse `rollup_manifest`, `staleness_warning_days`; untrusted-content note) and
   `workflow/run-digest.md` (read both rollups, group by squad then metric_type, compute staleness, render).
3. `reference/phase-index.md`, `lazy-load-index.md`, `smoke-test.md`, `report-format.md` (normative
   `WEEKLY_SQUAD_DIGEST.md` structure).
4. `.cursor/rules/weekly-squad-digest.mdc`, `.kiro/steering/weekly-squad-digest.md`.
5. `Makefile`: `install-weekly-squad-digest` (chains `install-migration-program-manager
   install-cost-optimization-sprint-planner`), `install-claude-weekly-squad-digest`,
   `lint-weekly-squad-digest` (SKILL.md line count, `disable-model-invocation: true` set, workflow
   frontmatter, dangling links, required reference files — no scripts/pytest, this skill is pure
   markdown-workflow like cost-optimization-sprint-planner), added to `.PHONY`/`lint:` deps and
   `lint-framework`'s 4 hardcoded per-skill loops.
6. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: rows following the established pattern.
7. `docs/skill-framework/shared/skill-routing.md`, `cross-skill-escalation.md`, `prompt-injection.md`,
   `phase-glossary.md`: routing row, escalation rows, mapping subsection (not exempt — has its own
   Analyze logic: the two-rollup merge, the metric_type split, the staleness computation).
8. Root `CHANGELOG.md` + `weekly-squad-digest/CHANGELOG.md`: initial release entry.
9. `make lint` green; deep review pass(es), fixing to 0 issues each round; commit.
