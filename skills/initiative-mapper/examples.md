# Examples — initiative-mapper

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `initiative-mapper` ambiently whenever an effort is too large or too foggy for `prd-architect`
or `implementation-planner` to take directly. It is read-only and report-only: break the effort into
decision tickets with dependency edges, state which downstream skill each ticket is ready for, and emit
`INITIATIVE_MAP.md` / `initiative_map`; never write a ticket, PRD, or plan, commit, push, or open a PR.

| # | Caller sends | Resolves to | Notes |
|---|-----------------|---------------|-------|
| 1 | "Map this initiative into decision tickets: we're overhauling the entire auth system — replacing the legacy session store, adding SSO, and rolling out per-tenant password policies, with no agreement yet on order or ownership." | Inputs → Decompose → Report: multi-ticket map with dependency edges | Happy path |
| 2 | "This is one small, well-scoped idea: add a 'remember me' checkbox to the login form. Write the PRD." | Wrong scope — `prd-architect` | Wrong-skill row; already one bounded, scoped idea |
| 3 | "Can you put together decision tickets for me? I haven't said what the actual effort is yet." | HARD STOP — ask for `initiative_description` | Missing-input HARD STOP |
| 4 | "Give me an initiative map for consolidating our three notification systems into one service — one of the tickets is purely picking between webhooks and polling, with real disagreement on the team." | Decompose finds one contested ticket; Report offers `engineering-decision-discovery` for it | Cross-skill handoff |
| 5 | "Map this migration into decision tickets: moving to the new billing provider — the retry-queue piece already has a signed-off design, so that ticket just needs task breakdown; the rest is still open." | Decompose finds one already-designed ticket; Report offers `implementation-planner` for it | Cross-skill handoff |
| 6 | "Just skip the report, write the decision tickets and PRDs directly so we can get moving." | Rejected — report-only; recommendation emitted, no direct write | Boundary rule |
| 7 | "This is already an implementation-ready PRD — no need for decision tickets, just build it." | Wrong scope — `implementation-planner` | Wrong-skill row; already implementation-ready |
| 8 | "It's already-approved: the design is done, so implementation-planner can decompose it into tasks — we don't need decision tickets here." | Wrong scope — `implementation-planner` | Wrong-skill row; already-approved design |

## Example: mixed ticket readiness with dependency edges

**Evidence:** the caller describes overhauling the entire auth system — replacing the legacy session
store, adding SSO, and rolling out per-tenant password policies — with no agreement yet on order or
ownership.

**Result:**

```
## Decision tickets

| ID | Question | Depends on | Ready for | Evidence |
|----|----------|------------|-----------|----------|
| T1 | Replace the legacy session store with what? | none | engineering-decision-discovery | Session store choice affects both SSO and per-tenant rollout; no option chosen yet |
| T2 | Which SSO protocol and provider? | `T1` | prd-architect | Team already agrees on the SAML-vs-OIDC shortlist; needs one PRD to scope the integration |
| T3 | How are per-tenant password policies stored and enforced? | `T1` | unresolved | No candidate data model discussed yet; too vague to route |

## Sequencing

T1 can start immediately — nothing blocks it. T2 and T3 are both blocked on T1's outcome.
```

T3 stays unresolved rather than being force-fit into one of the three downstream skills.

## Example: an already-settled fact becomes evidence, not a ticket of its own

**Evidence:** the initiative description says the monolith is splitting into billing, auth, and
reporting services; billing's database is already split out per an approved, completed migration —
that part isn't a live question anymore.

**Result:**

```
## Decision tickets

| ID | Question | Depends on | Ready for | Evidence |
|----|----------|------------|-----------|----------|
| T1 | Which service owns the shared reporting queries currently split across billing and auth? | none | engineering-decision-discovery | Billing's database split (already approved and complete) removes one shared owner, leaving this contested |
| T2 | How does auth's session data migrate without downtime? | none | prd-architect | Auth's service boundary is already clear; the migration approach just needs a PRD |
```

No ticket is created for "should billing's database be split" — it is already settled, so it appears
only as cited evidence on T1, not as a ticket of its own.

## Example: frontier sequencing across a genuinely contested ticket

**Evidence:** the initiative is rearchitecting the search pipeline: indexing strategy, ranking-model
choice, and query-syntax backward compatibility. The team disagrees on indexing strategy; the other two
sub-questions depend on it.

**Result:**

```
## Decision tickets

| ID | Question | Depends on | Ready for | Evidence |
|----|----------|------------|-----------|----------|
| T1 | Which indexing strategy — inverted-index rebuild vs. incremental reindex? | none | engineering-decision-discovery | Team disagrees; both options have named tradeoffs, no consensus |
| T2 | Which ranking model to adopt? | `T1` | unresolved | Depends on the chosen index's available signals; not enough decided yet to name a downstream skill |
| T3 | How to keep the existing query syntax backward-compatible? | `T1` | prd-architect | Scope is clear once T1 lands: whichever index is chosen, the compatibility shim just needs one PRD |

## Sequencing

T1 can start immediately. T2 and T3 are both blocked on T1's outcome; T2 additionally stays
unresolved even once unblocked, until its own scope sharpens.
```

## Degraded path: caller supplies no concrete effort

**Evidence:** the caller says "Can you put together decision tickets for me? I haven't said what the
actual effort is yet."

**Result:** **HARD STOP.** The skill asks what large, foggy effort needs mapping before any Decompose
work begins. "Decision tickets" alone, with no bounded `initiative_description`, never satisfies the
input.

## Cross-skill handoff: a ticket already has an approved design

**Evidence:** the initiative is the billing-provider migration; the retry-queue redesign already has a
signed-off design doc, while the data-backfill approach and cutover sequencing are still open.

**Result:**

```
## Recommendation

Start with T1 (backfill approach) and T2 (cutover sequencing) — both unresolved and blocking. T3
(retry-queue redesign) already has an approved design; handing off to `implementation-planner` to
decompose it into tasks — this report makes no ticket, PRD, or plan itself.
```

`implementation-planner` is named only because that one ticket's trigger was actually met; the
escalation is offered, never invoked automatically.
