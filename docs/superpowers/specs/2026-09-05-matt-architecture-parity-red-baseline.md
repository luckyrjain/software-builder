# Matt architecture parity bridge — RED baseline

Recorded by Task 1 ("Establish the RED parity baseline") of the [Matt
Architecture Parity Bridge Implementation
Plan](../plans/2026-09-05-matt-architecture-parity-bridge.md), arguing from
[the approved spec](2026-09-05-matt-architecture-parity-bridge.md) (R1-R5,
R7-R9). This document is the evidence artifact that the current
`codebase-architecture-review` / `module-design` catalog does not yet
require Matt-style depth, deletion-test, or visual-model behaviors. Tasks
2-6 make these RED cases pass; this document is not edited to make that
happen — it is the frozen record of what failed and why, before the fix.

- Date recorded: 2026-09-07T15:58:40Z
- `HEAD` at recording time: `1e0698773b0affb97255352472ace9327113d36f`
- Working tree: `/Users/luckyjain/Projects/software-builder/.claude/worktrees/elegant-poincare-4fb7b5`

## Command 1

```
python3 -m pytest scripts/tests/test_codebase_architecture_foundation.py -q
```

Exit code: `1` (3 failed, 14 passed)

Failing tests and failure messages:

- `test_matt_depth_and_deletion_doctrine_is_explicit`
  ```
  AssertionError: assert '## Module depth' in '# Codebase Design Principles\n\nThis doctrine defines the shared terms and decision rules for evaluating or changing...'
  ```
  `docs/skill-framework/shared/codebase-design-principles.md` has none of the
  headings `## Module depth`, `## Interface surface`, `## Deletion test`,
  `## Real versus hypothetical seams`, and neither of the phrases `shallow
  pass-through` / `deep module`.

- `test_architecture_report_requires_matt_visual_candidate_fields`
  ```
  AssertionError: assert 'Recommendation strength' in '# CODEBASE_ARCHITECTURE_REVIEW.md format\n\n**Normative.** [workflow/report.md](../workflow/report.md) emits this str...'
  ```
  `codebase-architecture-review/reference/report-format.md` has none of
  `Recommendation strength`, `Dependency category`, `Before model`, `After
  model`, `Deletion test`, `architecture-review-20260905T120000Z.html`.

- `test_module_design_evaluates_depth_and_deletion_test`
  ```
  AssertionError: assert 'interface surface' in '---\nworkflow_version: 1.0\nphase: design\nproduces:\n  - module_contract\n...'
  ```
  `module-design/workflow/design.md` has none of `interface surface`,
  `deletion test`, `implementation depth`.

Pre-existing foundation assertions in this file (the other 14 collected
tests) remained green.

## Command 2

```
python3 -m scripts.evals --skill codebase-architecture-review
```

Exit code: `1` (`error: 2 eval case(s) failed`)

Case results:

```
ok: codebase-architecture-review/evidence-gated-zero-candidate-report
ok: codebase-architecture-review/global-happy
ok: codebase-architecture-review/global-adversarial
FAIL: codebase-architecture-review/deepening-quality
ok: codebase-architecture-review/no-automatic-refactor
FAIL: codebase-architecture-review/deepening-report
ok: codebase-architecture-review/golden-injection
ok: codebase-architecture-review/golden-report
```

`codebase-architecture-review/deepening-quality` (Tier 2, new) failure
messages:

```
event_order: event 'candidate_retained' not found at or after position 2 (expected order ['repository_read', 'history_read', 'candidate_retained', 'report_write', 'outcome'])
expected tool 'visual_report_write' to be called
event_data_equals: event 'report_write' missing field path 'recommendation_strength'
```

`codebase-architecture-review/deepening-report` (Tier 3, new) failure
messages:

```
missing field path: 'top_recommendation.recommendation_strength'
missing required field path: 'top_recommendation.dependency_category'
missing required field path: 'top_recommendation.before_model'
missing required field path: 'top_recommendation.after_model'
missing required field path: 'top_recommendation.deletion_test'
```

All pre-existing `codebase-architecture-review` cases
(`evidence-gated-zero-candidate-report`, `global-happy`, `global-adversarial`,
`no-automatic-refactor`, `golden-injection`, `golden-report`) stayed `ok`,
including the read-only / no-write / no-automatic-refactor assertions
embedded in the two new fixtures themselves.

## Command 3

```
python3 -m scripts.evals --skill module-design
```

