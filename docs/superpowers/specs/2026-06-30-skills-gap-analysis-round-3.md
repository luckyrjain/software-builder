# Skills Gap Analysis — Round 3
## k8s-overprovisioning, incident-rca, pr-review

**Date:** 2026-06-30
**Scope:** Third broad sweep after Round 2 spec implementation
**Method:** Full re-read of current skill state + gap identification

---

## Context

Round 1 identified and fixed 39 gaps. Round 2 identified and fixed 20 gaps (6 were already implemented). This document covers:
1. **Gaps created by Round 2 additions** — new content introduced new edge cases or duplicate logic
2. **Genuinely new gaps** — angles not previously surfaced, found by re-reading all three skills with fresh eyes

---

## Priority Tiers

| Tier | Meaning |
|------|---------|
| **P0** | Safety/correctness — agent produces wrong, dangerous, or misleading output |
| **P1** | High-value capability — affects most users, significant signal lost without it |
| **P2** | Workflow improvement — correctness or UX improvement, not safety-critical |
| **P3** | Integration enhancement — nice-to-have handoffs and automation |

---

## P0 — Safety / Correctness

*None identified in Round 3. All P0 gaps from Rounds 1–2 are confirmed closed.*

---

## P1 — High-Value Capability

| # | Skill | Gap |
|---|-------|-----|
| P1-1 | k8s | **KEDA metric collection undefined** — `replica-analysis.md` detects KEDA (`keda.scaler.active`, `keda.scaler.metrics_value`) but there are no `OBS_` IDs for KEDA signals, no collection steps in `collect-metrics.md`, and no thresholds for KEDA-driven replica evaluation. An agent that hits a KEDA workload has a detection stub but no evaluation path — the replica analysis either silently falls through to "fixed replicas" or produces CPU-based verdicts on a workload that scales on queue depth or custom metrics. |
| P1-2 | k8s | **Limit-to-request ratio not analyzed** — `OBS_CPU_LIMIT` and `OBS_MEMORY_LIMIT` exist in `observation-ids.md` but are never queried in COLLECT or used in any REASON module. OOM kills happen at the *limit*, not the request. When `limit ≈ request` (zero burst headroom), any transient spike causes OOM/throttle. When `limit >> request` (10×), nodes are over-committed and scheduling is unreliable. Neither case is detected or flagged. |
| P1-3 | rca | **`slo_breach` investigation path absent when logs are missing** — Phase 1 records `signal_type: "slo_breach"` in `error_signals`, so the Phase 4 minimum evidence gate allows ranking. But when SLO breach is the *only* signal (log retention expired, logging disabled, high sampling rate), Phases 2–3 correlations against deploy events and Jira return nothing meaningful. No guidance on: trying traces as an alternative, querying SLO error-budget burn rate over a wider window, widening to find where logs do exist, or transitioning to a manual war-room posture. |
| P1-4 | pr-review | **Revert MR detection absent** — no detection of revert MRs (title "Revert ...", diff is predominantly `-` lines, recent sibling commit exists). Revert MRs need a specific review: (a) is the revert *complete* — does it undo all original changes including config/schema/migration steps, (b) were new dependencies introduced between the original merge and this revert that would break under reversal, (c) does the revert create a data/schema gap requiring a forward fix. Currently treated identically to a feature MR. |

---

## P2 — Workflow Improvements

