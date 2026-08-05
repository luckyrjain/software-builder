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
  only, 31 pytest cases in `tests/test_aggregate_migration_status.py`
- Never invokes mysql-to-postgres-sql or squad-map live — pure file reads; a missing `SQUAD_MAP.md` joins
  as `squad: UNKNOWN` rather than triggering squad-map itself (same lesson `new-hire-guide`'s round-1
  review learned about narrowing a live wrapped-skill invocation's scope — this skill avoids the whole
  risk class by never invoking either wrapped skill live)
- No `disable-model-invocation`, no gate-policy file — nothing to gate when nothing is invoked live
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-migration-program-manager-design.md](../docs/superpowers/specs/2026-08-05-migration-program-manager-design.md)

### Fixed (round-1 review, same day)
- **`join_squad` used the wrong squad-map tiebreak on a Conflicts-adjacent row.** It preferred `GitLab
  squad` over `Datadog team` whenever both were present; squad-map's own documented tiebreak (and
  org-rollup-schema.md's `pg_migration_gate` adapter) is the opposite — Datadog team (runtime ownership)
  wins on disagreement. Fixed to prefer `Datadog team` when the two differ.
- **`squad_confidence` wasn't normalized to the schema's enum.** A Confidence cell like `MEDIUM ⚠️` (as
  squad-map's own Reconciliation table documents for a conflict row) was copied verbatim into
  `migration_program_rollup.json`, breaking the `HIGH | MEDIUM | LOW | UNKNOWN` contract for any future
  consumer (e.g. the planned Weekly Squad Digest) that switches on the field. Added `normalize_confidence`
  — takes the leading token, falls back to `UNKNOWN` for anything outside the enum.
- **`derive_status` never reached `done` for a dialect-only service.** It required the literal strings
  `pass`/`pass`/`done`, but mysql-to-postgres-sql's own template documents `n/a` as the legitimate
  terminal value for `shadow_compare`/`config_cutover` when a service has nothing to shadow-compare or cut
  over. Fixed to treat `n/a` as settled alongside `pass`/`done`.
- **A malformed `MIGRATION_STATUS.yaml` or corrupted state file crashed the entire multi-workspace run**,
  not just the one workspace at fault — contradicting this skill's own "a gap in one workspace never
  drops the others" design principle. `parse_migration_status` now catches `yaml.YAMLError` and downgrades
  to a per-workspace `Gap`; `load_state` now catches `json.JSONDecodeError` and falls back to empty state
  with a stderr warning, rather than aborting `main()`.
- **`migration_program_rollup.json` never recorded `stalled`**, even though org-rollup-schema.md's own
  adapter table documents 4 status values (`blocked`/`stalled`/`in_progress`/`done`) for this exact
  adapter — `stalled` was applied only transiently at report-render time, so a future consumer reading the
  JSON directly (the file's whole reason for existing) would have had to re-derive it from
  `staleness_days` itself. `build_rollup` now takes `staleness_threshold_days` and writes the final
  `blocked > stalled > in_progress/done` status into the persisted rollup.
- **The script's own stdout summary double-counted a blocked-and-stale service** in both the `blocked` and
  `stalled` tallies. Now mutually exclusive, matching the persisted `status` field.
- 11 new pytest cases added covering the conflict tiebreak, confidence normalization, the dialect-only
  `done` case, malformed-YAML/malformed-state gap handling, and the `stalled` status derivation (26 total,
  up from 15).

### Fixed (round-2 review, same day)
- **The round-1 "stalled" fix over-applied the staleness override.** It escalated *any* non-`blocked`
  status to `stalled` once staleness crossed the threshold, including `done` — since a completed
  migration's gate signature is expected to stay unchanged forever once finished, every completed
  migration eventually got flagged as a false "stalled" alarm on later runs. Fixed: the staleness
  override now only applies to `status == "in_progress"`, per org-rollup-schema.md's own adapter
  wording ("a gate has been pending/not_run past threshold") — `done` and `blocked` are never
  reclassified by staleness.
- **`load_manifest` had an unguarded `json.load` and unguarded `entry["workspace_root"]` access**,
  the same crash class round-1 fixed for `MIGRATION_STATUS.yaml` and the state file, missed here. A
  malformed `--manifest` or an entry missing `workspace_root` raised a raw Python traceback instead of
  a clear error — worse than the other two cases, since a bad manifest kills the entire run before any
  per-workspace gap is even possible. Added `ManifestError` (raised for invalid JSON, a non-array
  top level, or a missing `workspace_root`); `main()` catches it and prints a one-line `error:` message
  with exit code 1 instead of a stack trace.
- 5 new pytest cases (`TestLoadManifest` × 4, plus a `done`-stays-`done`-under-staleness regression
  test) — 31 total, up from 26.
