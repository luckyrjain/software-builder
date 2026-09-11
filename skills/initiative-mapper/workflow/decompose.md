---
workflow_version: 1.0
phase: decompose
produces:
  - decision_tickets
  - sequencing
consumes:
  - initiative_description
---

# Decompose — build the decision-ticket map

Break `initiative_description` into decision tickets: bounded sub-questions that need answering before
implementation can begin. For each ticket, record:

1. **Question** — the specific sub-question, not a restatement of the whole initiative.
2. **Depends on** — which other tickets (if any) must be resolved first.
3. **Ready for** — which downstream skill this ticket is ready for right now:
   `engineering-decision-discovery` (it's one unresolved decision with contested alternatives),
   `prd-architect` (it's scoped enough for a single PRD), or `implementation-planner` (it already has
   an approved design and just needs task decomposition). A ticket with none of these yet — still too
   vague — stays unresolved rather than being force-fit into one.
4. **Evidence** — why this ticket matters, cited to the initiative description or repository evidence.

A ticket is created only when it materially affects sequencing; do not create a ticket for a fact
already settled by evidence — that becomes evidence on a ticket, not a ticket of its own.

Compute a suggested sequencing (which tickets can start immediately, which are blocked) from the
dependency edges — the same frontier logic `engineering-decision-discovery` uses for its decision tree,
applied at the initiative level.
