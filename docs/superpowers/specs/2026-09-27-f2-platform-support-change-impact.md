# Change impact report — F2: per-skill platform support declaration + install-time enforcement

**title:** F2 — per-skill platform support declaration + install-time enforcement
**assessment_target:** [2026-09-27-f2-platform-support-design.md](2026-09-27-f2-platform-support-design.md) (revision 4, `proposed_state`), validated by [2026-09-27-f2-platform-support-architecture-review.md](2026-09-27-f2-platform-support-architecture-review.md) (Approved with conditions)
**coverage_status:** COMPLETE — repository read used to ground every field, including a direct check that `validate_registry()` is genuinely the one function both `cmd_generate` and `cmd_validate` unconditionally share, and that `package_skill._resolve_source_dir`'s recursion risk (via `parse_registry()`) is real and correctly avoided by the design's corrected local path computation

## material_unknowns

None on the design's own terms — 4 rounds of adversarial review, converging CLEAN, leave no undisclosed
gaps. The one thing this report cannot verify from documents alone is whether the Builder's actual
implementation preserves the specific boundaries the design's own review process fought hardest to
establish (see `review_triggers` — these are review-time checks, not change-impact unknowns).

## criticality

**High** — a different tier from every prior ticket this session (A5/A6/F1/F4), and higher than F2's own
architecture review initially framed it. Those changes were each confined to one skill's own executor
script, one new standalone file, or (at most) one shared library function reused read-only. **This change
modifies `scripts/registry/schema.py`'s `_parse_skill_entry` and adds a new call inside
`scripts/registry/crosscheck.py`'s `validate_registry()` — both are shared parse-path code that every one
of `make generate`, `make validate`, and every single `sb install <any-skill>` invocation runs, for all
~50 skills, not just the two skills this ticket names.** A defect introduced here has repo-wide reach: a
bug in the new `platforms` resolution logic could degrade or crash registry processing for skills that have
nothing to do with this ticket. The design's own 4-round review process already found and fixed exactly
this class of defect once (an uncaught parse error from one skill's malformed `.py` file could have crashed
registry resolution for all 50 skills simultaneously) — this criticality rating reflects that this is a
real, demonstrated risk class for this specific change, not a hypothetical one.

## change_classes

- **New pure module**: `scripts/registry/platform_detection.py` (`derive_platforms`, AST-based, no I/O
  beyond reading `.py` files under one skill's directory)
- **New validator function**: `validate_platform_declarations`, added inside `crosscheck.py`'s
  `validate_registry()` — this is the load-bearing integration point the design's own round 3 review
  specifically had to locate by tracing `cli.py`'s actual call graph; a Builder placing this call anywhere
  else (e.g. inside `_validate_all` directly, a natural but incorrect first guess) would silently make
  `cmd_generate --check` never catch override-vs-derivation drift
- **Additive schema field**: `SkillEntry.platforms: list[str]` (`models.py`), parsed via a new
  `_parse_platforms`-style function in `schema.py`, following `_parse_risk_class`'s exact existing pattern
- **Modified shared parse-path function**: `_parse_skill_entry` (`schema.py`) — gains the logic to resolve
  each skill's on-disk path locally (`root / entry.get("path", skill_id)`, computed independently, **not**
  by calling `package_skill._resolve_source_dir`, which would recurse via `parse_registry()`) and pass it to
  `derive_platforms` when `platforms:` is absent from the fragment
- **New CLI enforcement**: `install_engine.py`'s `install_skill()` gains a platform-check hook, a
  `sys.platform` → `{"posix","windows"}` translation, and a new `--allow-unsupported-platform` flag
- **Modified existing scripts, each independently**: `idempotency_store.py` (guarded import, new
  `UnsupportedPlatformError`, new exit code `5`), `aggregate_migration_status.py` (guarded import only, CLI
  entrypoint scope confirmed sufficient — no shared helper module between the two, matching this repo's
  established convention of independent duplication over cross-skill-package coupling, confirmed by direct
  read of `plan_state_store.py`/`task_lease.py` already doing the same)
