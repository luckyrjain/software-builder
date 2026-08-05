# Smoke test

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

Re-run after **any** skill edit (not only install).

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> Assess `<deployment>` in `<namespace>` — is it overprovisioned?

Example:

> Is `neo-disbursement-service` overprovisioned in production? Use the last 7 days of Datadog metrics.

## Fixture

Deployment with ≥7d Datadog metrics; single namespace; <5 containers.

## Output checklist

1. **MCP profile** — Datadog ✅; git MCP noted (✅ or paste-fallback)
2. **Scope** — deployment, env, window announced (pre-flight block)
3. **decision_graph** — passes INV-01–INV-13 (`make lint-k8s` or `scripts/validate_decision_graph.py`)
4. **Human Report** — all slugs from [report-schema.md](report-schema.md#human-report-fixed-order-primary-output)
5. **Human Report hygiene** — no `OBS_`/`DEC_`/`REC_`/`EVID_` IDs; no weighted-sum arithmetic; Evidence table orders fleet p95 → Kafka lag → memory peak → HPA → CPU avg → HTTP → restarts → manifest; Recommendations section orders observability → actionable change → hold; recommendation Decision and Decision confidence on separate lines; opens with `## Recommendation` not `Decision`/`Verdict`; keep recs show `Decision: Keep` not `State: Blocked`; appendix LifecycleSummary uses `KEEP`/`DEFER`/`CHANGE`/`NOT RECOMMENDED` — not graph `BLOCKED` on keep recs
6. **Assessment confidence** — Human Report shows band + numeric + Basis bullets; appendix has factor list only — no `0.35×` formulas in default render
7. **Conclusion + chat follow-up** — Human Report ends with `## Conclusion`; no "Type ACT" or agent mode instructions in report body; handoff offer, PostChangeVerification (when ≥1 READY rec), or re-run hint belongs in **chat only**

## Render-specific checks

From [workflow/report.md](../workflow/report.md):

- Full DORA appendix includes Evidence Registry + Assessment Metadata fingerprint
- JSON render round-trips the graph unchanged ([render/json.md](../render/json.md))

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Datadog ❌ in prerequisites | MCP disconnected / auth | Run **ddsetup**; re-auth Datadog MCP |
| INV-01–INV-13 failure | Schema or template drift | `make lint-k8s-skill` |
| Human Report shows `0.35×` arithmetic | Render regression | Check `workflow/report.md` — band + Basis only |
| Report body contains `Type ACT` | Render regression | Post-render instructions belong in chat / `SKILL.md` only |
| Missing `## Conclusion` | Render regression | Last Human Report section before appendix |
| Smoke passes but edge case fails | Pressure scenario regression | See [pressure-tests.md](pressure-tests.md) |

Deep edge cases: [pressure-tests.md](pressure-tests.md) (≥2 rows — e.g. missing fleet p95, active incident blocks downsizing).
