# Engineering decision discovery bridge — RED baseline

Recorded by Task 1 ("Establish the RED decision-discovery baseline") of the
[Engineering Decision Discovery Bridge Implementation
Plan](../plans/2026-09-05-engineering-decision-discovery-bridge.md) (Child
Plan B), arguing from R6 of [the approved
spec](2026-09-05-matt-architecture-parity-bridge.md). This document is the
evidence artifact that no route, skill package, registry/artifact contract,
or eval admission currently exists for `engineering-decision-discovery`.
Tasks 2-4 make these RED cases pass; this document is not edited to make
that happen — it is the frozen record of what failed and why, before the
fix.

- Date recorded: 2026-09-08T06:00:58Z
- `HEAD` at recording time: `33a2df02942ff6e1c7e6b1a84ca37feaf1482f54`
- Working tree: `/Users/luckyjain/Projects/software-builder/.claude/worktrees/decision-discovery-bridge-childb`

## Command 1

```
python3 -m pytest scripts/tests/test_engineering_decision_discovery.py -q
```

Exit code: `1` (`9 failed`)

Failing tests and failure messages:

- `test_decision_discovery_has_a_dedicated_owner[Grill me on this architecture decision.]`
- `test_decision_discovery_has_a_dedicated_owner[Challenge my plan and question my assumptions.]`
- `test_decision_discovery_has_a_dedicated_owner[Stress-test this engineering decision.]`
- `test_decision_discovery_has_a_dedicated_owner[What decisions are missing before we implement this design?]`
- `test_decision_discovery_has_a_dedicated_owner[Help me decide between these module designs.]`

  All five parametrized cases fail identically:
  ```
  AssertionError: DispatchResult(status='no_match', candidates=())
  assert 'no_match' == 'selected'
  ```
  No routing rule currently matches any of these prompts to
  `engineering-decision-discovery` (the skill and its `routing.patterns`
  fragment do not exist yet — Task 3, Step 1).

- `test_decision_discovery_skill_is_not_yet_registered`
  ```
  AssertionError: assert 'engineering-decision-discovery' in {'api-design-review': SkillEntry(...), ...}
  ```
  `skills.yaml` has no `engineering-decision-discovery` entry (Task 3, Step 1
  adds `scripts/registry/skills.d/engineering-decision-discovery.yaml`).

- `test_decision_frontier_transcript_fixture_is_admitted_and_passes`
  ```
  AssertionError: ['skill not in skills.yaml']
  assert False
  ```
  `evals/transcripts/engineering-decision-discovery/decision-frontier.yaml`
  loads and its recorded events already satisfy its own `event_order` /
  `tool_not_called` / `event_data_equals` / `outcome_status` assertions
  (verified directly against `run_transcript_case`); the eval harness's
  `admit_case` (`scripts/evals/__main__.py`) still rejects it because
  `engineering-decision-discovery` is not a registered skill.

- `test_decision_record_golden_fixture_is_admitted_and_passes`
  ```
  AssertionError: ['skill not in skills.yaml']
  assert False
  ```
  Same admission gate; `evals/golden/engineering-decision-discovery/decision-record.yaml`'s
  recorded output already satisfies its own `field_equals` / `require_pattern`
  / `forbid_pattern` assertions.

- `test_unattended_execution_blocks_on_unresolved_frontier`
  ```
  AssertionError: ['skill not in skills.yaml']
  assert False
  ```
  In-memory transcript case run through the same `admit_case` path; same
  admission gate. Per the brief, this unattended-BLOCKED scenario is
  exercised in-memory rather than as a committed
  `evals/transcripts/engineering-decision-discovery/unattended-block.yaml`
  fixture, because Task 4's file list `Create`s that exact path — Task 1
  committing it first would leave Task 4 nothing to create.

## Command 2

```
python3 -m scripts.evals --skill engineering-decision-discovery
```

Exit code: `1` (`error: 2 eval case(s) failed`)

Output:

```
  - skill not in skills.yaml
  - skill not in skills.yaml
error: 2 eval case(s) failed
FAIL: engineering-decision-discovery/decision-frontier
FAIL: engineering-decision-discovery/decision-record
```

Both fixtures are discovered (they parse and self-validate) and both fail
admission for the same reason: `engineering-decision-discovery` is not a
registered skill yet.

## Collateral RED side effects outside this task's file scope (not repaired)

