# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a real or realistic change description with a
schema migration, a stated rollback plan, and a named affected service, so the happy path exercises
all five analysis sections — not just the clean/no-migration case.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `Assess deployment risk for: <change_description>` (optionally with `affected_services`,
> `migration_steps`, `rollback_plan`, `traffic_pattern`)

Example: `Assess deployment risk for: adding a nullable column to orders.status via an online
migration, deployed to checkout-service, rollback is a feature flag toggle, deploying at 2pm UTC
weekday (peak).`

## A correct minimal output contains

1. **Scope announcement** — the resolved `change_description` and which optional fields were
   supplied vs. defaulted, before analysis starts.
2. **Core findings** — all five sections (Blast radius, Migration risk, Rollback complexity,
   Dependency risk, Traffic risk) each populated, or explicit "None found"/"None stated" — never an
   omitted section.
3. **`DEPLOYMENT_RISK_REPORT.md` produced**, per
   [reference/report-format.md](report-format.md), with the bold `Risk:` verdict line matching the
   derivation rule in `report-format.md` § Rules exactly.
4. **`deployment_confidence`** stated as its own field (`HIGH | MEDIUM | LOW | UNKNOWN`), distinct
   from the Risk verdict.
5. **Confirmation/next-step** — a one-line pointer to
   [cross-skill escalation](../../docs/skill-framework/shared/cross-skill-escalation.md) when a
   finding matches one of `SKILL.md` § Cross-skill escalation's rows.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| `rollback_plan` not supplied and not discoverable in the repository | Rollback complexity section records "None stated — evidence gap"; `deployment_confidence` capped at `LOW`; Risk verdict floored at `High` per `report-format.md` § Rules |
| `traffic_pattern` not supplied | Traffic risk section records "Unknown" and analysis proceeds with the conservative peak-risk default, not an assumed off-peak/low-traffic deploy |
| `change_description` is empty or missing | Inputs phase HARD STOPs and asks — Analyze never runs |
| `affected_services` not supplied and not inferable from `change_description` | Blast radius section records "Unknown — affected_services not supplied and not inferable"; does not silently narrow blast radius to "none" |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
