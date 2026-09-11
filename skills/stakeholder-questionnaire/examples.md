# Examples — stakeholder-questionnaire

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `stakeholder-questionnaire` ambiently whenever a decision is blocked by one named person's
knowledge. It is read-only and report-only: inspect the decision context and recipient, emit a
discovery questionnaire proposal, and never send, post, or write it to disk, or implement anything
automatically.

| # | Caller sends | Resolves to | Notes |
|---|-----------------|---------------|-------|
| 1 | "We need to decide on retry budget for transient payment failures. Only the payments on-call engineer knows what we can sustain — they hold the SLA constraints and historical load data. Can you draft a questionnaire?" | Inputs → Draft → Report with a discovery questionnaire targeting the gap between what the engineer knows and what the decision needs | Happy path |
| 2 | "We're blocked on whether to cache the user profile endpoint. Our caching expert (the platform team lead) knows the trade-offs we've already tried. Can you draft a questionnaire to explore this with them?" | Inputs → Draft → Report with questions grouped by theme (observability, edge cases, invalidation strategy, most-important-first) | Questionnaire with themes |
| 3 | "I need a discovery questionnaire drafted." | Inputs HARD STOP — ask what decision is blocked and who holds the missing knowledge | No context |
| 4 | "The database migrations are taking too long on prod. Draft a questionnaire." | Inputs HARD STOP — ask whose knowledge is missing (DBA? DevOps? Ops on-call?) | No named recipient |
| 5 | "Should we migrate to the new payment processor, or stick with the current one?" | Wrong skill — the caller can reason through this with enough interrogation; offer `engineering-decision-discovery` | Wrong-skill row |
| 6 | "We ran the questionnaire with the infra team and got their answers. Now turn these answers into a PRD." | Wrong skill — offer `prd-architect` to turn answered questions into a PRD | Cross-skill handoff |
| 7 | "The questionnaire you draft shouldn't need to be sent — just tell me the answers." | Rejected — this skill never receives or fabricates answers; questionnaire is read-only output only, and the caller decides how to hand it to the recipient | Boundary rule |
| 8 | "Draft a questionnaire for the frontend lead on whether we should adopt a new component library, given that they know our team's build-time constraints." | Inputs → Draft → Report with a questionnaire targeting the specific gap (build constraints, migration effort, tooling integration risk) between what they know and what the decision needs | Gap-targeted questionnaire |

## Example: discovery questionnaire with multiple themes

**Evidence:** the caller needs to decide on caching the user-profile endpoint. The caching expert
(platform team lead) knows the trade-offs, risk patterns, and edge cases from prior caching
decisions. The decision is blocked by that expertise.

**Result:**

```
# User-Profile Endpoint Caching Strategy

**Purpose:** Decide whether to cache the user-profile endpoint — we know it's a hot path, but the
trade-offs and past lessons from our infrastructure are known only to you.

**From:** <the caller> — **To:** the platform team lead — **How your answers will be used:** to
inform a decision on endpoint-level caching vs. full-service caching

## Context

We're seeing high latency on the user-profile endpoint during peak load. One option is endpoint-level
caching; another is deferring to full-service caching. Your experience with the trade-offs and edge
cases we've hit before is what we need.

## How to answer

Rough effort: 20–30 minutes. No hard deadline, but we're deciding this week. Partial answers are
useful; flag anything you're unsure about.

## Caching Strategy

### What are the edge cases where endpoint-level caching would break our product behavior?

Why this matters: We need to understand what stale profile data could affect.

### How did our previous endpoint caching decisions go? What would you do differently this time?

## Invalidation & Consistency

### If we cache at the endpoint level, how do we handle profile updates without long stale-data windows?

### Should we lean on eventual consistency here, or strict consistency?

## Anything else?

Anything else about endpoint caching, service dependencies, or operational constraints we should know?

## Recommendation

A questionnaire targeting the gap between your infrastructure expertise and our caching decision.
No downstream invocation — once you answer, use the answers to inform a technical decision and a
follow-on architecture review if needed.
```

## Example: no decision context — HARD STOP

**Evidence:** the caller asks for a questionnaire but provides no decision that's blocked.

**Result:** HARD STOP. Ask: "What decision are you trying to make, and why can't you make it alone?"

## Example: no named recipient — HARD STOP

**Evidence:** the caller provides a decision ("Should we use a serverless database?") but doesn't
name whose knowledge is missing.

**Result:** HARD STOP. Ask: "Whose knowledge or expertise would resolve this decision? (e.g., the
DBAs, the DevOps team lead, the vendor rep?)"

## Example: wrong skill — not a knowledge gap, a decision gap

**Evidence:** the caller asks "Should we refactor this module or rewrite it from scratch?" — a
decision they can reason through with interrogation, not blocked by one person's knowledge.

**Result:** Offer `engineering-decision-discovery` — you can answer this decision with enough
interrogation and structured thinking.

## Example: cross-skill handoff to prd-architect

**Evidence:** the questionnaire was drafted and the recipient answered. Now the caller wants to turn
the answers into a PRD.

**Result:** Offer `prd-architect` — once the questionnaire is answered, the next step is turning
those answers into product requirements.

---

**Verification:** Every "resolves to stakeholder-questionnaire" row above contains the word
"questionnaire" to anchor routing logic.
