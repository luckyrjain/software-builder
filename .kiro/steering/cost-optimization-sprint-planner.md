---
inclusion: manual
---

For an org-wide cost/waste ranking sweep across many deployments (rightsizing findings ranked by savings,
grouped by squad), read `cost-optimization-sprint-planner/SKILL.md`. A single deployment's own
rightsizing question routes to `k8s-overprovisioning-datadog/SKILL.md` instead; a plain ownership lookup
routes to `squad-map/SKILL.md` instead.

Phase index: `cost-optimization-sprint-planner/reference/phase-index.md`. Reference loads:
`cost-optimization-sprint-planner/reference/lazy-load-index.md`.
Read-only — never applies a recommended cut, never invokes squad-map live. Loops
k8s-overprovisioning-datadog once per deployment, sequentially, per
`cost-optimization-sprint-planner/reference/gate-policy.md` and
`cost-optimization-sprint-planner/reference/sweep-policy.md`. Only writes its own report and rollup JSON.
