# Smoke test

## Fixture

Supply a READY system design, PASS architecture review, complete change-impact report with one
target path and required test, no triggered specialists, and repository evidence with known bounds.

## Invocation

> Create a deterministic implementation plan for the approved checkout change.

## Expected output

1. `implementation_plan` is present with `state_semantic: proposed_state`.
2. `plan_set_id` and `plan_id` are stable across identical inputs.
3. The task uses `loop-task-implementer`, has no unknown estimate, and appears in exactly one wave.
4. Required tests and source conditions/actions are traceable to a task or verification gate.
5. Missing triggered evidence returns `BLOCKED`; missing scope estimates return `PARTIAL`.

## Script self-test

Pressure cases are defined in [pressure-tests.md](pressure-tests.md).

```bash
python3 -m py_compile scripts/implementation_plan.py
python3 -m pytest scripts/tests/test_implementation_plan.py
make lint-implementation-planner
```
