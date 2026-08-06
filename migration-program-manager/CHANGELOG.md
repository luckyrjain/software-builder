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
  only, 50 pytest cases in `tests/test_aggregate_migration_status.py`
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

### Fixed (round-6 review, same day)
- **`compute_staleness`'s state-lookup key silently diverged from `build_rollup`'s state-write
  key whenever a service's `name` field was missing or explicitly `null`**, latent since round 1
  (not introduced by round 5) and never a crash — that's exactly why 5 rounds of crash-hunting
  missed it. `compute_staleness` built its read key as `f"{workspace_root}::{svc.get('name')}"`;
  when `name` is absent or `null`, `svc.get('name')` is `None` either way, and an f-string
  stringifies that to the literal `"None"`. `build_rollup` builds its write key from
  `coerce_str(svc.get("name", ""))`, which yields `""` for both of those same cases. The read key
  (`"...::None"`) and the write key (`"...::"`) never matched, so a service without a `name` could
  never find the `first_observed_at` it persisted last run — every run looked like a first
  observation, staleness silently pinned at 0 forever, and such a service could never reach
  `"stalled"` no matter how long its gate signature stayed unchanged. No error, no gap, no
  traceback — the staleness feature (this skill's core purpose per its own module docstring) was
  just silently inert for these services. Fixed `compute_staleness` to build its key with the
  exact same `coerce_str(svc.get("name", ""))` expression `build_rollup` uses.
- Found by feeding `build_rollup`'s own persisted `new_state` back into a second `build_rollup`
  call — a true round-trip through the exact `load_state`/`save_state` path `main()` uses — which
  no test across 5 prior rounds had done; every existing staleness test hand-constructed its
  `state` input with a key that happened to already match the code under test.
- 3 new pytest cases (`compute_staleness` key-match unit tests for missing/null `name`, 1
  `build_rollup`-level two-run round-trip regression) — 50 total, up from 47.

### Fixed (round-7 review, same day)
- **`workflow/run-rollup.md` § 2 and `reference/report-format.md` described Blocked/Stalled section
  membership by restating each status's raw criteria (`blocked` = "any gate `fail`", `stalled` =
  "staleness ≥ `staleness_threshold_days`") instead of pointing at the single, already-finalized `status`
  field `build_rollup` persists into `migration_program_rollup.json`.** Those two criteria aren't
  mutually exclusive on their own: a `blocked` service's `staleness_days` can independently exceed the
  threshold too (its failing gate just hasn't changed in a while) — confirmed with a real two-run CLI
  round trip (`scan_gate: fail` held unchanged 20 days past a 14-day threshold) that produces exactly
  this shape in the persisted rollup: `{"status": "blocked", "staleness_days": 20, "value":
  {"scan_gate": "fail", ...}}`. The script itself never double-counts this (`build_rollup`'s status
  override only fires for `status == "in_progress"`, same guard round 2 added), but an agent rendering
  `MIGRATION_PROGRAM_REPORT.md` from the two docs' literal wording — independently re-checking "any gate
  fail" and "staleness ≥ threshold" as separate conditions per service, rather than reading the one
  `status` field the aggregator already committed to disk — could place that same service in *both* the
  Blocked and Stalled tables, silently drifting from the rollup JSON's own single source of truth. The
  same failure shape as round 1's stdout double-count, relocated from the script to the docs that drive
  the agent's report-rendering step. Fixed: both docs now explicitly instruct grouping by the persisted
  `status` field (mutually exclusive, `blocked` wins) and call out the blocked-and-stale case by name as
  the reason not to re-derive membership from `value.*`/`staleness_days` while rendering.
- No script change, no new pytest cases (a workflow-doc clarification, not a code path) — 50 total,
  unchanged from round 6. Verified via real `--state-path` round trips through the actual CLI
  (`python3 scripts/aggregate_migration_status.py ...`, not direct function calls): (1) an `in_progress`
  service across 3 runs — unchanged same-day, then unchanged 15 days later past a 14-day threshold —
  correctly reaches `stalled`; (2) a `stalled` service whose `MIGRATION_STATUS.yaml` gate values then
  change (progress made) correctly resets to `staleness_days: 0` / `status: in_progress`, not stuck;
  (3) a workspace removed from `program_manifest` between runs has its services' state entries fully
  pruned from `state.json` on the very next run (`new_state` is rebuilt fresh from the current manifest
  each run and `save_state` overwrites, never merges) — no stale-state leak if that workspace's name is
  ever reused. All three round trips executed clean; `gate_signature`, `evidence_ref`, and the
  `workspace_root::name` state key each have exactly one production call site (`compute_staleness`,
  `build_rollup`, and `compute_staleness`+`build_rollup` sharing the identical `coerce_str(...)`
  expression respectively) — no other latent two-call-site drift risk found in the script itself.
