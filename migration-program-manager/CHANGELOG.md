# Changelog — migration-program-manager

All notable changes to the migration-program-manager skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — pure read-only aggregator over mysql-to-postgres-sql's `MIGRATION_STATUS.yaml`
  and squad-map's `SQUAD_MAP.md`, implementing [org-rollup-schema.md](../docs/skill-framework/shared/org-rollup-schema.md)'s
  `pg_migration_gate` adapter
- `workflow/inputs.md` — `program_manifest` (list of workspaces) + `staleness_threshold_days` (no default
  — an operational policy decision) + `state_path` parsing, HARD STOP on missing required fields
- `workflow/run-rollup.md` — invokes `scripts/aggregate_migration_status.py`, ranks/groups by squad, builds
  `MIGRATION_PROGRAM_REPORT.md` + `migration_program_rollup.json`
- `scripts/aggregate_migration_status.py` — this repo's first cross-workspace aggregator: parses
  `MIGRATION_STATUS.yaml` × N, parses `SQUAD_MAP.md`'s main join table (tolerating its Conflicts/Unmapped/
  Out-of-scope sections — the repo's first markdown-table parser), joins, computes staleness against
  persisted cross-run state (`gate_signature` + `first_observed_at` per service — genuinely new since
  `MIGRATION_STATUS.yaml` has no per-gate timestamp), `main(argv) -> int` CLI entrypoint, stdlib + PyYAML
  only, 15 pytest cases in `tests/test_aggregate_migration_status.py`
- Never invokes mysql-to-postgres-sql or squad-map live — pure file reads; a missing `SQUAD_MAP.md` joins
  as `squad: UNKNOWN` rather than triggering squad-map itself (same lesson `new-hire-guide`'s round-1
  review learned about narrowing a live wrapped-skill invocation's scope — this skill avoids the whole
  risk class by never invoking either wrapped skill live)
- No `disable-model-invocation`, no gate-policy file — nothing to gate when nothing is invoked live
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-migration-program-manager-design.md](../docs/superpowers/specs/2026-08-05-migration-program-manager-design.md)
