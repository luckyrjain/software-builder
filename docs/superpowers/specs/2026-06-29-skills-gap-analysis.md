# Skills Gap Analysis — k8s-overprovisioning, incident-rca, pr-review

**Date:** 2026-06-29  
**Scope:** Broad sweep across capability, workflow, guardrail, and integration gaps  
**Method:** Three-pass review + brainstorming session  

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

These can produce wrong or dangerous output and should be addressed first.

| # | Skill | Gap | Risk |
|---|-------|-----|------|
| P0-1 | k8s | **No post-change projection** — recommending a CPU/memory cut with no check that the proposed new request still clears measured p95. Agent could recommend a request below observed usage. | Recommending a cut that causes throttle/OOM post-apply |
| P0-2 | k8s | **No active incident check before analysis** — `firing_required_monitor` only fires when a monitor is found; no proactive check for open/active incidents before emitting cut recommendations. | Right-sizing cut applied during an active incident worsens the outage |
| P0-3 | k8s | **Metrics staleness not detected** — if a service was redeployed 2 days ago within a 7d window, 5 days of old/zero metrics pull p95 down artificially, making a healthy service look overprovisioned. | False overprovisioning verdict; incorrect cut recommendation |
| P0-4 | rca | **No minimum evidence gate before Phase 4** — hypothesis ranking runs even when `error_signals` is empty, producing a valid-looking `inconclusive` result that obscures "no data was found." | User acts on a report with zero underlying evidence |
| P0-5 | rca | **Confidence guardrail ignores signal timing** — HIGH/MEDIUM rules check signal count but not temporal proximity. A signal 55 min after the window still qualifies for HIGH if it's the second independent source. | Inflated confidence from signals outside the actual incident window |
| P0-6 | rca | **No minimum window check** — a 2-minute window won't produce meaningful log aggregation; no guard prevents a full investigation on a window too narrow for reliable signal. | Investigation on insufficient data presented as authoritative |
| P0-7 | rca | **Phase 0b has no timezone check** — `inputs.md` now asks for timezone when timestamps lack a suffix, but Phase 0b parses Jira ticket timestamps from description text (often in reporter's local time) with no equivalent check. | Wrong incident window anchored from Jira ticket |
| P0-8 | pr-review | **No merge conflict detection** — if the MR has unresolved conflicts, the diff may include conflict markers. No step detects this before review; findings could be based on a corrupted diff. | Review findings cite lines that don't represent real code |
| P0-9 | pr-review | **Cross-session duplicate posting prevention** — `<!-- cursor-pr-review -->` tag detects re-runs within a session but not across separate Claude Code sessions. Same finding can be posted as a new thread. | Author sees duplicate review comments; noise erodes trust |

---

## P1 — High-Value Capability

Missing capabilities that affect the majority of users.

| # | Skill | Gap |
|---|-------|-----|
| P1-1 | k8s | **VPA integration absent** — VPA recommendations are never read as a positive signal. The skill re-derives what VPA already computed; ignoring it produces redundant or conflicting recommendations. |
| P1-2 | k8s | **Seasonality not distinguished from overprovisioning** — a service with 3× more traffic on weekdays vs. weekends looks overprovisioned on a 7d average. No structured guidance for flagging "seasonal pattern — do not cut." |
| P1-3 | k8s | **Service name mismatch silent failure** — if the user-provided service name doesn't match the Datadog service tag, `insufficient_metrics` fires with no disambiguation. No suggestion that the name might be wrong. |
| P1-4 | rca | **No multi-hop cascade analysis** — `dependency_failure` is a hypothesis type but has no investigation steps. When A→B→C fails, no structured path to trace the chain beyond reading error messages. |
| P1-5 | rca | **No canary/blue-green deploy detection** — `deploy_regression` assumes a full deploy. Canary deploys show partial error spikes on a traffic percentage; the change story looks identical but the error pattern differs. No guidance to distinguish. |
| P1-6 | rca | **No Grafana/Prometheus/Loki path** — skill degrades Datadog → KubeSense → stop. Orgs on OSS stacks have no investigation path at all. |
| P1-7 | rca | **No runbook linkage** — after identifying a hypothesis, no step checks whether a runbook exists for that failure type. Known playbooks go unsurfaced. |
| P1-8 | pr-review | **No dependency vulnerability scanning** — new packages added in `package.json`, `Gemfile`, `go.mod`, `requirements.txt` are not checked against known CVEs. A supply-chain gap distinct from code-level security checks. |
| P1-9 | pr-review | **No bot-authored PR fast path** — Renovate, Dependabot, and codegen PRs need a different review: verify the bump is safe, check for breaking changes, skip style/architecture analysis. No alternate persona or fast path. |
| P1-10 | pr-review | **No monorepo multi-service awareness** — a PR touching shared library code affects every service that imports it. No step identifies downstream impacted services; blast-radius assessment is incomplete. |

---

## P2 — Workflow Improvements

Correctness or experience improvements that don't pose immediate safety risk.

| # | Skill | Gap |
|---|-------|-----|
| P2-1 | k8s | **Rollback trigger definition is vague** — report template asks for rollback triggers but never defines what a valid one looks like. Agents emit freeform text, quality varies widely. |
| P2-2 | k8s | **No namespace ResourceQuota / LimitRange check** — a cut recommendation could be blocked at apply time by a namespace quota. No step verifies the proposed values are within namespace limits before emitting. |
| P2-3 | k8s | **InitContainer resources unanalyzed** — only main containers are assessed. InitContainers with oversized resource requests silently inflate pod cost. |
| P2-4 | rca | **No progress checkpoint between phases** — phases 1–3 run silently. If Phase 1 returns sparse data, the agent continues into Phase 2–4 without surfacing thin signal and asking whether to proceed. |
| P2-5 | rca | **No partial report path** — if the user says "stop here, give me what you have," the skill has no structured partial-report output. Only full Phase 5 report or blocked report exist. |
| P2-6 | rca | **No rate-limit handling** — multiple `analyze_datadog_logs` calls across phases can hit API rate limits. No guidance on retry, skip, or stop when rate-limited mid-investigation. |
| P2-7 | rca | **Recurrence threshold has no similarity definition** — Phase 3 escalates to "Systemic" when 3+ similar incidents found by JQL text match. No filter to confirm matched tickets are the same failure mode vs. accidental keyword overlap. |
| P2-8 | pr-review | **No large individual file guard** — the 200-file cap protects against wide MRs but a single 10,000-line generated file can exhaust context silently. No per-file size check before inline review. |
| P2-9 | pr-review | **No stale MR guard** — if the MR source branch is 50+ commits behind target, review findings may be invalid by the time the author addresses them. No staleness check before Phase 2. |
| P2-10 | pr-review | **No second-reviewer prompt on Critical** — the skill posts the Critical comment but doesn't signal that the PR should not be merged without a human reviewing that specific finding. |
| P2-11 | pr-review | **No test coverage delta** — CI results are checked but not whether the PR reduced overall test coverage. If coverage reports are in the pipeline, this signal is invisible. |

---

## P3 — Integration Enhancements

Handoffs and automation that extend the skills beyond their current boundaries.

| # | Skill | Gap |
|---|-------|-----|
| P3-1 | k8s | **No change delivery pointer** — right-sizing recommendations have no pointer to where the change lives (Helm values, kustomize overlay, Terraform). Skill stops at "here's what to change" with no apply path. |
| P3-2 | k8s | **No deploy freeze check** — no step checks whether the org has a merge/deploy freeze that would make the recommendation un-actionable. |
| P3-3 | k8s | **No re-run after change workflow** — after a right-sizing change is applied, no structured "come back in 7d and verify" path. |
| P3-4 | rca | **No post-RCA action structure** — after the report, no guidance on next steps: create follow-up Jira, update runbook, open pr-review on causative MR. Implied by cross-skill escalation but not structured as output fields. |
| P3-5 | rca | **No structured handoff to k8s skill** — when `infra_capacity` is confirmed and user is directed to k8s-overprovisioning, no evidence is passed as context. User re-explains the incident manually. |
| P3-6 | rca | **No Confluence/wiki output format** — the report template produces markdown. Teams writing postmortems in Confluence have no output path or template. |
| P3-7 | pr-review | **No Jira ticket transition** — `jira_write_available` is detected but never used. After posting findings, the linked Jira ticket stays in its current state regardless of review outcome. |
| P3-8 | pr-review | **No pipeline vote / merge block** — Critical findings are advisory only. No mechanism to vote -2 or block the pipeline; a developer can merge over Critical findings. |
| P3-9 | pr-review | **No Slack/Teams notification** — after posting inline comments, no option to notify the PR author directly. Teams relying on push notifications over GitLab email miss the review. |

---

## Summary Counts

| Tier | k8s | rca | pr-review | Total |
|------|-----|-----|-----------|-------|
| P0 | 3 | 4 | 2 | **9** |
| P1 | 3 | 4 | 3 | **10** |
| P2 | 3 | 4 | 4 | **11** |
| P3 | 3 | 3 | 3 | **9** |
| **Total** | **12** | **15** | **12** | **39** |

---

## Recommended Implementation Order

1. **P0 items first** — 9 gaps, safety-critical. All three skills have P0 items; fix in parallel.
2. **P1 high-frequency capability** — 10 gaps; prioritize by skill usage frequency.
3. **P2 workflow** — 11 gaps; can be batched per skill.
4. **P3 integration** — 9 gaps; evaluate against available MCPs/infrastructure before committing.