- **Modified generated docs**: `generate_docs.py` (new table column), `generate_agent_compatibility.py` (new
  disclaimer template constant), `docs/skill-framework/shared/terminology-glossary.md` (new glossary entry
  — confirmed by direct read this is the actually-correct location, not `CONTEXT.md`, which does not
  document `risk_class` either despite an earlier design revision's stale assumption that it did)
- **One-time, repo-wide `make generate` run**: bakes `platforms` for all ~50 skills; two skills get explicit
  hand-authored overrides as defense-in-depth (not load-bearing — the design's own Phase 0 gating test
  requires the corrected auto-detector to classify both correctly independently of the override)

## impacted_repositories

- `luckyrjain/software-builder` only.

## impacted_services

- N/A — local CLI/registry-generation tooling, no runtime service.

## impacted_contracts

- **`_parse_skill_entry`'s existing per-skill parsing contract** (confirmed by direct read,
  `schema.py:360-400`): currently raises `ValueError` only on malformed shape (mirroring `_parse_risk_class`'s
  exact idiom, confirmed at `schema.py:519-528`) — the design's own review process confirmed this contract
  is preserved: `platforms` resolution itself never raises on an override/derivation mismatch, only
  `validate_platform_declarations` (a genuinely separate step) does, and only inside the validation layer,
  never inside `SkillEntry` construction.
- **`validate_registry()`'s existing role as the one function both `cmd_generate` and `cmd_validate`
  unconditionally share** (confirmed by direct read of `cli.py`'s `_validate_for_generate`/`_validate_all`
  call chain, per the design's own round-3 finding): this is now a load-bearing integration contract for
  this feature's drift detection to work at all. Any refactor of `cli.py`'s validator-wiring in the future
  must preserve `validate_registry()`'s unconditional-call property, or this feature's CI enforcement
  silently stops working with no test failure to catch it (see `unknowns`).
- **`package_skill._resolve_source_dir`'s existing behavior** (confirmed by direct read, delegates to
  `scripts/registry/paths.py`'s `skill_dir()`): unchanged by this design — the new local path computation in
  `_parse_skill_entry` deliberately does **not** call this function (would recurse via `parse_registry()`);
  it independently replicates `skill_dir()`'s own formula (`root / entry.path` with a `skill_id` fallback),
  confirmed by direct read to produce byte-identical results for any already-registered skill.
- **`idempotency_store.py`'s existing exit-code contract** (0-4, confirmed by direct read of `main()` and
  `reference/idempotency.md`'s existing table, all from the prior F4 hardening round): codes 0-4 are
  unchanged; the new code `5` is confirmed free — no collision.
- **`install_skill()`'s existing precondition-check ordering** (confirmed by direct read,
  `install_engine.py:538-565`): registry-membership check → ownership classification → dry-run
  short-circuit. The new platform-check hooks in before ownership classification and before the dry-run
  short-circuit, preserving dry-run's accuracy (a dry-run preview correctly reflects a platform-mismatch
  refusal) — confirmed consistent with the design's own stated intent.

## impacted_data

- New per-skill registry field (`platforms`) in `skills.yaml` — no migration needed, absence has a
  well-defined derived meaning.
- No new on-disk data files, no new stored state anywhere.

## impacted_dependencies

- **`scripts/registry/crosscheck.py`'s existing `validate_registry()` sibling checks**
  (`_validate_skill_paths_share_one_parent`, `_validate_invoke_skill_references`, etc., confirmed present by
  direct read): `validate_platform_declarations` is added alongside these, following the exact same
  "compute expected, compare, append error string" idiom already established there — no new pattern
  introduced.
- **`scripts/tests/install_lock_test_helpers.py`'s `spawn_lock_holder` pattern**: not needed for this
  ticket (no new locking primitive), confirmed out of scope.
