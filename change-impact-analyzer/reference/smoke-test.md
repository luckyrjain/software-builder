# Smoke test — expected minimal output

Run after install and after any edit to this skill.

## Fixture

Use the design-only fixture `system_design: “Add a payment.created event.”` with no repository or
SCM capability.

## Invocation

> What services and contracts does this proposed payment design affect?

## A correct minimal output contains

1. **Phase 0 / capability profile** — repository and SCM capabilities are unavailable.
2. **Scope announcement** — supplied design-only analysis and bounded-impact boundary.
3. **Core findings** — changed classes and explicit unknown surfaces.
4. **Summary / report** — `PARTIAL` or `UNKNOWN`, never `COMPLETE`.
5. **Structured footer** — `change_impact_report` with target and evidence references.
6. **Confirmation or next step** — offer repository evidence collection or specialist handoff.

## Expected first output

```text
Capabilities: host.repository.read ❌ | host.scm.change.read ❌ | host.report.write ✅
Scope: supplied design-only material; no repository-backed completeness claim
```

## Script self-test

```bash
python3 -m py_compile scripts/change_impact.py
python3 -m pytest scripts/tests/test_change_impact_analyzer.py
make lint-change-impact-analyzer
```

## Failure diagnosis

- Missing repository capability: expected `PARTIAL`/`UNKNOWN` with material unknowns.
- Missing exact SCM head or mismatched head: expected fail-closed non-`COMPLETE` coverage.
- Missing report capability: fix host configuration before invoking the leaf.

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