Following the same rule the prior RED baseline task recorded
(`docs/superpowers/specs/2026-09-05-matt-architecture-parity-red-baseline.md`,
"Collateral RED side effects..."): adding one new Tier-2 transcript fixture
and one new Tier-3 golden fixture for a not-yet-registered skill also flips
pre-existing, out-of-scope tests that assert whole-repository invariants
("every eval case passes", "there are exactly N golden/transcript fixture
ids"). None of the following files are in this task's brief `Files:` list,
so — consistent with "record the exact failure list rather than repairing
the failures in this task" — they are left untouched rather than repaired:

- `scripts/tests/test_evals.py::test_evals_pass_on_repository`
  ```
  AssertionError: [EvalResult(skill='engineering-decision-discovery', case_id='decision-frontier', passed=False, messages=['skill not in skills.yaml']), EvalResult(skill='engineering-decision-discovery', case_id='decision-record', passed=False, messages=['skill not in skills.yaml'])]
  ```
- `scripts/tests/test_evals_tier2.py::test_transcript_cases_pass_on_repository`
  ```
  AssertionError: [EvalResult(skill='engineering-decision-discovery', case_id='decision-frontier', passed=False, messages=['skill not in skills.yaml'])]
  ```
- `scripts/tests/test_evals_tier2.py::test_tier_filter_excludes_opposite_tier`
  (hardcoded `len(tier2_ids) == 10`; now 11 — the new `decision-frontier`
  case_id is admitted as a *result*, just a failing one, so it is still
  counted)
- `scripts/tests/test_evals_tier3.py::test_golden_fixtures_load`
  (hardcoded `len(cases) == 81`; now 82)
- `scripts/tests/test_evals_tier3.py::test_golden_cases_pass_on_repository`
  ```
  AssertionError: [EvalResult(skill='engineering-decision-discovery', case_id='decision-record', passed=False, messages=['skill not in skills.yaml'])]
  ```

Whichever later task (Task 3, once the skill is registered, or Task 4, once
eval admission is formally wired up) changes these fixture counts and
admission results next should update the two hardcoded counts and confirm
the three "pass on repository" tests are green again once the skill exists.

Full-suite result at this commit's working tree:
`python3 -m pytest scripts/tests -q` → `14 failed, 2267 passed in 83.41s`
(the 9 failures in `test_engineering_decision_discovery.py` above, plus the
5 collateral failures in this section — the two exact-count assertions are
pre-existing tests that now fail rather than new tests, so they add to the
failure count without changing the total collected count). Baseline
immediately before Task 1 (recorded in
`.superpowers/sdd/2026-09-05-engineering-decision-discovery-bridge/progress.md`):
`2272 passed`. Reconciling: `2272` (baseline) `+ 9` (new tests in this file)
`= 2281` total collected; of those, `14` fail and `2267` pass, matching the
run above (`2267 + 14 = 2281`).

## A deliberate, minimal, non-brief change: `scripts/evals/transcript.py`'s `EVENT_TYPES`

The brief's Step 2 event ordering requires `decision_frontier`,
`recommendation`, and `human_decision` as first-class event `type` values —
`event_order`/`event_data_equals` label every non-`tool` event by its bare
`type` (`_event_label` in `scripts/evals/transcript.py`), so collapsing all
three onto the existing `gate` type would make `decision_frontier`,
`recommendation`, and `human_decision` indistinguishable to `event_order`,
which the brief's exact required ordering
(`[repository_read, decision_frontier, recommendation, human_decision, decision_frontier]`)
depends on being distinguishable.

Before this task, `EVENT_TYPES` was the closed set `{tool, gate, outcome}`;
`_parse_event` (used by `load_transcript_fixtures`, which scans *all* of
`evals/transcripts/` unfiltered, not just this skill's) raises `ValueError`
on any other type. Authoring `decision-frontier.yaml` with the brief's
literal event types, without extending this set, would have made
`load_transcript_fixtures` raise for the *entire* transcript tree — crashing
every test and CLI invocation that loads transcripts unfiltered (confirmed:
15 other test files call `load_transcript_fixtures` or `scripts.evals`
un-scoped), not just this skill's own RED cases. That is a materially larger
and less honest RED signal than "the skill doesn't exist" — it would read as
"the eval harness is broken," including for skills that have nothing to do
with this plan.

`scripts/evals/transcript.py` was therefore modified (not listed in the
brief's `Files:` section) to extend `EVENT_TYPES` to
`{tool, gate, outcome, decision_frontier, recommendation, human_decision}`.
This is additive and backward-compatible (three new frozenset members; no
existing assertion type, event type, or fixture is affected — confirmed by
the full-suite run above showing no failures traceable to this change). It
does not implement any decision-discovery behavior; it only admits the
vocabulary the brief's own required fixture content needs to parse. The
remaining, and correct, RED reason for both new fixtures is unchanged:
`engineering-decision-discovery` is not a registered skill (`admit_case`:
`"skill not in skills.yaml"`).

## Files added/changed in this task

- `scripts/tests/test_engineering_decision_discovery.py` (new)
- `evals/transcripts/engineering-decision-discovery/decision-frontier.yaml` (new)
- `evals/golden/engineering-decision-discovery/decision-record.yaml` (new)
- `scripts/evals/transcript.py` (`EVENT_TYPES` extended; see above — deviation from the brief's file list, justified above)
- `docs/superpowers/specs/2026-09-05-engineering-decision-discovery-red-baseline.md` (this file, new)
