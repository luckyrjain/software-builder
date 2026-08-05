# Gold RCA excerpt (format few-shot)

Load in **Phase 5** before authoring markdown. Match **section order and narrative shape** — do not copy
findings; translate from `evidence_json`, `ranked_hypotheses`, and validated `causal_graph`.

---

## Path A — deploy regression (happy path)

# Incident Root Cause Analysis

## Executive summary

Between 2026-06-28 14:00–16:00 UTC, `neo-disbursement-service` experienced a 5xx spike on
`transfer-money`. **Deploy regression** (MR !482) is the leading hypothesis (**HIGH** confidence): production
deploy at 14:20 UTC preceded the error spike at 14:45 UTC with diff touching `TransferMoneyHandler`.
Immediate action: rollback or hotfix the handler path.

## Incident scope

| Field | Value |
|-------|-------|
| Window | 2026-06-28 14:00 → 16:00 UTC |
| Environment | production |
| Service | neo-disbursement-service |
| Incident class | Deploy |
| Confidence | HIGH — deploy + error spike + diff on failing path |

## Customer impact

| Field | Value |
|-------|-------|
| Affected endpoints / flows | POST /transfer-money |
| Availability impact | Elevated 5xx (~12% peak) |
| Duration | ~40 minutes |

## Detection analysis

| Field | Value |
|-------|-------|
| Detected by | PagerDuty |
| MTTD | ~3 minutes |

## Unified timeline

| Time (UTC) | Type | Evidence quality | Source | Event |
|------------|------|------------------|--------|-------|
| 14:20 | deploy | Correlated | gitlab | Production deploy MR !482 |
| 14:45 | error_signal | Observed | datadog | 5xx spike on transfer-money |
| 15:10 | remediation | Observed | ops | Rollback initiated |
| 15:25 | recovery | Observed | datadog | Error rate returned to baseline |

## Causal chain

```text
14:20 UTC — production deploy MR !482
↓
14:45 UTC — 5xx spike on transfer-money handler
↓
15:10 UTC — rollback initiated
```

## Causal graph

Acyclic — mirrors validated `rca_causal_graph.yaml` (deploy → handler regression → 5xx spike).

## Initiating event / trigger / root cause

- **Initiating event:** Production deploy MR !482 at 14:20 UTC
- **Trigger:** Code change on `TransferMoneyHandler` validation path
- **Root cause:** Deploy regression — logic error introduced in MR !482
- **Contributing factors:** None identified beyond deploy timing

## Ranked hypotheses

**H1 — deploy_regression (primary)** — **HIGH**

Supporting evidence:
- Deploy at 14:20 UTC; 5xx onset 14:45 UTC (Observed)
- MR !482 diff modifies `TransferMoneyHandler` (Observed)

Contradicting evidence:
- None material

**H2 — dependency_failure** — **LOW** — ruled out; no upstream latency spike in window

## Evidence matrix

| Signal | Quality | Source | Finding |
|--------|---------|--------|---------|
| 5xx rate spike | Observed | datadog | Onset 14:45 UTC |
| Deploy MR !482 | Correlated | gitlab | 14:20 UTC; diff on handler |

## Evidence coverage

Overall completeness: 85% · Confidence ceiling: HIGH

## Recovery analysis

Rollback at 15:10 UTC; errors normalized by 15:25 UTC. MTTR ~40 minutes.

## Corrective actions

| Action | Owner | Priority |
|--------|-------|----------|
| Hotfix or revert MR !482 | service team | P0 |

## Preventive actions

| Action | Owner | Priority |
|--------|-------|----------|
| Add regression test for transfer-money validation | service team | P1 |

## Gaps / missing evidence

None material for primary hypothesis.

## Conclusion

Deploy regression on MR !482 is the defensible primary cause. Rollback restored service; follow with
PR review and regression test before re-deploy.

---

## Path B — inconclusive (no defensible primary)

## Executive summary

Between 2026-06-21 05:30–06:30 UTC, OpenSearch cluster saturation coincided with elevated API errors.
**No defensible root cause** — all ranked hypotheses remain **MEDIUM** or below after caps: expensive-query
branch and infra saturation co-occur but trigger attribution is incomplete after investigation.

## Conclusion

Do not assert a single primary cause. Next steps: complete query-string hunt on onset slice, validate
caller baselines, re-run RCA after instrumentation.

---

*Post-RCA actions table and `assessment_metadata` YAML are chat/appendix only — not duplicated here.*
