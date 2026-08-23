---
workflow_version: 1.0
phase: analyze
produces:
  - business_impact
  - engineering_drag
  - operational_risk
  - effort
  - priority_score
consumes:
  - debt_items
  - repo_context
  - effort_unit
---

# Analyze — score each debt item on four dimensions

For every item in `debt_items`, score four independent dimensions on a **1–5 scale** (integers), then
combine them into a `priority_score`. Concrete checks per dimension:

## 1. Business impact (1–5)

What does leaving this unfixed cost the business — revenue, customer trust, or compliance exposure?

- Read `description`, `notes`, `ticket_ref` text, and `affected_area` for concrete signals: does the area
  touch payments, auth, PII, or a regulated workflow (compliance/legal exposure)? Does `repo_context` (if
  supplied) show the affected area on a customer-facing critical path?
- 5 = severe revenue/compliance/regulatory exposure (e.g. a known compliance gap, a payments-path defect).
  1 = cosmetic or internal-tooling-only, no customer or revenue path touched.
- Record the concrete evidence cited for the score (which sentence, which repo signal) — this feeds the
  Rationale column in the report.

## 2. Engineering drag (1–5)

How often does this item slow down *unrelated* work — the velocity cost of leaving it in place?

- Look for signals of recurring friction: repeated workarounds mentioned in `notes`/tickets, a module
  named in multiple unrelated tickets, `repo_context` churn/commit-message signals ("workaround for",
  "temporary fix", "TODO") concentrated in the affected area.
- 5 = actively blocks or measurably slows most changes touching this area. 1 = isolated, rarely touched,
  no reported friction.

## 3. Operational risk (1–5)

What's the incident/outage exposure from leaving this unfixed?

- Look for incident history signals in `notes`/`ticket_ref` text or `repo_context` (recent postmortems,
  repeated pages, known fragile dependency) tied to the affected area.
- 5 = active or recurring incident-level exposure (has caused, or is clearly positioned to cause, an
  outage). 1 = no incident history or plausible operational exposure identified.

## 4. Effort (1–5)

Rough sizing to actually fix the item, independent of how urgent it is.

- Map `effort_unit` T-shirt sizes: `S`→1, `M`→2, `L`→4, `XL`→5 (a caller-supplied raw 1–5 score is used
  as-is). Base the estimate on scope described in `description`/`notes` and, when `repo_context` is
  available, the size/coupling of the affected area.
- This is a divisor in the priority-score formula below, not an urgency signal by itself — a large,
  low-urgency item and a small, low-urgency item can both land in `Won't-fix now`; effort only changes
  *where* on that low end they sit.

## Combine into `priority_score`

```
priority_score = (business_impact × engineering_drag × operational_risk) ÷ effort
```

Higher score = higher priority. State this formula in the report, next to the ranked table, so a reader
can recompute any row.

## Evidence gaps

If any of the three multiplicands (business impact, engineering drag, operational risk) cannot be scored
from the available evidence — the description is too vague, no corroborating `repo_context` signal
exists, and no ticket text fills the gap — do **not** guess a value and do **not** silently drop the
item. Record that dimension as `Unknown` for the item and carry `priority_score: Unknown` through to
Report, which surfaces it as an explicit `Unknown — insufficient evidence` state rather than folding it
into `Won't-fix now` or omitting the row. A missing `effort` estimate is treated the same way — never
defaulted to `1` or `5`, since either default would silently distort the score in one direction.
