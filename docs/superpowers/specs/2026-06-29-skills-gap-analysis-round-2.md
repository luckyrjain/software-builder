# Skills Gap Analysis — Round 2
## k8s-overprovisioning, incident-rca, pr-review

**Date:** 2026-06-29  
**Scope:** Second broad sweep after Round 1 spec implementation  
**Method:** Full re-read of current skill state + gap identification  

---

## Context

Round 1 identified and fixed 39 gaps (P0–P3). This document covers:
1. **Round 1 items not yet confirmed implemented** — gaps from the first spec that were not found in the current files
2. **New gaps introduced by implementation** — especially the k8s v3.0 graph architecture
3. **Genuinely new gaps** — not identified in Round 1

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

| # | Skill | Gap | Risk |
|---|-------|-----|------|
| P0-1 | k8s | **INV violation recovery undefined** — when invariants fail, the skill emits "graph + violations only" and stops. No guidance on whether the agent should attempt to fix the violation (re-query, mark observation missing, etc.) or just surface errors. An agent hitting INV-03 has no recovery path. | Agent stuck with no output, user gets raw invariant violations instead of a usable report |
| P0-2 | k8s | **`ASSUME_` IDs not validated by any invariant** — `assumptions[]` entries have `ASSUME_*` IDs referenced from `depends_on.assumptions`, but none of the 12 invariants validate that referenced ASSUME IDs exist in `assumptions[]`. Agent can reference a non-existent assumption silently. | Graph passes invariant checks while containing broken internal references |
| P0-3 | pr-review | **Merge conflict detection absent** — `get_merge_request` and diff pagination don't check for conflict markers before review begins. Findings could be based on a diff containing conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`). | Review findings cite lines that are conflict artifacts, not real code |
| P0-4 | pr-review | **Cross-session duplicate posting not addressed** — `<!-- cursor-pr-review -->` tag detects re-runs within a session but not across separate Claude Code sessions on the same MR. Same finding can be posted as a new inline thread. | Author sees duplicate review comments; noise erodes trust in the review bot |

---

## P1 — High-Value Capability

| # | Skill | Gap |
|---|-------|-----|
| P1-1 | k8s | **Namespace waste routing removed** — old orchestrator had a "Namespace waste" intent; new orchestrator routing table omits it. SKILL.md description still lists "namespace waste ranking" as a keyword — users who ask this will get misrouted or no result. |
| P1-2 | k8s | **Service name mismatch disambiguation absent** — `insufficient_metrics` fires when zero metrics are returned but there's no step to suggest the service name might be wrong vs. genuinely having no data. User gets a blocked report with no actionable next step. |
| P1-3 | k8s | **No multi-Deployment / StatefulSet / DaemonSet handling** — skill is written for a single Deployment. Services running multiple Deployments, StatefulSets (databases, queues), or DaemonSets have different scaling semantics and no guidance. |
| P1-4 | rca | **Multi-hop cascade analysis absent** — `dependency_failure` is a hypothesis type with no investigation steps. Tracing A→B→C failure chains is entirely unguided; the agent relies on reading error messages and guessing. |
| P1-5 | rca | **No `slo_breach` hypothesis type** — Phase 1 detects SLO breaches and escalates severity, but there's no corresponding hypothesis type. When an SLO breach is the primary signal with no error rate spike, the investigation reaches `inconclusive` with no clean path. |
| P1-6 | rca | **Grafana/Prometheus/Loki path still absent** — skill degrades Datadog → KubeSense → stop. Orgs on OSS stacks have no investigation path. |
| P1-7 | rca | **Runbook lookup missing** — post-RCA actions table has a runbook update row, but there's no step to check whether a runbook *already exists* for the identified hypothesis type before Phase 5. Known playbooks go unsurfaced during investigation. |
| P1-8 | pr-review | **Monorepo multi-service awareness absent** — no step identifies which downstream services are affected when shared library code changes. Blast-radius is incomplete for monorepo PRs. |
| P1-9 | pr-review | **Bot-authored PR detection location undefined** — Phase 2 has a "bot-dependency profile" fast path but Phase 1 (where `capability_profile` is built) has no step that detects a bot-authored MR. The profile would never be set. |
| P1-10 | pr-review | **No AI-generated code review guidance** — §15 covers LLM usage patterns in code but not reviewing *AI-generated implementations* (Copilot, Claude). These have distinct failure modes: hallucinated APIs, confident-but-wrong logic, inconsistent internal references. |

