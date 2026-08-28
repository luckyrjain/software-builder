# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `assessment_target: {project: api-disbursement, merge_request_iid: 482}` | Inputs → Collect evidence → Dispatch (pr-review always; specialists per change-impact evidence) → Aggregate → Report |
| 2 | Same, with a schema migration in the diff | Change-impact evidence marks a database change class → **database-review** dispatched with `schema`/`migration_script` |
| 3 | Same, with a new public REST endpoint in the diff | Change-impact evidence marks an API-surface change class → **api-design-review** dispatched with `api_spec` |
| 4 | Same, with no security/observability/resilience/API/DB/performance/capacity/dependency-relevant change classes | Only pr-review, change-impact, and deployment-risk run; every specialist dimension is `NOT_APPLICABLE` |
| 5 | `assessment_target` (an `mr_context`) missing entirely | Inputs HARD STOP — ask, no Collect evidence |
| 6 | A specialist's mandatory input can't be assembled from available evidence (e.g. `api_spec` not resolvable) | That specialist is never dispatched — its dimension is recorded `UNKNOWN`, not skipped silently |
| 7 | `host.ci.status` unavailable | CI dimension is `UNKNOWN`, not assumed passing — see [reference/evidence-authority-policy.md](reference/evidence-authority-policy.md) |
| 8 | A dependency bump (`current_version` → `target_version`) in the diff | Change-impact evidence marks a dependency change class → **dependency-upgrade-review** dispatched |
| 9 | "Review MR !482" (no readiness verdict requested) | **Wrong skill** → pr-review directly |
| 10 | "Is this release ready to ship?" with a `release_manifest` across 3 repos | **Wrong skill** → release-readiness-checker |
| 11 | pr-review's Phase 0 detects a write-capable SCM connection | Phase 3 posting confirmation fires — answered "Hold — don't post" per [reference/gate-policy.md](reference/gate-policy.md); nothing posted |
| 12 | A criticality-`tier0` service with only a caller-asserted rollback plan (no authoritative evidence) | Rollback/abort operational gate is `UNKNOWN`, never `PASS` — see [reference/operational-gates.md](reference/operational-gates.md) |

---

### Scenario: Happy path — no specialists triggered

**Caller:** `assessment_target: {project: api-disbursement, merge_request_iid: 482}`, a one-line
config-value change, `criticality: tier2`.

**Agent:**

1. Inputs — `assessment_target` resolved, `criticality: tier2`, `build_provenance_ref: NOT_APPLICABLE`
2. Collect evidence — CI green, 2 approvals + CODEOWNERS satisfied, change-impact reports no
   security/observability/resilience/API/DB/performance/capacity/dependency change classes
3. Dispatch — pr-review runs (posting forbidden, 0 findings); no specialist mandatory input applies,
   every specialist dimension recorded `NOT_APPLICABLE`
4. Aggregate — CI PASS, code review PASS, SCM policy PASS, change-impact PASS, deployment-risk Low,
   operational gates PASS (tier2, authoritative ownership/recovery evidence present)
5. Report — verdict `READY`

**Expected fragment:**

```
# Production readiness — api-disbursement !482

**Verdict: READY**

| Dimension | Status | Notes |
|-----------|--------|-------|
| CI | PASS | All required checks green |
| Code review (pr-review) | PASS | 0 Critical/High findings |
| Build provenance | NOT_APPLICABLE | source_revision is the deployable |
| SCM policy | PASS | 2 approvals, CODEOWNERS satisfied |
| Change impact | PASS | No material change classes detected |
| Deployment risk | PASS | Risk: Low |
| Security / Observability / Resilience / API design / Database / Performance / Capacity / Dependency upgrade | NOT_APPLICABLE | No triggering change class |
| Ownership | PASS | On-call owner confirmed (host.service.metadata.read) |
| Rollback/abort | PASS | Rollback plan verified in deploy config |
| Post-deploy verification | PASS | Health check gate configured |
| Recovery | NOT_APPLICABLE | Change confirmed stateless/reversible (host.service.metadata.read); no destructive operation |
```

---

### Scenario: Database change triggers a specialist, evidence gap sets UNKNOWN

**Caller:** Same target, but the diff adds a migration script and `host.ci.status` is unreachable.

**Agent:** Change-impact evidence marks a database change class → **database-review** dispatched with
`migration_script` per [reference/child-input-map.md](reference/child-input-map.md). `host.ci.status`
failure means the CI dimension cannot be verified — recorded `UNKNOWN`, never assumed green.

**Expected fragment:**

```
| Dimension | Status | Notes |
|-----------|--------|-------|
| CI | UNKNOWN | host.ci.status unavailable — not assumed PASS |
| Database (database-review) | CONDITIONAL | Migration reversible; index-build lock window flagged |
```

**Verdict: UNKNOWN** — an evidence gap (CI) takes precedence over the database dimension's own
`CONDITIONAL`, per worst-first precedence in [reference/gate-policy.md](reference/gate-policy.md#verdict-precedence).

---

### Scenario: Specialist mandatory input incomplete — never dispatched

**Caller:** Same target, diff touches a public API but the OpenAPI/proto/GraphQL spec text can't be
resolved from the repository or the caller.

**Agent:** `api-design-review` requires `api_spec` — with no resolvable spec text, this skill does
**not** dispatch it on a partial/guessed input. Per
[reference/gate-policy.md](reference/gate-policy.md), that dimension is recorded `UNKNOWN` directly.

**Expected fragment:**

```
| API design (api-design-review) | UNKNOWN | api_spec not resolvable — dispatched skipped, not run with incomplete input |
```

---

### Scenario: Degraded path — a child returns BLOCKED instead of an interactive prompt

**Caller:** Same target; the dispatched `security-review` would normally ask the caller to disambiguate
scope.

**Agent:** Per [reference/gate-policy.md](reference/gate-policy.md), an embedded child that would
otherwise render an interactive question instead returns `BLOCKED` to this skill — no live prompt
surfaces mid-aggregation. The security dimension is recorded `UNKNOWN` with the block reason retained
in `evidence_refs`.

---

### Scenario: Cross-skill — wrong entry point

**Caller:** "Review MR !482" (no readiness verdict requested).

**Agent:** Routes to **pr-review** directly — this is a generic correctness review, not a readiness
verdict (see [SKILL.md](SKILL.md) § When to use / NOT to use).
