# Large-scale execution (100–500+ repos)

**When:** `repos_in_scope` > 50 or user indicates enterprise workspace.

## Strategy

1. **Classify first** — [repo-classification.md](repo-classification.md); shrink graphs before deep dive.
2. **Tiered depth** — Tier 0/1: full deep dive; Tier 2/3: catalog + critical-path touch only.
3. **Batch manifest** — update `repos[]` in chunks of 50; sort **ascending by name**.
4. **SHA resume** — skip re-scan when `repos[].sha` unchanged.
5. **Convergence** — fixed column order, fixed enums, fixed section order in all deliverables.

## Graph scope

Default service/runtime graphs: `application`, `infrastructure`, `schema` only.

Libraries/SDKs appear as dependency leaves — never as bounded-context owners without evidence.

## Phase adjustments

| Phase | Large-scale note |
|-------|------------------|
| Session 0 | Classification provisional OK; full enum by P0 end |
| P0 | Census in batches; `KNOWN_OMISSIONS.md` for bulk excludes |
| P0.5 | Per-tier-0/1 `/understand` first; defer tier 2/3 mechanical pass |
| P1 | Deep dive tier 0/1 only unless flow-critical |
| P2 | ≥3 business flows from product lines — not per-repo flows |
| P2b | Entry services = tier 0/1 Datadog names only |
| P4 | Top 10 smells ranked — not exhaustive per-repo prose |
| P5 | Evidence summary mandatory; overall confidence in EXEC_SUMMARY |

## Agent parity

Two agents with same repo set and SHAs must produce:

- Identical artifact file set
- Identical table columns and enum values
- Content may differ only where evidence paths differ
