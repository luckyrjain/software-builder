# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `workspace_root`, `domain_config`, `delivery_mode` |
| **Session 0** | [workflow/session-0.md](../workflow/session-0.md) | `domain-config.yaml`, deliverables, draft Q1–Q5 |
| **Session 0b** | [workflow/session-0b.md](../workflow/session-0b.md) → **squad-map** | `mcp_profile`, `SQUAD_MAP.md` |
| **P0** | [workflow/phase-0.md](../workflow/phase-0.md) | inventory, config/relationship tables |
| **P0.25** | [workflow/phase-0-25.md](../workflow/phase-0-25.md) | contract inventory |
| **P0.5** | [workflow/phase-0-5.md](../workflow/phase-0-5.md) | merged graph, domain graph, mechanical insights |
| **P1** | [workflow/phase-1.md](../workflow/phase-1.md) | per-repo deep dives, ownership cards |
| **P2** | [workflow/phase-2.md](../workflow/phase-2.md) | E2E flow, state machine, code/graph divergence |
| **P2b** | [workflow/phase-2b.md](../workflow/phase-2b.md) | Runtime validation *(Datadog and/or KubeSense MCP)* |
| **P3** | [workflow/phase-3.md](../workflow/phase-3.md) | core domain deep dive (section name from config) |
| **P3b** | [workflow/phase-3b.md](../workflow/phase-3b.md) | adversarial fraud/compliance review |
| **P4** | [workflow/phase-4.md](../workflow/phase-4.md) | quality, ops, `RUNBOOK.md` |
| **P5** | [workflow/phase-5.md](../workflow/phase-5.md) | `EXEC_SUMMARY` final synthesis, DoD |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| User asks | Phases |
|-----------|--------|
| Full domain map (default) | Inputs → Session 0 → Session 0b → P0 → P0.25 → [approve P0.5] → … |
| Quick orientation only | Inputs → Session 0 → [0b if MCP] → P0 (stop after draft five questions) |
| Resume multi-session | Inputs → read `PROGRESS.md` → continue from Next action |
| Mechanical graphs only | Session 0 → P0.5 (requires prior inventory or seed list) |
| Onboard one new repo into existing map | Inputs (`ADD_REPO`) → P0/P0.25/P0.5/P1 for new repo → merge gate → affected downstream phases per DELTA table |
| Check a proposal against the existing map | Inputs (`PROPOSAL_CHECK`) → precondition check → compare proposal to `BOUNDED_CONTEXTS.md`/`DATA_OWNERSHIP.md`/`API_CATALOG.md`/`EVENT_CATALOG.md` → `PROPOSAL_CHECK_REPORT.md` (read-only, no merge) |

## Phase execution order

```
Session 0 → Session 0b [GitLab/Datadog MCP] → P0 → P0.25 [parallel with P0 tail]
  → [user approves mechanical scope]
  → P0.5 → P1 → P2 → P2b [Datadog/KubeSense MCP] → P3 → P3b → P4 → P5
```
