# Change Impact Report — B2: lightweight ticket → plan path for small tasks

**Assessment target:** `luckyrjain/software-builder`, proposed state (design revision 10, "Ready with open
questions")
**Coverage status:** COMPLETE
**Criticality:** High

Not because the code surface is large — after 10 rounds of review it's the smallest form the mechanism has
taken (~130–160 lines in one already-small, already-heavily-shared module) — but because this is the
**first-ever conditional exception** carved into `implementation-planner`'s previously-unconditional
"Required evidence" contract, a shared-skill contract change, not a mechanical/additive-only change. The
blast radius is narrow; the *precedent* it sets is wide.

## Change classes

- `contract-change` — `implementation-planner`'s "Required evidence" (`SKILL.md:25-28`,
  `workflow/plan.md:19-21`) goes from unconditional to conditional for the first time.
- `schema-addition` — `implementation_plan` v1's registered field set gains one member (`planning_path`),
  on two independently-enforced surfaces (`PLAN_FIELDS` in code, `fields`+`payload_types` in the registry).
- `new-validation-logic` — `_validate_planning_path`, path normalization, and a CI/permissions/governance/
  dependency-manifest denylist are new, non-trivial validation code in a module with no precedent for this
  shape of content-aware gate.
- `documentation-only` (Fix 11 specifically) — the Condition 4 residual-risk disclosure is prose, zero code.

## Impacted repositories

`luckyrjain/software-builder` only. Single-repository change; no `external_dependencies` implied.

## Impacted services / components

| Component | Impact | Notes |
|-----------|--------|-------|
| `scripts/implementation_plan.py` | Direct, additive | New constants, 2 new helper functions, 1 new validator function, `PLAN_FIELDS` entry, 1 carve-out in `validate_implementation_plan`'s existing field-diff logic, 1 new key in `build_implementation_plan`'s output literal. No existing function signature changes; no existing function's behavior changes for a `FULL`-mode or pre-existing plan. |
| `skills.yaml` / `scripts/registry/composition_contracts.yaml` | Direct, additive | `implementation_plan` artifact schema gains 1 field on 2 registration surfaces (`fields`, `payload_types`) that must move together — confirmed via `artifact_contracts.py:141-150`'s equality check between them. |
| `scripts/plan_state_store.py` | **None** — confirmed, not assumed | Repo-wide grep for `implementation_plan` imports outside `scripts/tests/` finds exactly one non-test consumer: `plan_state_store.py`, which calls `initial_plan_execution_state`/`validate_implementation_plan`/`canonical_plan_digest` as opaque functions and duplicates none of their internals. The design's final form (after round 6 found and reverted an `EXECUTION_STATE_FIELDS` attempt) makes zero changes to this file, `EXECUTION_STATE_FIELDS`, or `reference/state-schema.yaml` — the module boundary genuinely holds; this was the one thing explicitly asked to be re-confirmed and it checks out. |
| `skills/implementation-planner/` (SKILL.md, workflow/plan.md, new reference/lightweight-path.md, reference/lazy-load-index.md) | Direct | The contract-change surface itself. |
| `skills/loop-task-implementer/workflow/orchestrator.md` | Direct, additive only | One sentence near the existing size-threshold section, one sentence distinguishing the lightweight path from the legacy `implementation_task` bypass. No change to review lenses, circuit breakers, or dispatch logic. |
| `scripts/tests/test_implementation_planner_integration.py` | Direct | `test_implementation_plan_v1_contract_fields`'s expected-field list needs updating in lockstep with the schema change, or CI fails immediately — this is by design (the pinned test is the drift guard). |
| Every other skill/consumer of `implementation_plan` (`loop-task-implementer` itself, any future consumer) | Indirect, none observed | `implementation_plan`'s consumer contract (`plan_set_id`/`plan_id`/`readiness`/`tasks`/`execution_waves` etc.) is unchanged; `planning_path` is a new field nothing existing reads, so nothing existing can break from its mere presence. `loop-task-implementer`'s own `SKILL.md:17` ("accepts a validated `implementation_plan`") doesn't enumerate fields it depends on beyond what already exists. |

## Impacted contracts

