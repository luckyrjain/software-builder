# System Design Spec — F2: per-skill platform support declaration + install-time enforcement

**Readiness: Ready to implement**

Revision 4, after round 3 of adversarial review (2 personas, tightly scoped to revision 3's 4 fixes) found
two of them genuinely resolved (`mr_lock()`/exit-5 contract, purely-syntactic rule consistency) and three
concrete, code-traced gaps in the other two — including a genuine circular-recursion trap in the
path-threading plumbing that would have crashed or become pathologically expensive on every registry read.
**Round 4 (SRE, final, tightly scoped to these 4 fixes) confirmed all four genuinely resolved by direct code
trace against `crosscheck.py`, `schema.py`, and `package_skill.py`/`paths.py` — verdict CLEAN.** One
non-blocking suggestion surfaced (a bare `RecursionError` from pathologically deep nesting in `ast.parse()`
is still uncaught — narrower and far less likely than the NUL-byte case this exception set was built to
close; noted as an accepted residual limitation, not a blocker). See Revision history.

## Revision history

**Revision 3 → 4, round 3 findings (2 personas, tightly scoped to revision 3's 4 fixes):**

- **SRE (blocking)**: `validate_platform_declarations`'s wiring was still under-specified — the design named
  candidate homes ("`cmd_generate`'s/`cmd_validate`'s existing error-accumulation path") without naming the
  one function both commands actually, unconditionally share. Traced: `cmd_generate` calls
  `_validate_for_generate` directly; `cmd_validate` calls `_validate_all`, which calls
  `_validate_for_generate` first. The only unconditional call inside that shared function is
  `validate_registry(root)` (`scripts/registry/crosscheck.py`), the established home for every other
  "compare a resolved value against expectation, append an error string" check in this pipeline. **Fixed**:
  the design now names the exact call site — `validate_platform_declarations` is added inside
  `validate_registry()` in `crosscheck.py`, alongside its sibling `_validate_*` calls, guaranteeing both
  `cmd_generate --check` and `cmd_validate` actually reach it.
- **SRE (blocking)**: the per-file parse-failure isolation fix (revision 3) was ambiguous about **same-skill
  aggregation** — different sections said a parse failure defaults "for that one skill" vs. "for that file,"
  which are different behaviors. The unsafe reading (one failing file aborts the whole skill's scan) would
  silently discard real POSIX-only evidence found in a sibling file that parsed fine — an under-restriction
  bug, exactly the failure direction this design's purely-syntactic rule was chosen specifically to avoid.
  **Fixed**: the design now states explicitly that each file is parsed and scanned independently inside the
  per-skill loop; a failing file contributes zero evidence (not a skill-wide abort); the final classification
  is the union of whatever evidence survives across all successfully-parsed files; the permissive default is
  used only if literally no evidence survives anywhere in the skill.
- **SRE (blocking, genuinely new — found while tracing the plumbing fix)**: the "suggestions taken" note
  from revision 3 ("resolved the same way `package_skill._resolve_source_dir` already does") read as
  "call that function" — but `_resolve_source_dir` itself calls `parse_registry()`, which would recurse
  straight back into the very per-skill loop `platforms` resolution runs inside of (before that loop's own
  registry-cache entry is even written), either crashing with `RecursionError` or becoming pathologically
  expensive on every single registry read. **Fixed**: the design now says explicitly to compute the skill's
  on-disk path independently, using the same fallback *logic* (`root / entry.get("path", skill_id)`) computed
  locally inside `_parse_skill_entry` — never by invoking `_resolve_source_dir` itself.
- **SRE (blocking, high-confidence)**: the declared exception-catch set (`SyntaxError`/`UnicodeDecodeError`/
  `OSError`) is incomplete — CPython's `ast.parse()`/`compile()` raises `ValueError` (not `SyntaxError`) for
  source text containing an embedded NUL byte, a well-known quirk. A corrupted or binary-garbage `.py` file
  with a stray NUL byte would still escape the catch set and reproduce the exact repo-wide-crash defect this
  fix exists to close. **Fixed**: `ValueError` added to the catch set; a Phase 0 fixture with an embedded
  NUL byte added.
- **Software Architect (resolved, confirmed by code trace)**: the `mr_lock()`/`UnsupportedPlatformError`/
  exit-`5` contract is genuinely correct — `idempotency_store.py`'s actual exit codes (0-4) leave `5` free,
  and the fix mechanically extends an already-existing `try/except LockTimeoutError: return 3` pattern in
  `main()`. No changes needed.
- **Software Architect (resolved, confirmed by full-doc grep)**: the purely-syntactic detection rule is
  stated consistently across every section that mentions it, with no leftover "content-sensitive" language
  from the now-rejected revision 2 reading. No changes needed.
- **Software Architect (suggestion, taken)**: `_validate_for_generate` runs unconditionally in plain
  `make generate` too, not only `--check` — the Consistency/Failure-strategy wording is now corrected to say
  the drift check blocks any `make generate`/`cmd_validate` invocation (same as every other validator wired
  into that function), and has no effect on `sb install`/`install_skill()` itself.

**Revision 1 → 2** (round 1, 8 findings): fixed the detection rule's guard-vs-fallback conflation, the
generate-time-vs-every-read architectural inconsistency, the unspecified `sys.platform` translation, the
override-drift-detection gap, and the `mr_lock()` guard-placement gap. Kept for record, not repeated here
at full length.

**Revision 2 → 3, round 2 findings:**

- **Software Architect (blocking) + SRE (independently, same root cause)**: the design claimed
  `make generate --check` "already catches" an override-vs-derivation mismatch, but SRE traced the actual
  mechanism (`_check_outputs`'s byte-diff of generated file content) and found the `platforms` value written
  into `skills.yaml` is raw fragment passthrough either way — an override and a fresh derivation never
  differ in what gets *written*, so there is nothing for a byte-diff to catch. Software Architect
  independently found the design's own tables contradict each other about *where* a mismatch becomes a
  failure (a hard parse-time raise inside `SkillEntry` resolution, vs. a soft check-only failure) — and
  confirmed via the actual CI wiring (`generate-check` is a required `lint-static` prerequisite) that the
  *policy* claim ("a drifted override cannot reach merged `main` silently") is true, but the *mechanism*
  was never named. **Fixed**: the comparison is now explicitly specified as a **new, separate, named
  validator function** (`validate_platform_declarations`, wired into `cmd_generate`'s/`cmd_validate`'s
  existing error-accumulation path, distinct from `_check_outputs`'s file-diff) — `SkillEntry.platforms`
  resolution itself never raises on a mismatch (a mismatch is data, not an exception); only this dedicated
  validator turns it into a `make generate --check`/`cmd_validate` failure, which the existing CI wiring
  already blocks merge on.
- **Software Architect (blocking) + Security Architect (independently, same root cause) + SRE
  (independently, a symmetric case)**: the corrected detection rule's own prose was self-contradictory — one
  sentence said any bare `try/except ImportError` counts as POSIX-only evidence regardless of handler
  content, a parenthetical immediately qualified that with "no functioning cross-platform alternative,"
  and neither worked example resolved the real, plausible case of `try: import fcntl / except ImportError:
  import msvcrt as fcntl` (a genuine, working fallback shaped like the "doesn't count" pattern). Left
  ambiguous, a Builder could implement either reading, and the "content-sensitive" reading would require
  behavioral verification (does the handler's replacement actually get used?) that no static AST check can
  cheaply provide. **Fixed**: the rule is now committed to the **purely syntactic** reading — the
  parenthetical is dropped. Only an explicit `if sys.platform == ...: import X else: import Y` branch
  counts as a functional fallback; every `try/except ImportError` shape, regardless of handler content,
  counts as POSIX-only evidence. This is a deliberate, disclosed, safe-direction trade-off: it can
  over-restrict (misclassify a real try/except-based fallback as POSIX-only, blocking a Windows install
  that would have worked) but can never under-restrict (misclassify a POSIX-only skill as Windows-safe) —
  the failure direction this ticket most needs to avoid. A skill using the try/except-fallback idiom for
  real cross-platform support must hand-author an explicit `platforms: [posix, windows]` override.
- **Software Architect (blocking, a genuinely new gap created by combining revision 2's own two headline
  fixes)**: `parse_registry()` loops over every skill unconditionally, and derivation now runs on every
  read against live file content (not committed blobs) — so if any one of the ~50 skills has a `.py` file
  that currently fails to parse (a mid-edit syntax error, a bad encoding — confirmed not a problem today via
  a direct `ast.parse()` sweep, but a foreseeable one given "live file content" now actively invites it), an
  uncaught `SyntaxError`/`UnicodeDecodeError` from `derive_platforms()` would propagate out of
  `load_registry_raw()` uncaught by any existing error-accumulation layer (`_parse_skill_entry`'s per-skill
  catch is `ValueError`-only; `cli.py`'s catch-all doesn't cover these either) — one skill's WIP-broken,
  unrelated script would raw-crash `sb install <any other skill>`, `make validate`, and `make generate`
  simultaneously, repo-wide. This is precisely the "raw crash instead of a clean message" defect the whole
  ticket exists to eliminate, reintroduced at a new layer with a much larger blast radius. **Fixed**:
  `derive_platforms()` now catches `SyntaxError`/`UnicodeDecodeError`/`OSError` per file, fails closed to
  the permissive default (`["posix", "windows"]`) for that one skill, and emits a loud, named warning
  (surfaced through the same channel as any other detection miss) rather than propagating.
- **Security Architect (blocking)**: the `mr_lock()`-relocated guard (fixed in revision 2) had no specified
  exception type, no specified exit code, and no Phase 0 test — meaning the fix itself could ship with an
  uncaught new exception type propagating as a raw traceback from `main()`, reproducing the exact defect
  category this ticket exists to close, one layer down. **Fixed**: a new `UnsupportedPlatformError
  (RuntimeError)` is raised by the guard; `main()` catches it and maps to a new exit code `5` (documented in
  `reference/idempotency.md`'s exit-code table alongside 0-4); a Phase 0 test now exercises both the CLI
  path and a direct Python-handler-style `mr_lock()` call under a simulated `sys.platform == "win32"`.
- **All three reviewers, converging on one root cause (disclosed, not further mitigated)**: the AST
  detector verifies import *shape*, not behavioral equivalence — a skill author who partially or carelessly
  ports the `if sys.platform: ... else: ...` shape without actually wiring the alternate import into real
  use could fool the detector into classifying a still-broken skill as portable. Given the rule is now
  purely syntactic (see above), this residual gap is named explicitly as a third, accepted Failure-strategy
  row rather than further engineered around — behavioral verification is out of proportion for a static
  registry-generation check.
- **Suggestions taken**: the design now states explicitly that the `mr_lock()` guard's completeness rests
  on "every `fcntl.flock` call site funnels through `mr_lock()` today," not on a (incorrect) claim that
  every public function calls `mr_lock()` — a future direct `fcntl` call added elsewhere in the file would
  need its own guard, this is named as a maintenance note; the plumbing needed to thread a skill's
  on-disk `path:` into `derive_platforms()` (through `_parse_skill_entry`, resolved the same way
  `package_skill._resolve_source_dir` already does) is now named explicitly, not left implicit; the
  Capacity section now states the actual shape (`derive_platforms` runs across *all* ~50 skills' script
  trees on every single `sb install <one-skill>` subprocess invocation, since `install.sh` spawns a fresh
  process per skill×destination with no cross-process cache) rather than rounding to "negligible" with no
  growth caveat; the hand-authored overrides on the two known-POSIX-only skills are now stated as
  deliberate defense-in-depth/explicitness, not load-bearing correctness (Phase 0's test roster already
  requires the corrected auto-detector alone to classify both skills correctly); the doc-location claim for
  a `platforms` glossary entry now targets `docs/skill-framework/shared/terminology-glossary.md` (confirmed:
  this repo's actual registry-vocabulary doc, per its own stated purpose — `risk_class` itself is not
  actually documented in `CONTEXT.md` today, a stale assumption in revision 2 now corrected) rather than
  `CONTEXT.md`.

**Not yet re-reviewed**: round 3 has not run. Given the depth and genuine severity of round 2's findings
(a real repo-wide-crash bug, a mechanism-vs-policy mismatch three reviewers converged on from different
angles), this revision is marked **Ready with open questions**, not **Ready to implement**, pending
confirmation that these four fixes are correct and complete.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `scripts/registry/platform_detection.py` (new) | Purely syntactic AST scan, scoped to module-top-level imports only: an `if sys.platform == ...: import X else: import Y` branch counts as a functional fallback (suppresses POSIX-only classification for that import); **any** `try/except ImportError` shape, regardless of handler content, counts as POSIX-only evidence. Both apply only at module-top-level — a guarded import nested inside a function/class/conditional produces no evidence either way. Catches `SyntaxError`/`UnicodeDecodeError`/`OSError`/`ValueError` (the last for CPython's embedded-NUL-byte quirk) **per file**, contributing zero evidence for that one file only (not a skill-wide abort) — final classification is the union of evidence across all files that parsed successfully in that skill | Pure function, one skill's directory at a time; each file within a skill is parsed independently; a parse failure in one skill's files never affects another skill's resolution, and a parse failure in one file never discards real evidence found in a sibling file | Corrected per round 2's two most severe findings and round 3's scoping/aggregation/exception-set gaps |
| `validate_platform_declarations` (new, called from `scripts/registry/crosscheck.py`'s `validate_registry()`) | Compares an explicit `platforms:` override against a fresh derivation for that skill; appends a distinct error string on mismatch, added alongside `validate_registry()`'s existing sibling `_validate_*` checks | Validation layer only — **never raises inside `SkillEntry`/`_parse_skill_entry` resolution itself** | Exact call site named per round 3 — `validate_registry()` is the only function both `cmd_generate` (via `_validate_for_generate`) and `cmd_validate` (via `_validate_all` → `_validate_for_generate`) unconditionally share; naming any other location risks one of the two commands never reaching this check |
| `SkillEntry.platforms: list[str]` (`scripts/registry/models.py`) | Stores the resolved (explicit-override-or-derived) value; resolution never raises on override/derivation mismatch — that's `validate_platform_declarations`'s job | Existing frozen dataclass, new field | Unchanged from revision 2 |
| Fragment-merge/registry-read layer (`scripts/registry/schema.py`) | Resolves `platforms` on every load (generate, validate, install); computes each skill's on-disk path **independently**, inside `_parse_skill_entry`, using the same fallback logic `package_skill._resolve_source_dir` uses (`root / entry.get("path", skill_id)`) — **never by calling `_resolve_source_dir` itself**, since that function calls `parse_registry()` and would recurse back into the very per-skill loop this resolution runs inside of | The one place `cmd_generate`'s write path and `install_skill()`'s read path converge | Round 3 found the revision-3 wording ("resolved the same way `_resolve_source_dir` already does") read as "call that function," which would recurse — corrected to "same logic, computed independently" |
| `install_engine.py`'s platform-check (existing function, extended) | Unchanged from revision 2: hook point before staging/locking and before the `dry_run` short-circuit; `"windows" if sys.platform == "win32" else "posix"` translation | Inside `install_skill()` | |
| `idempotency_store.py`'s guard (existing file, extended) | `try/except ImportError` around `import fcntl`; a new `UnsupportedPlatformError(RuntimeError)` raised inside `mr_lock()` when `fcntl is None`; `main()` catches it and exits `5` with a clean message | Self-contained | Exception type and exit code now specified per round 2 |
| `aggregate_migration_status.py`'s guard (existing file, extended) | Same guard, at the CLI entrypoint only (confirmed sufficient — its only real caller is its own `main()`) | Self-contained | Unchanged from revision 2 |

## APIs

| Endpoint / method | Contract | Consumer(s) | Notes |
|--------------------|----------|-------------|-------|
| `scripts/registry/skills.d/<skill>.yaml`'s optional `platforms:` key | Present → authoritative for enforcement; compared against a fresh derivation by `validate_platform_declarations` (not by resolution itself); a mismatch is a `cmd_generate --check`/`cmd_validate` failure, which CI already blocks merge on (confirmed: `generate-check` is a required `lint-static` prerequisite). Absent → derived value used directly, recomputed on every load | Skill authors, `make generate`, `install_skill()` | Mechanism now precisely specified |
| `platform_detection.derive_platforms(skill_path: Path) -> list[str]` (new, pure function) | AST-parses every `.py` file under `skill_path`, **each file independently**. For a given file, a module-top-level import of a known POSIX-only stdlib module counts as `["posix"]` evidence unless it's inside a genuine `if sys.platform == ...: ... else: ...` branch — **any** `try/except ImportError` shape still counts as POSIX-only evidence, regardless of handler content (purely syntactic rule, safe-direction trade-off). Both the if/else exemption and the try/except non-exemption apply only to a **module-top-level** import statement; an import guarded at any other nesting level (inside a function, class, or conditional block) produces no evidence either way and is out of scope for this detector. A per-file parse/decode/null-byte failure (`SyntaxError`, `UnicodeDecodeError`, `OSError`, or `ValueError` — CPython raises `ValueError`, not `SyntaxError`, for a source file containing an embedded NUL byte) is caught and contributes **zero evidence for that one file only**, with a loud warning; it never aborts the scan of the skill's other files. The skill's final classification is the union of whatever evidence survives across all successfully-parsed files — `["posix"]` if any file contributed POSIX-only evidence, `["posix","windows"]` only if literally no file in the skill contributed any | Every registry read | Corrected per round 3 — both the top-level-only scoping (previously inconsistent between this table and the Components table) and the same-skill aggregation semantics (previously ambiguous between "per file" and "per skill") are now stated precisely, and the exception set now includes `ValueError` for the NUL-byte case |
| `idempotency_store.py`'s `mr_lock()` | Raises `UnsupportedPlatformError(RuntimeError)` if `fcntl is None` (guarded import failed), before attempting any lock operation. `main()` catches this and exits `5` with a clean message; a direct Python-handler-style caller sees the raised exception directly | CLI (`check`/`mark`/`run-if-new`) and direct Python-handler integrators alike | Exception/exit-code contract specified per round 2 |
| `sb install --agent <host> <skill> [--allow-unsupported-platform]` / `install.sh` | Unchanged from revision 2 | End users, CI | |

## Events

None found.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `skills.yaml`'s per-skill entry | `platforms: list[str]` | One entry per skill | `scripts/registry/schema.py`/`models.py` |
| `scripts/registry/skills.d/<skill>.yaml` fragment | `platforms:` key optional | Merged by the existing pipeline | Skill authors (optionally) |

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| A skill's `platforms` resolution, on any registry load | `FRAGMENT_HAS_EXPLICIT_VALUE -> VALIDATED_AS_IS` (never raises here), `FRAGMENT_OMITS_KEY -> DERIVED_VIA_AST_SCAN -> {["posix"] \| ["posix","windows"]}`. A per-file parse failure during derivation is caught and does not propagate | `validate_platform_declarations` runs as a **separate** step, comparing an explicit override against a fresh derivation, and is the only place a mismatch becomes an error | Resolution and validation are now two distinct steps, not one, per round 2's correction |
| An `idempotency_store.py` invocation on an unsupported platform | `MR_LOCK_ENTERED -> GUARD_CHECK -> {PROCEED \| RAISE_UNSUPPORTED_PLATFORM_ERROR}` | CLI path: caught by `main()`, exit `5`. Python-handler path: propagates to the caller directly | Specified per round 2 |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| `platforms` value seen by `make generate`, `cmd_validate`, and `install_skill()` | Strong — same derivation logic, same live file content, every read | Unchanged from revision 2 |
| Explicit override vs. fresh derivation | Compared, not enforced at resolution time — divergence is `validate_platform_declarations`'s finding (called from `validate_registry()`), blocking any `make generate`/`cmd_validate` invocation (same as every other validator sharing that function) and enforced by CI via the required `generate-check` prerequisite. Has no effect on `sb install`/`install_skill()` — resolution itself never raises on it | Corrected per round 3 — the exact call site and blocking boundary are now named, not just asserted |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `derive_platforms()` | Yes — pure function per file, with per-file failure isolation (new) | N/A |
| `validate_platform_declarations` | Yes | N/A |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| AST-scan cost | `derive_platforms` runs across **all** ~50 skills' script trees (27 `.py` files total today, confirmed by direct count) on **every single** `sb install <one-skill>` subprocess invocation, since `install.sh` spawns a fresh process per skill×destination with no cross-process cache benefit from the existing in-process `_registry_raw_cache`. Empirically negligible at 27 files today; **this shape (O(all skills) per subprocess, not O(1))** should be revisited if the registry grows by an order of magnitude | Stated precisely per round 2, not rounded to "negligible" without a growth caveat |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| Detection rule misses a real POSIX dependency not in the known-module list, or a known module imported non-statically | Defaults to `["posix","windows"]` incorrectly — Component 4's per-file guard remains the backstop |
| **New, named third miss shape**: the purely-syntactic rule cannot verify a functional-fallback branch's alternate import is actually *used* — a careless or partial port of the `if sys.platform: ... else: ...` shape could still be broken on Windows despite matching the "counts as portable" pattern | Accepted, disclosed heuristic limitation — behavioral verification is out of proportion for a static registry check |
| **New, named**: a real try/except-based cross-platform fallback (e.g. `except ImportError: import msvcrt as fcntl`) is misclassified as POSIX-only by the now-purely-syntactic rule | A deliberate, safe-direction trade-off — over-restricts rather than under-restricts. A skill author using this idiom must hand-author an explicit override |
| **New, closed**: one skill's malformed `.py` file (mid-edit syntax error, or an embedded NUL byte raising `ValueError` rather than `SyntaxError`) could previously have crashed registry resolution for every skill simultaneously, or silently discarded a sibling file's real POSIX-only evidence within the same skill | Fixed — `derive_platforms()` catches `SyntaxError`/`UnicodeDecodeError`/`OSError`/`ValueError` per file, isolated to that one file's contribution only; the skill's other files' evidence still aggregates in; the permissive default is used only if no file in the skill contributed any evidence |
| `idempotency_store.py` invoked on an unsupported platform | `mr_lock()` raises `UnsupportedPlatformError`; CLI exits `5` with a clean message; a direct Python-handler caller sees the exception directly — no raw traceback either way |
| An explicit override diverges from a fresh derivation | Caught by `validate_platform_declarations` (called from `validate_registry()` in `crosscheck.py`), blocking any `make generate`/`cmd_validate` invocation and enforced by CI via the required `generate-check` prerequisite. No effect on `sb install`/`install_skill()` |
| Host that never calls `install_skill()` uses a POSIX-only skill on Windows | Zero protection from the install gate; `mr_lock()`'s guard is the only universal backstop | Unchanged from revision 2 |
| `--allow-unsupported-platform` used in a scripted/CI context | Effectively silent in practice; accepted trade-off for the human-invoked case | Unchanged from revision 2 |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `make generate --check`/`cmd_validate` failure from `validate_platform_declarations` | A distinct, named error — override-vs-derivation drift — separate from the existing file-diff mechanism |
| `derive_platforms()`'s per-file parse-failure warning | Names the specific file and skill, so a WIP syntax error in one skill doesn't silently and invisibly degrade its own classification |
| `idempotency_store.py` exit code `5` | Platform-unsupported, distinct from codes 0-4 |

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 0 | Tests: purely-syntactic detection-rule tests (bare `try/except ImportError` → POSIX-only regardless of handler content, including the `import msvcrt as fcntl` case now explicitly classified POSIX-only and documented as the accepted trade-off; `if sys.platform: ... else: ...` → not POSIX-only; a guarded import nested inside a function body → no evidence either way, out of scope); **mixed-file same-skill aggregation test** (one file has real unconditional POSIX-only evidence, a sibling file in the same skill has a syntax error → skill still correctly classifies `["posix"]`, the broken sibling's failure doesn't discard the first file's evidence); **cross-skill isolation test** (one skill's malformed `.py` file does not affect another skill's classification, does not crash the run); **NUL-byte fixture test** (a `.py` file containing an embedded NUL byte raises `ValueError`, is caught, contributes no evidence, doesn't crash); `validate_platform_declarations` unit tests, calling it exactly as wired into `validate_registry()` (override matches derivation → clean; mismatch → distinct error, verified to actually fail both `cmd_generate --check` and `cmd_validate`, not just the file-diff); `mr_lock()`'s `UnsupportedPlatformError`/exit-`5` test, both CLI and direct-call paths, under simulated `sys.platform == "win32"`; every-read consistency test (generate/validate/install all resolve the same value); `sys.platform` translation test; dry-run coverage test | No flag |
| 1 | `make generate` once repo-wide with explicit `platforms: [posix]` overrides pre-added for `pr-gatekeeper`/`migration-program-manager` (Phase 0's gating test already requires the corrected auto-detector to classify both correctly independently — the override is defense-in-depth/explicitness, not load-bearing); named expected-classification checklist, diffed and justified before merge. Land the fragment-merge/derivation fix, `validate_platform_declarations`, the `install_engine.py` gate, both guarded-import fixes (including `mr_lock()`'s new exception/exit-code), and doc updates (`docs/skill-framework/shared/terminology-glossary.md` for the `platforms` glossary entry, `docs/agent-compatibility.md`'s disclaimer) | Merge gate: both `loop-task-implementer` review lenses clean, `make lint-python`, `make generate --check`/`cmd_validate` clean, full test suite green |
| 2 (future, out of scope) | Per-skill Windows CI smoke testing; a machine-checkable signal for scripted `--allow-unsupported-platform` use | Explicitly deferred |

## Open questions

None — round 4 (SRE, final) confirmed all four of round 3's findings genuinely resolved by direct code
trace. The one non-blocking suggestion it surfaced (a bare `RecursionError` from pathologically deep AST
nesting, not caught by the current exception set) is an accepted residual limitation, not a gap requiring
further revision — narrower and far less realistic than the NUL-byte case the exception set was built to
close, and consistent with this design's other disclosed, accepted heuristic limitations.