Exit code: `1` (`error: 2 eval case(s) failed`)

Case results:

```
ok: module-design/contract-boundary-read-only
ok: module-design/global-happy
ok: module-design/global-adversarial
ok: module-design/contract-boundary
FAIL: module-design/deep-module-quality
FAIL: module-design/deep-module-contract
ok: module-design/golden-contract
ok: module-design/golden-injection
```

`module-design/deep-module-quality` (Tier 2, new) failure message:

```
event_data_equals: no event labeled 'design_comparison' found for path 'deep_design.provider_seam'
```

`module-design/deep-module-contract` (Tier 3, new) failure messages:

```
missing required field path: 'interface_surface'
missing required field path: 'deletion_test'
missing required field path: 'implementation_depth'
missing required field path: 'design_comparison'
```

All pre-existing `module-design` cases (`contract-boundary-read-only`,
`global-happy`, `global-adversarial`, `contract-boundary`, `golden-contract`,
`golden-injection`) stayed `ok`, including the read-only assertions embedded
in the two new fixtures themselves.

## `event_order` / `event_data_equals` unit tests (expected to pass immediately)

Per the controller's ruling for this task, `event_order` and
`event_data_equals` are real, working assertion types implemented in this
same task in `scripts/evals/transcript.py` — only the *doctrine* and
*quality-fixture* RED cases above are deferred to Tasks 2-6. The four direct
unit tests specified in the task brief were run and passed on first
implementation:

```
python3 -m pytest scripts/tests/test_evals.py -k "event_order or event_data_equals" -q
....
4 passed, 15 deselected in 0.04s
```

- `test_transcript_event_order_accepts_subsequence` — PASSED
- `test_transcript_event_order_rejects_out_of_order_event` — PASSED
- `test_transcript_event_data_equals_accepts_nested_value` — PASSED
- `test_transcript_event_data_equals_rejects_missing_field` — PASSED

## Collateral RED side effects outside this task's file scope (not repaired)

Running the full suite (`python3 -m pytest scripts/tests -q`) after adding
the two new Tier-2 transcript fixtures and two new Tier-3 golden fixtures
shows those additions also flip four *pre-existing, out-of-scope* tests to
RED, because they assert whole-repository invariants ("every eval case
passes", "there are exactly N golden fixtures") that these deliberately
failing fixtures now violate:

- `scripts/tests/test_evals.py::test_evals_pass_on_repository`
- `scripts/tests/test_evals_tier2.py::test_transcript_cases_pass_on_repository`
- `scripts/tests/test_evals_tier2.py::test_tier_filter_excludes_opposite_tier`
  (hardcoded `len(tier2_ids) == 8`; now 10)
- `scripts/tests/test_evals_tier3.py::test_golden_fixtures_load`
  (hardcoded `len(cases) == 79`; now 81)
- `scripts/tests/test_evals_tier3.py::test_golden_cases_pass_on_repository`

None of these three files (`test_evals_tier2.py`, `test_evals_tier3.py`) are
in this task's brief `Files:` list — only
`scripts/tests/test_codebase_architecture_foundation.py`,
`scripts/evals/transcript.py`, and `scripts/tests/test_evals.py` are — so
they were left untouched rather than repaired, consistent with "record the
exact failure list rather than repairing the failures in this task." Full
suite result: `8 failed, 2263 passed in 90.02s` (the 3 foundation failures +
2 codebase-architecture-review eval failures + 2 module-design eval failures
above, plus this section's `test_golden_fixtures_load` exact-count
assertion). Tasks 2-6 (or whichever task changes these fixture counts next)
should update the two hardcoded counts once the new fixture set is
intentional and stable.

## Skill-doctrine confirmation (why these are genuine RED, not typos)

Direct inspection at `HEAD` confirms the missing terms are genuinely absent,
not a copy/paste mismatch:

```
$ grep -n "^## " docs/skill-framework/shared/codebase-design-principles.md
## Contract surface
## Change locality
## Behavioral leverage
## Seam
## Adapter
## Cohesion
## Coupling
## Dependency direction
## Test surface
## Abstraction cost
## AI navigability
## Evidence threshold
```

No `## Module depth`, `## Interface surface`, `## Deletion test`, or `##
Real versus hypothetical seams` heading exists. `codebase-architecture-review/reference/report-format.md`
and `module-design/workflow/design.md` were read in full and contain no
occurrence of the required phrases either.