| Contract | Before | After | Compatibility |
|----------|--------|-------|---------------|
| `implementation_plan` v1 schema (registry + `PLAN_FIELDS`) | 13 fields, all required, strict two-way check | 14 fields; `planning_path` required for the registry's producer-emission check, but *not* required for `validate_implementation_plan`'s missing-field check on an already-existing plan (deliberate asymmetry — see Required tests) | Backward compatible for every already-persisted `implementation_plan` artifact; forward-only for fresh producer emissions, which always populate the field unconditionally |
| `implementation-planner`'s "Required evidence" (doc contract, not code) | Unconditional: 3 real reports (or valid stubs matching their real schema) always required | Conditional: a caller-asserted `LIGHTWEIGHT` stub, matching a fixed template and passing code-enforced gates, is now also accepted | The unconditional path is unchanged and remains the default; this is purely additive optionality |
| `repository_evidence.planning_path` (new, optional caller input to `build_implementation_plan`) | Did not exist | New optional key, mirrors `estimated_scope`'s existing pattern exactly | No existing caller passes this key, so no existing caller's behavior changes |

## Impacted data

None. No schema/table/persisted-record change beyond the `implementation_plan` artifact schema already
covered above. No PII, no secrets, no data migration.

## Impacted dependencies

None new. No new third-party package, no new external service call. `implementation_plan.py`'s existing
imports (`hashlib`/`json`-adjacent via `assessment_target.py`, `validation_primitives`) are sufficient for
every new function in this design — confirmed by re-reading the actual proposed code, which uses only
already-imported names (`Mapping`, `non_empty_str`, etc.) plus plain string/set operations.

## Impacted owners

