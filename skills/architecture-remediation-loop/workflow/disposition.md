---
workflow_version: 1.0
phase: disposition
produces:
  - dispositioned_ledger
consumes:
  - candidate_ledger
---

# Disposition — grill and terminally disposition every candidate

**Goal:** every ledger row without a terminal disposition gets one, using evidence, not ceremony. No new
grilling logic here — engineering-decision-discovery's own tree/frontier/interaction workflow is
authoritative; this step only feeds it one candidate at a time and records its resolution.

## Steps

1. For each ledger row without a terminal disposition, invoke **engineering-decision-discovery** scoped to
   that one candidate — pass its evidence, falsification result, and any unresolved questions
   codebase-architecture-review already flagged.
2. Read `engineering_decision_record`. Map every resolved material question's impact to this skill's
   disposition contract (identical vocabulary to codebase-architecture-review's own candidate strength,
   extended with the terminal states below) — full contract:
   [reference/candidate-ledger.md § Disposition contract](../reference/candidate-ledger.md#disposition-contract).
3. **ACCEPT** or **ACCEPT WITH MODIFICATION** rows continue to Remediate. Record the modification (if any)
   verbatim against the row — Remediate implements what Disposition actually accepted, never the original
   candidate text once it has been modified.
4. **ALREADY SATISFIED** / **DUPLICATE** / **REJECT** / **OUT OF SCOPE** rows are terminal here — record the
   evidence for the disposition and stop; they never reach Remediate.
5. **Contested disposition:** if engineering-decision-discovery's resolution is itself contested (evidence
   conflicts, or a second grilling pass reverses the first), record both passes; a candidate contested twice
   without decisive evidence trips the circuit breaker in [SKILL.md § Circuit breakers](../SKILL.md#circuit-breakers)
   — do not force a disposition past that point.
6. A candidate whose remedy needs a concrete module/interface/seam design before implementation is flagged
   `needs_design: true` on the row (engineering-decision-discovery's own escalation trigger:
   "resolved decisions describe one module's contract, seam, or interface") — Remediate reads this flag.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `dispositioned_ledger` | Session state | Every row has exactly one terminal disposition (or `needs_design` + ACCEPT pending Remediate) | Disposition incomplete — do not proceed to Remediate |

## Read-only boundary

This phase never writes to the repository — engineering-decision-discovery is read-only by its own
contract; only the ledger (session state) is updated.