| # | Skill | Gap |
|---|-------|-----|
| P2-1 | k8s | **VPA + HPA coexistence conflict not detected** — `collect-metrics.md` has VPA collection steps and warns about VPA in REASON. But when both a VPA and an HPA are active on the same resource dimension (both controlling CPU or both controlling memory), they fight: VPA resizes the pod template while HPA scales replicas, causing oscillation. No step checks whether HPA is already targeting the dimension that VPA is recommending on. Agent may produce VPA-based cut recommendations that the HPA immediately overrides. |
| P2-2 | rca | **Phase 0b window anchor expansion missing** — Phase 0b anchors `from_time` from the Jira ticket's `created_at`. Incident tickets are typically created 15–30 minutes *after* the incident started (on-call response lag). The pre-ticket degradation period — often where the earliest root signal lives — is invisible. No guidance to: expand `from_time` backwards by at least 15 minutes post-anchor, or run a brief Phase 1 "backstroke" query over the expanded window to find the actual first error spike. |
| P2-3 | rca | **Runbook lookup duplication across phases** — Round 2 added runbook lookup in Phase 1 (after the Phase 1 checkpoint, when hypothesis is forming). Phase 4 already had a separate "Runbook linkage" step (search after hypothesis is ranked). No dedup guidance between them. Agent runs two searches, may produce two inconsistent results in the report (different runbooks or same runbook listed twice), and has no rule for which finding takes precedence. |
| P2-4 | pr-review | **Mixed bot+human MR not handled** — Round 2's bot detection sets `capability_profile.bot_dependency: true` when the MR author is a bot. But human-authored commits on top of a bot MR (common pattern: Renovate creates the PR, a human resolves a conflict or bumps a constraint manually) are not separated. The `bot-dependency` fast path would skip architecture/style review of the human-authored commits, which may contain substantive changes beyond the dependency update. |
| P2-5 | pr-review | **CODEOWNERS approval path not enforced** — Phase 1 step 7 reads and caches CODEOWNERS rules. Phase 5 records overall MR approval count. But no step cross-checks whether the code owners for *each changed path* have approved. A PR touching `src/payments/` that only has an approval from a non-payments-team member passes without a finding. The total approval gate (N/M approvals) does not catch path-level ownership gaps. |

---

## P3 — Integration Enhancements

| # | Skill | Gap |
|---|-------|-----|
| P3-1 | rca | **PagerDuty / OpsGenie incident lookup absent** — Phase 0 checks `search_datadog_incidents` for prior incident context. Most orgs use PagerDuty or OpsGenie as the primary alerting/on-call layer. Prior alerts, escalation timelines, acknowledgment timestamps, and alert severity from PD/OG go entirely unused. No Phase 0 detection step for PD/OG MCP tools, and no guidance for orgs that don't use Datadog incidents at all. |
| P3-2 | k8s | **Application-level APM metrics not used for confidence** — All sizing decisions are driven by infra metrics (CPU p95, memory max). When the bottleneck is a connection pool, thread pool, goroutine limit, or DB connection saturation — visible as APM latency p99 increasing while CPU stays low — the skill has no path to detect it. APM signals (latency trend, error rate) should at minimum lower recommendation confidence when `p99 latency is rising despite healthy CPU utilization`, preventing false-positive cut recommendations. |
| P3-3 | pr-review | **OpenAPI / Protobuf spec changes not specifically detected** — §6 covers breaking API changes generically. When a PR modifies `openapi.yaml`, `swagger.json`, `*.proto`, or `asyncapi.yaml`, those files deserve a dedicated check: spec validity, breaking field removal (removed paths, required field dropped, response type changed), and presence of a version bump. Currently these fall through to generic §6 prose without triggering any structured spec diff check. |

---

## Summary Counts

| Tier | k8s | rca | pr-review | Total |
|------|-----|-----|-----------|-------|
| P0 | 0 | 0 | 0 | **0** |
| P1 | 2 | 1 | 1 | **4** |
| P2 | 1 | 2 | 2 | **5** |
| P3 | 1 | 1 | 1 | **3** |
| **Total** | **4** | **4** | **4** | **12** |

---

## Recommended Implementation Order

1. **P1 first** — 4 gaps: KEDA collection (k8s), limit/request ratio (k8s), slo_breach investigation path (rca), revert MR detection (pr-review).
2. **P2** — 5 gaps; batch per skill: VPA+HPA conflict (k8s), Phase 0b window expansion + runbook dedup (rca), mixed bot+human MR + CODEOWNERS enforcement (pr-review).
3. **P3** — 3 gaps: PagerDuty/OpsGenie (rca), APM confidence (k8s), OpenAPI detection (pr-review).