`CODEOWNERS` already covers every touched path via existing wildcard entries — `/scripts/` and
`/skills.yaml` are both already explicit rows (confirmed by direct read); `skills/implementation-planner/`
and `skills/loop-task-implementer/` fall under the root `*` default owner. No `CODEOWNERS` edit needed
(matches this session's own A6 precedent for the same situation).

## Required tests

1. **Atomic-rollout regression test** (the design's own Phase 0 requirement, elevated here to a named
   required test because its absence was a real, round-3/round-7-adjacent failure class in this review's
   own history): a test that builds a `FULL`-mode plan through the unmodified default path and confirms its
   output is byte-identical to pre-change behavior except for the addition of
   `planning_path: {"mode": "FULL", "eligibility_category": None, "asserted_by": None}`.
2. **Resume-compatibility test against a real historical artifact**: load an actual pre-existing committed
   plan JSON (e.g. `docs/superpowers/specs/2026-09-28-b1-clarify-step-implementation-plan.json`, which
   genuinely lacks `planning_path`) through `validate_implementation_plan` post-change and confirm it still
   validates — the direct regression test for the exact bug class round 1 and round 3/6 each found in
   different forms.
3. **`LIGHTWEIGHT` positive/negative validation matrix**: valid category / invalid category / missing
   `asserted_by` / >3 `target_paths` / a denylisted path in each of its variant forms (`./`-prefixed,
   backslash-separated, case-varied, a dependency-manifest basename, a `tests/fixtures/`-exempted manifest
   path) / a `FULL`-mode plan with non-null `eligibility_category` or `asserted_by` (must reject).
4. **Plan-identity uniqueness test**: two `LIGHTWEIGHT` builds sharing `eligibility_category` and
   `target_paths` but different `title` text produce different `plan_id`; identical stub content produces
   the same `plan_id` (idempotent retry).
5. **Resume-digest stability test**: two `build_implementation_plan` calls with byte-identical
   `title`/`target_paths`/`asserted_by`/`eligibility_category` produce the same `canonical_plan_digest` —
   the direct regression test for the round-4/5 bug class (a session/run-id-bearing field silently entering
   the resume digest).
6. **`ELIGIBILITY_CATEGORIES` doc-parity test**: every value in the code constant appears, backtick-wrapped,
   in `reference/lightweight-path.md` — matching `test_run_log.py`'s established convention exactly, not the
   structurally different `test_plan_execution_state.py` convention (the design's own round-3 citation
   correction).
7. **Registry schema regeneration check**: `test_implementation_plan_v1_contract_fields`'s expected list
   updated and passing; `make generate --check`-equivalent (or the repo's actual generated-file-drift
   lint) clean for `composition_contracts.yaml`.

## Operational impacts

| Impact | Detail |
|--------|--------|
| **Hard sequencing constraint on the merge itself** | The design's Rollout Phase 0 requires the registry schema change and the `implementation_plan.py` code change to land in the *same* commit/PR — not merely "close together." Confirmed why: `artifact_contracts.py`'s producer-emission check treats the registered schema as a strict required-field set for any fresh `SUCCESS` envelope; if the schema change merged first, alone, *every* `implementation-planner` run (`FULL` mode included, not just `LIGHTWEIGHT`) would fail that check in the gap before the code change lands, since the schema would require a field the code doesn't yet emit. This is a genuine deployment-ordering risk, not a style preference — flagged as the primary operational risk of this change. |
| CI/lint surface | `make generate` regeneration is a known, established step this session has hit before (A4, B1) — sometimes blocked by the host's own auto-mode classifier when the Orchestrator itself attempts it, requiring the user to run it directly. Flag this as an expected, not novel, friction point for the implementation phase, not a new risk this ticket introduces. |
| Documentation drift risk | `reference/lightweight-path.md` (prose eligibility categories) and `ELIGIBILITY_CATEGORIES` (code) can drift without the new parity test (Required test 6) — already covered above. |
| No rollback complexity | The change is purely additive at every layer (new optional field, new optional doc path, new additive orchestrator sentences); reverting the commit is a clean revert with no data migration in either direction. |

## Review triggers

None of the 8 fixed specialist categories (`api`, `database`, `security`, `performance`, `capacity`,
`observability`, `resilience`, `dependency_upgrade`) are triggered:

- No API surface change (no new endpoint, no external contract).
- No database/schema change.
- **Security**: considered and explicitly not triggered as a *specialist* review, because the architecture
  review + 10 rounds of adversarial design review already functioned as the security review this change
  needed — the eligibility-bypass/self-certification risk, the CI-permissions-denylist gap, and the
  dependency-manifest gap were all found and closed by that process, not deferred to a later specialist
  pass. Re-triggering a fresh `security-review` here would re-litigate ground already covered at
  higher intensity than a standard specialist pass provides.
- No capacity/observability/resilience/dependency-upgrade surface (this change doesn't touch runtime
  capacity planning, monitoring, fault-tolerance behavior, or a dependency manifest itself — it *adds a
  denylist protecting* dependency manifests, which is the opposite of a dependency upgrade).

## Unknowns

1. **Whether `make generate` will run cleanly for the Orchestrator directly, or require the user to run it**
   (per this session's own A4/B1 precedent of the host's auto-mode classifier sometimes blocking this
   specific command) — not knowable in advance, disclosed as an execution-time contingency, not a design
   gap.
2. **The exact literal content of `reference/lightweight-path.md`'s prose** is specified in shape (allowlist
   categories, stub templates, code-enforced gates, Condition 4 disclosure) by the design but not written
   verbatim in this change-impact report — normal for a change-impact analysis, to be produced during
   implementation per the design's own literal templates.

## Evidence refs

- `docs/superpowers/specs/2026-09-29-b2-lightweight-plan-path-architecture-review.md`
- `docs/superpowers/specs/2026-09-29-b2-lightweight-plan-path-design.md` (revision 10)
- `scripts/implementation_plan.py` (direct read, full file, across 10 review rounds)
- `scripts/plan_state_store.py` (direct read, confirms zero required changes)
- `scripts/registry/artifact_contracts.py`, `scripts/registry/composition_contracts.py` (registry
  enforcement mechanics)
- `skills.yaml`, `scripts/registry/composition_contracts.yaml` (current schema, pre-change)
- `CODEOWNERS` (confirms existing wildcard coverage)
- `skills/implementation-planner/SKILL.md`, `workflow/plan.md`, `reference/` directory listing
- `skills/loop-task-implementer/workflow/orchestrator.md`, `SKILL.md`
- `docs/superpowers/specs/2026-09-28-b1-clarify-step-implementation-plan.json` (real historical artifact
  used for the resume-compatibility test's grounding)
