# Task 5 — Routing and escalation report

> **Final status (branch as submitted in PR #201):** the blockers recorded below were intermediate.
> Later tasks added the missing Framework references, registry rows, generated adapters, and Make
> targets. At the PR head `make generate-check`, `make validate-registry`, `make validate-evals`,
> `make lint-static`, and the full `scripts/tests` suite all pass. Read the command output below as a
> record of the state at the time this task ran, not of the branch.

## Scope completed

- Added deterministic dispatcher rules for the registered `codebase-architecture-review` and
  `module-design` skills. The ready-PRD/system-design overlap now excludes `prd-architect`, preserving
  the existing `system-design` owner.
- Made the central routing table and canonical disambiguation explicit for existing-code architecture
  friction, proposed architecture correctness, implementation design, one code-level module/interface/seam,
  caller-supplied debt backlog ranking, and current-state domain reconstruction.
- Updated the concise boundary tables in `architecture-review`, `system-design`, and
  `domain-comprehension` so their local routes remain central-table subsets.
- Added the three registered forward escalation edges and corresponding reverse rows:
  `codebase-architecture-review → module-design` for a selected code-level candidate, and
  `module-design → system-design` / `module-design → architecture-review` only for scope expansion.
- Added the requested foundation routing-presence assertion and two ambiguous dispatcher cases.
- Did not modify `skills.yaml`, artifact/capability registry sources, Make targets, transcripts, goldens, or
  generated projections. No `engineering-decision-discovery` edge was added.

## Focused verification outputs

Command:

```text
python3 -m pytest -q scripts/tests/test_routing_sync.py
```

Output:

```text
....                                                                     [100%]
4 passed in 0.55s
```

Command:

```text
python3 -m pytest -q scripts/tests/test_codebase_architecture_foundation.py
```

Output:

```text
.........                                                                [100%]
9 passed in 0.61s
```

Command:

```text
python3 - <<'PY'
from pathlib import Path
from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
root = Path('.')
expected = {
    'Review this existing codebase architecture and find evidence-backed refactoring opportunities.': 'codebase-architecture-review',
    'Design the contract and seam for this one code-level payment module.': 'module-design',
    'Review this proposed architecture and its failure modes before implementation.': 'architecture-review',
    'Turn this ready PRD into an implementation-oriented system design.': 'system-design',
}
for prompt, owner in expected.items():
    result = dispatch_prompt(root, load_registry(root), prompt)
    assert result.status == 'selected', result
    assert result.owner == owner, result
    print(f'{owner}: PASS')
PY
```

Output:

```text
codebase-architecture-review: PASS
module-design: PASS
architecture-review: PASS
system-design: PASS
```

Command:

```text
python3 - <<'PY'
from pathlib import Path
from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file, require_mapping
root = Path('.')
registry = load_registry(root)
raw = require_mapping(load_unique_yaml_file(root / 'evals/ambiguous/cases.yaml'), 'ambiguous cases')
for case in raw['cases']:
    result = dispatch_prompt(root, registry, case['prompt'])
    assert result.status == case['expected_status'], (case, result)
    assert sorted(result.candidates) == sorted(case['expected_candidates']), (case, result)
print(f"ambiguous dispatch: PASS ({len(raw['cases'])} cases)")
PY
```

Output:

```text
ambiguous dispatch: PASS (40 cases)
```

Command:

```text
python3 - <<'PY'
from pathlib import Path
from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix
from scripts.registry.load import load_registry
root = Path('.')
text = (root / 'docs/skill-framework/shared/cross-skill-escalation.md').read_text()
edges = parse_forward_escalation_matrix(text)
required = {
    ('codebase-architecture-review', 'module-design'),
    ('module-design', 'system-design'),
    ('module-design', 'architecture-review'),
}
actual = {(source, target) for _trigger, source, target in edges}
assert required <= actual, required - actual
registry = load_registry(root)
for source, target in required:
    assert target in registry.skills[source].composition.escalation_targets, (source, target)
assert 'engineering-decision-discovery' not in text
for phrase in (
    'codebase-architecture-review selects one code-level candidate',
    'module-design expands beyond one module into components/APIs/events/data',
    'module-design expands into an architecture-wide correctness/risk/scale decision',
):
    assert phrase in text, phrase
print(f'escalation checks: PASS ({len(edges)} forward rows; 3 required edges; no forbidden edge)')
PY
```

Output:

```text
escalation checks: PASS (95 forward rows; 3 required edges; no forbidden edge)
```

Command:

```text
git diff --check
```

Output:

```text
(no output; passed)
```

## Out-of-scope check result

`python3 -m scripts.evals` and `make generate-check` remain blocked by Task 4 work intentionally excluded
from Task 5:

```text
error: degraded behavior must cover exactly all registered skills; missing=['codebase-architecture-review', 'module-design'], extra=[]
error: Makefile has no install-<skill> target for: codebase-architecture-review, module-design
error: codebase-architecture-review: SKILL.md's Framework section does not reference: skill_result, action_gates, blocked_conditions, runtime-contract.md
error: module-design: SKILL.md's Framework section does not reference: skill_result, action_gates, runtime-contract.md
```

Those checks require eval/degraded coverage, Make targets, or skill-framework content outside this task's
authorized files. No generated projection was written.

## Full-suite attempt

The default command, `python3 -m pytest -q`, stopped during collection because four unrelated skill
directories share the `test_creator_write_guard.py` module basename:

```text
ERROR contract-test-creator/scripts/test_creator_write_guard.py
ERROR e2e-test-creator/scripts/test_creator_write_guard.py
ERROR integration-test-creator/scripts/test_creator_write_guard.py
ERROR unit-test-creator/scripts/test_creator_write_guard.py
4 errors in 1.30s
```

The isolated-import retry, `python3 -m pytest -q --import-mode=importlib --maxfail=1`, collected and
executed beyond the collision, then stopped on the known Task 4 degraded-eval gap:

```text
FAILED scripts/tests/test_batch3_eval_contract.py::test_batch3_all_registered_skills_execute_five_scenarios
ValueError: degraded behavior must cover exactly all registered skills; missing=['codebase-architecture-review', 'module-design'], extra=[]
1 failed, 930 passed, 2 warnings in 11.06s
```

## Review

Direct Standards and Spec review against `656e5bd` found no issues. The workflow's normal parallel
subagent review was not used because the Task 5 request explicitly forbids subagents.