- **`make lint-python`/`make generate --check`**: both already existing, already CI-wired
  (`generate-check` confirmed a required `lint-static` prerequisite by direct read of
  `make/core.mk`/`.github/workflows/lint.yml`) — this feature's drift detection rides on already-required
  CI, no new CI job needed.
- **No new PyPI dependency** — `platform_detection.py` is stdlib-only (`ast`, `pathlib`).
- **Both `idempotency_store.py` and `aggregate_migration_status.py`'s guarded-import fixes are independent,
  non-shared code** — confirmed consistent with this repo's own established convention (`plan_state_store.py`/
  `task_lease.py` already duplicate the same guard pattern independently rather than sharing a helper
  module), so this isn't a new coupling decision, it's continuity with existing practice.

## impacted_owners

- Repo owner (`@luckyrjain`), sole owner, unchanged.

## required_tests

- `platform_detection.py` unit tests: purely-syntactic rule (bare `try/except ImportError` → POSIX-only
  regardless of handler content, including the `import msvcrt as fcntl` real-fallback case explicitly
  misclassified as an accepted, disclosed trade-off; `if sys.platform: ... else: ...` → not POSIX-only; a
  guarded import nested below module-top-level → no evidence either way).
- **Mixed-file same-skill aggregation test** (one file has real unconditional POSIX-only evidence, a sibling
  file in the same skill has a syntax error → skill still correctly classifies `["posix"]`) — this is the
  concrete regression test for round 3's aggregation-semantics fix and should be treated as required, not
  optional, given it directly tests a previously-real under-restriction bug.
- **Cross-skill isolation test** (one skill's malformed `.py` file does not crash or affect another skill's
  classification) — the concrete regression test for the repo-wide-crash bug this design's own review
  process found and fixed; required.
- **NUL-byte fixture test** (`ValueError` from `ast.parse()` on an embedded NUL byte, caught, no crash) —
  required, given this exact case was independently found in round 3.
- `validate_platform_declarations` tests, calling it exactly as wired into `validate_registry()` — override
  matches derivation → clean; mismatch → distinct error, verified to actually fail both `cmd_generate
  --check` and `cmd_validate`, not just asserted.
- `install_engine.py`'s platform-check: `sys.platform` translation test; refuse-by-default and
  `--allow-unsupported-platform` paths; dry-run coverage (a mismatch is still refused during `--dry-run`).
- `idempotency_store.py`'s `UnsupportedPlatformError`/exit-`5` test, both the CLI path and a direct
  Python-handler-style `mr_lock()` call, under simulated `sys.platform == "win32"`.
- **Repo-wide `make generate` regression**: after landing the code, the one-time repo-wide `make generate`
  run must be diffed against an explicit expected-classification list for `pr-gatekeeper` and
  `migration-program-manager` (both must derive `["posix"]` from auto-detection alone, per the design's own
  Phase 0 gating requirement) — any other skill unexpectedly classifying `["posix"]` (i.e., the detector
  found POSIX-only evidence somewhere not anticipated) should be spot-checked before merge, not silently
  accepted.
- `make lint-python` — standing no-regression check.

## operational_impacts

- **New, first-time-in-this-repo class of risk**: a bug in shared registry parse-path code (`schema.py`,
  `crosscheck.py`) has repo-wide reach across all ~50 skills' registry processing on every `make generate`/
  `make validate`/`sb install` invocation — not confined to the two skills this ticket names. The design's
  own review process already found and fixed the most severe instance of this risk class (an uncaught
  parse-error crash), which is the strongest available evidence this risk is real and worth naming plainly,
  not just a hypothetical severity-inflation.
- **New user-facing behavior**: `sb install`/`install.sh` can now refuse an install it previously would have
  silently attempted — a real, disclosed, intentional behavior change for any Windows user installing
  `pr-gatekeeper` or `migration-program-manager` going forward (was previously a clean install followed by a
  mid-run crash; now a clear pre-install refusal, or an explicit override).
