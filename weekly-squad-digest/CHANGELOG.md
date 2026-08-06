# Changelog — weekly-squad-digest

All notable changes to the weekly-squad-digest skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — the first skill in this repo to read two already-computed `org_rollup_item`
  rollup files (migration-program-manager's `migration_program_rollup.json` and
  cost-optimization-sprint-planner's `cost_optimization_sprint_rollup.json`) and combine them, rather than
  producing a rollup of its own. Confirmed via design research: both producing skills already document
  "written so a future Weekly Squad Digest can reuse this" — this skill is that reuse, not new invention.
- `workflow/inputs.md` — `rollup_manifest` (both paths individually optional, HARD STOP only if neither
  is set) + `staleness_warning_days` (default 14, display-only — never changes a computed `status`,
  unlike migration-program-manager's own staleness threshold)
- `workflow/run-digest.md` — reads both rollups (a missing one is a gap, not a HARD STOP for the other),
  groups by squad then splits by `metric_type` into Migration status / Cost optimization sub-sections
  (never merged into one cross-metric ranking — the two `value` shapes aren't comparable), computes
  per-item staleness, renders
- **Corrects a claim made in two other places before designing against it**: the roadmap item's own
  wording ("squad-map — routing to the right channel") and
  [org-rollup-aggregation-layer-design.md](../docs/superpowers/specs/2026-08-05-org-rollup-aggregation-layer-design.md)
  (which stated as settled fact that squad-map has "its own routing convention" this skill would reuse)
  both imply a squad→channel delivery mechanism that doesn't exist anywhere in squad-map's actual schema
  (`SQUAD_MAP.md` has two ownership *name* columns, no channel/contact/webhook field) or in either cited
  precedent (who-owns-x-bot/incident-triage-agent both have one hardcoded/configured target, not a
  per-squad table). This skill produces one combined markdown digest instead, with per-squad-channel
  delivery left to an external handler documented in `SETUP.md` — the same pattern every other
  `disable-model-invocation: true` skill in this repo already uses (backlog-runner's morning summary,
  incident-triage-agent's triage doc)
- **No gate policy** — same reasoning as migration-program-manager: nothing is ever invoked live (neither
  producing skill, nor squad-map), so there's nothing to gate or confirm
- `disable-model-invocation: true` — same scheduled-trigger pattern as backlog-runner; a human asking for
  a single-source status question still routes to migration-program-manager or
  cost-optimization-sprint-planner directly
- No scripts of its own — pure markdown-workflow, like cost-optimization-sprint-planner
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md](../docs/superpowers/specs/2026-08-05-weekly-squad-digest-design.md)
  — this is the last item (#11) of the [team-facing agents roadmap](../docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md)

### Fixed (round-1 review, same day)
- **`squad_confidence`'s "Notes callout" rule contradicted the report's own normative Structure
  template** — the template's Notes column was defined single-purpose (staleness only), with no room
  shown for a confidence callout, and the cited "same convention as cost-optimization-sprint-planner"
  precedent didn't actually match (that skill uses a dedicated Confidence column, not a Notes callout).
  Fixed: both tables now have a real Confidence column showing every item's `squad_confidence`, not just
  LOW/UNKNOWN ones — genuine parity with cost-optimization-sprint-planner's own report structure.
- **Migration items' staleness flag was effectively meaningless per-item.** migration-program-manager's
  `last_updated` is stamped at aggregation-run time (the same instant for every item that run), not a
  per-service signal — so a `last_updated`-derived age for migration items would tell you "how long since
  the aggregator last ran," not "which service's data is actually stale," despite this skill's own
  framing implying genuine per-item granularity. Fixed: migration items now prefer `staleness_days`
  (which genuinely does vary per service via persisted `gate_signature` comparison) when present, falling
  back to `last_updated`-derived age only if absent; cost items (no `staleness_days` equivalent) always
  use `last_updated`-derived age.
- **The same `service` appearing in both rollups under different squads** (a real, expected case — the
  two rollups resolve `squad` via different join mechanisms) **was acknowledged only in `SETUP.md`'s
  operator-facing troubleshooting table, never in the normative render spec.** A reader of
  `WEEKLY_SQUAD_DIGEST.md` could see the same service under two squad headings with no indication they're
  the same service. Fixed: added an explicit cross-referencing rule to `reference/report-format.md` and a
  detection step to `workflow/run-digest.md` § 2 — each side's Notes column now points at the other
  section/squad, never silently presented as two unrelated rows.

Found by an adversarial review agent that verified every field name, quote, and precedent claim against
the real source files (migration-program-manager's, cost-optimization-sprint-planner's, squad-map's own)
rather than trusting this skill's own docs — the central "squad-map has no routing convention" design
claim held up under scrutiny, but three implementation-level gaps in how the digest actually renders
staleness, confidence, and cross-rollup conflicts did not.
