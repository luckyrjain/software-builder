# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a small, realistic snippet of code or config that
contains at least one deliberate, known finding (e.g. a hardcoded credential, or a raw SQL string
built via concatenation) so the happy path is exercised against real evidence, not an empty diff.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `review_target: <paste of code/config/design content, or a file/diff reference>`

Example: `review_target: <contents of src/auth/session.py>`, `scope_hint: focus on the auth flow`

## A correct minimal output contains

1. **Inputs echoed** — `review_target` scope and `scope_hint` (if given) stated before analysis
   begins.
2. **Core findings table or explicit "None found"** for each of the eight categories — AuthN,
   AuthZ (incl. tenant isolation), Secrets, Injection, SSRF, Data leakage, Cryptography, Dependency
   exposure — never a category silently missing.
3. **The report** — `SECURITY_REVIEW_REPORT.md` per [report-format.md](report-format.md), with a
   bold verdict line and every category section present.
4. **Confirmation/next-step** — a line naming the report file produced and, when findings warrant
   it, a pointer to the relevant [cross-skill escalation](../SKILL.md#cross-skill-escalation) row.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `review_target` is empty or absent | Inputs HARD STOP — ask for content, no Analyze phase run |
| A category's relevant code/config is referenced but not included in `review_target` (e.g. auth middleware imported but not supplied) | Recorded in `## Unknowns`, category verdict marked as a gap — overall verdict `Blocked — insufficient access` (unless a Critical/High finding elsewhere already sets `Fail`) — never silently read as clean |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