- **No new Actions minutes, no impact on required checks beyond what's already required** (`generate-check`
  already gates merge).
- **Owner-visible cost**: the one-time repo-wide `make generate` diff is the first artifact the owner should
  personally review before merge, given this is a bulk-classification pass across every skill — the
  design's own Phase 1 plan already requires this, restated here as a required, not optional, review step.

## review_triggers

- **Recommended, strongly**: verify the Builder's actual implementation places `validate_platform_declarations`
  inside `validate_registry()` specifically (`crosscheck.py`), not inside `_validate_all` or anywhere else
  that would compile and pass tests locally but silently fail to gate `cmd_generate --check` in practice —
  this is exactly the kind of defect that would not be caught by a naive test of "does `validate_platform_declarations`
  return the right errors," only by a test that actually invokes `cmd_generate --check`/`cmd_validate`
  end-to-end against a deliberately-mismatched fixture.
- **Recommended, strongly**: verify the path-computation fix does not call `package_skill._resolve_source_dir`
  anywhere in the actual implementation — a Builder who "helpfully" simplifies the local computation back
  into a call to that function would reintroduce the recursion trap the design's own review found and fixed.
- **Recommended**: verify the per-file parse-error isolation is implemented at the correct granularity
  (per-file within a skill, not per-skill) — the mixed-file aggregation test above is the concrete check,
  but this is subtle enough that both review lenses should treat it as a named check, not incidental
  coverage, given round 3 found this exact ambiguity in the design text itself.
- No other hard trigger under this skill's own vocabulary — no external API, no database, no new attack
  surface beyond what's already been adversarially reviewed across 4 rounds.

## unknowns

- Whether `cli.py`'s validator-wiring is ever refactored in the future in a way that breaks
  `validate_registry()`'s "unconditionally called by both commands" property without any test noticing —
  this is a structural dependency this feature now has on an implementation detail of unrelated code, not
  something this ticket can close, but worth naming for future maintainers.
- Whether the repo-wide `make generate` run surfaces any skill besides the two named ones unexpectedly
  classifying as POSIX-only — not knowable until the Builder actually runs it against the real, current
  state of all ~50 skills' scripts.

## evidence_refs

- `docs/superpowers/specs/2026-09-27-f2-platform-support-design.md` (revision 4, full document, including
  all 4 rounds' Revision history entries)
- `docs/superpowers/specs/2026-09-27-f2-platform-support-architecture-review.md` (Approved with conditions)
- `scripts/registry/cli.py:103-145,251-301` (`_validate_for_generate`/`_validate_all`/`cmd_generate`/
  `cmd_validate` — confirmed call-graph convergence on `validate_registry()`)
- `scripts/registry/crosscheck.py` (`validate_registry()` and its existing sibling `_validate_*` checks)
- `scripts/registry/schema.py:360-400,519-528` (`_parse_skill_entry`, `_parse_risk_class` precedent)
- `scripts/registry/models.py` (`SkillEntry` dataclass)
- `scripts/package_skill.py:242-260`, `scripts/registry/paths.py` (`_resolve_source_dir`/`skill_dir` —
  confirmed recursion risk and the exact formula the local computation replicates)
- `scripts/install_engine.py:523-649` (`install_skill()`, existing precondition-check ordering)
- `skills/pr-gatekeeper/scripts/idempotency_store.py`, `skills/pr-gatekeeper/reference/idempotency.md`
  (existing exit-code table, confirmed 0-4 used, 5 free)
- `skills/migration-program-manager/scripts/aggregate_migration_status.py`
- `scripts/plan_state_store.py`, `scripts/task_lease.py` (confirmed independent-duplication convention)
- `make/core.mk`, `.github/workflows/lint.yml` (confirmed `generate-check` is a required `lint-static`
  prerequisite)
