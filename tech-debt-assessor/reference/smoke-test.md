# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a `debt_items` list of ≥3 items covering a spread —
at least one clearly urgent (high business impact or operational risk), one clearly low-priority
(small, isolated, low drag), and one deliberately vague (thin description, no evidence) to exercise the
Unknown path, not just the clean scoring path.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `debt_items: [{description: "Legacy auth module still uses deprecated crypto library", affected_area:
> "auth-service"}, {description: "Unused feature flag left in payments config", affected_area:
> "payments"}, {description: "Something's off with the reporting job", affected_area: "reporting"}]`

## A correct minimal output contains

1. **Every supplied item scored on all four dimensions** (business impact, engineering drag, operational
   risk, effort), or explicitly marked `Unknown` on the dimension that couldn't be assessed — never
   silently skipped.
2. **Scope announcement** — item count and the priority-score formula stated before the ranked table.
3. **Ranked backlog table**, sorted by priority score descending, `Unknown`-score rows last but present.
4. **`TECH_DEBT_ASSESSMENT.md` produced**, per [reference/report-format.md](report-format.md), with the
   Ranked backlog, Rationale, and Notes sections all present.
5. **Confirmation / next step** — a one-line pointer to items whose Priority is `Now`, if any, as the
   natural next action for the caller.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `debt_items` is present but empty | Inputs HARD STOP — ask for the backlog, no Analyze |
| An item's description is too vague to score engineering drag or operational risk | Recorded as `Unknown` for that dimension; item's Priority score is `Unknown`, Priority is `Unknown — insufficient evidence` — never guessed into a numeric score or silently dropped |
| `repo_context` is supplied but unreadable | Analyze proceeds on `debt_items` alone; Notes states the repo evidence source was unavailable, items relying on it get a wider `Unknown` gap rather than a fabricated score |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
