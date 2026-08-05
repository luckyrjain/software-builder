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
  only, 47 pytest cases in `tests/test_aggregate_migration_status.py`
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

### Fixed (round-3 review, same day)
- **`parse_migration_status` only guarded YAML *syntax* errors, not *shape* errors.** A
  syntactically valid `MIGRATION_STATUS.yaml` whose top level wasn't a mapping (e.g. a bare list),
  whose `services` key wasn't a list, or whose `services` list contained a non-mapping entry (a
  stray string from a hand-edit) crashed `build_rollup` with a raw `AttributeError` and took down
  the *entire* multi-workspace run — the exact crash class round-1 claimed to have closed, just one
  layer deeper (type validation, not just parse-error handling). Fixed: `parse_migration_status` now
  validates the top level is a mapping and `services` is a list (gap on either), and silently skips
  non-mapping entries within an otherwise-valid `services` list rather than crashing on them.
- **`compute_staleness` crashed on a state-file entry with a missing or unparseable
  `first_observed_at`.** `load_state`'s existing malformed-JSON guard only covers the whole file
  being invalid JSON, not a validly-parsed-but-wrong-shape entry inside it. Fixed: a missing or
  unparseable `first_observed_at` is now treated the same as a first observation (staleness 0,
  `first_observed_at` reset to now) instead of raising `KeyError`/`ValueError`.
- 5 new pytest cases (3 for `parse_migration_status`'s type validation, 2 for
  `compute_staleness`'s corrupted-entry handling) — 36 total, up from 31.

### Fixed (round-4 review, same day)
- **`load_state` never validated the parsed JSON's top-level shape**, only that it was valid
  JSON — the same gap round 3 closed for `parse_migration_status`'s top level, missed here. A
  `state_path` file that's valid JSON but not a mapping (e.g. a bare list) crashed
  `compute_staleness`'s `state.get(key)` with a raw `AttributeError`. Fixed: `load_state` now
  falls back to empty state (with a stderr warning) on a non-mapping top level too.
- **A YAML-auto-typed date scalar crashed the final `json.dumps`.** `yaml.safe_load` converts an
  unquoted date-shaped value (e.g. `mr_url: 2026-08-05`, a plausible hand-edit of a free-text
  template field) into a `datetime.date` object; that object flowed untouched into
  `RollupItem.value`/`priority` and blew up JSON serialization at the very last step, after every
  workspace had already been processed. Added `json_safe()` — stringifies anything that isn't
  already a JSON primitive — applied to every pass-through field
  (`scan_gate`/`shadow_compare`/`config_cutover`/`mr_url`/`tier_focus`) before it reaches
  `RollupItem`.
- **`load_manifest` validated `workspace_root`/`squad_map_path` were present but not that they
  were strings.** A manifest entry with a JSON number, list, or bool for either field passed
  validation and crashed downstream (`Path(12345)`, `TypeError`) with a raw traceback — directly
  contradicting `ManifestError`'s own "never a raw traceback" contract. Fixed: both fields are now
  type-checked as part of manifest validation.
- **`--staleness-threshold-days` accepted a negative value**, which silently flagged every
  freshly-observed `in_progress` service as `stalled` on its very first run (`0 >= negative` is
  always true). Added a clean `>= 0` validation in `main()` instead of a confusing first-run
  result.
- 7 new pytest cases (`load_state` shape, `json_safe` unit test + an end-to-end
  `build_rollup`-through-`json.dumps` regression test, 2 `load_manifest` type-validation cases, 1
  CLI-level negative-threshold case) — 43 total, up from 36.

### Fixed (round-5 review, same day)
- **A service's `name`/`path` field left as a YAML-auto-typed non-string (e.g. an unquoted
  date- or number-shaped service name, or a stray list/mapping from a hand-edit) crashed the
  entire multi-workspace run**, not just the one workspace at fault — the same "never crash
  the whole run" contract round 1 through round 4 each closed one field/layer at a time, missed
  here. Unlike `scan_gate`/`shadow_compare`/`config_cutover`/`mr_url`/`tier_focus` (all routed
  through round-4's `json_safe()`), `name` and `path` were read via bare `svc.get(...)` and
  handed straight to `join_squad`, which calls `candidate.strip()` on them — an
  `AttributeError` whenever the workspace has a populated `SQUAD_MAP.md` (the normal case),
  raised as a raw traceback out of `build_rollup`/`main()` with no per-workspace `Gap` to catch
  it. Added `coerce_str()` (distinct from `json_safe()` — must always produce a real `str`,
  including for `int`/`bool`/`float`, since these need `.strip()` to work, not just JSON
  serializability) and applied it to `name`/`path` immediately after they're read from the
  service dict, before either reaches `join_squad` or `RollupItem.service`.
- 4 new pytest cases (`coerce_str` unit tests × 3, 1 `build_rollup`-level regression
  reproducing the crash with a populated `SQUAD_MAP.md`) — 47 total, up from 43.
