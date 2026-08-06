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