---

## P2 — Workflow Improvements

| # | Skill | Gap |
|---|-------|-----|
| P2-1 | k8s | **Graph persistence mechanism undefined** — `decision_history` field exists in schema for cross-run comparison, but no guidance on how a prior graph is obtained (no file path, no storage format). An agent running a second check cannot populate `decision_history`. |
| P2-2 | k8s | **`delivery_pointer.verified: false` rendering unspecified** — the schema flags unverified delivery pointers but neither `render/markdown.md` nor `templates/recommendations.md` specifies what to display differently vs. verified. Both render identically, hiding confidence gap from the user. |
| P2-3 | k8s | **Sidecar container collection steps missing** — `collect-metrics.md` references pod-level cost rollup including sidecars but only initContainers has dedicated collection steps. Sidecar resource costs are silently omitted from pod cost rollup. |
| P2-4 | rca | **Rate-limit handling absent** — multiple `analyze_datadog_logs` and `search_datadog_logs` calls across phases can hit Datadog API rate limits with no retry/skip/stop guidance. |
| P2-5 | rca | **Phase 2 checkpoint scope narrowing missing** — checkpoint asks "proceed to Jira (Phase 3) or stop?" but doesn't offer "skip Phase 3, go straight to Phase 4 with deploy evidence only." Users with a confirmed deploy regression waste time on unnecessary Jira queries. |
| P2-6 | rca | **Minimum window "widen" guidance vague** — when window < 10 minutes, guidance says "widen or confirm" with no suggested minimum (e.g., "at least 30 minutes for log-based analysis"). User is left to guess. |
| P2-7 | rca | **Multi-site Datadog not addressed** — some incidents span multiple Datadog orgs (US1 + EU). Skill assumes one Datadog site. No guidance on investigating across sites or when incident signals are split across orgs. |
| P2-8 | pr-review | **Large individual file guard absent** — 200-file cap protects against wide MRs but a single 10,000-line generated file can exhaust context silently. No per-file size check before inline review. |
| P2-9 | pr-review | **Second reviewer prompt on Critical absent** — Critical findings are posted but no escalation signal is emitted suggesting a human must also review before merge. Finding is advisory only with no enforcement nudge. |
| P2-10 | pr-review | **Multiple Jira tickets with conflicting ACs unhandled** — Phase 1 step 6 says "load all and merge ACs" when multiple ticket keys are found, but gives no guidance when those tickets have conflicting acceptance criteria or different priority levels. |

---

## P3 — Integration Enhancements

| # | Skill | Gap |
|---|-------|-----|
| P3-1 | pr-review | **No Jira ticket transition on review verdict** — `jira_write_available` is detected in Phase 0 but Phase 5 still doesn't use it to transition the linked ticket state (e.g., "In Review" → "Needs Changes") when Critical/High findings are posted. |
| P3-2 | k8s | **k8s v3.0 handoff format not reflected in RCA/PR-review escalation tables** — RCA and PR-review cross-skill escalation tables reference k8s by name but don't specify that the handoff format changed in v3.0. The RCA handoff block format may not match what k8s v3.0 expects. |

---

## Summary Counts

| Tier | k8s | rca | pr-review | Total |
|------|-----|-----|-----------|-------|
| P0 | 2 | 0 | 2 | **4** |
| P1 | 3 | 4 | 3 | **10** |
| P2 | 3 | 4 | 3 | **10** |
| P3 | 0 | 0 | 2 | **2** |
| **Total** | **8** | **8** | **10** | **26** |

---

## Recommended Implementation Order

1. **P0 first** — 4 gaps: INV recovery (k8s), ASSUME_ validation (k8s), merge conflict detection (pr-review), cross-session duplicate posting (pr-review).
2. **P1 capability gaps** — 10 gaps; prioritize by usage frequency: namespace waste routing (k8s), service name disambiguation (k8s), bot PR detection (pr-review), multi-hop cascade (rca).
3. **P2 workflow** — 10 gaps; batch per skill.
4. **P3 integration** — 2 gaps; low effort, high user value.
