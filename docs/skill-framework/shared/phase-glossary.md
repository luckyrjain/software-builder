# Phase glossary (shared)

**Normative.** Canonical phase names for cross-skill docs, examples, and handoffs.

**Consumers:** All `reference/phase-index.md` files should align terminology here.

## 1. Canonical phase names

| Canonical | Meaning |
|-----------|---------|
| **Detect** | MCP capability discovery, input resolution |
| **Gather** | Fetch artifacts, metrics, diffs, tickets |
| **Analyze** | Apply rubrics, detectors, sizing logic |
| **Correlate** | Cross-source matching (deploy ↔ errors ↔ infra) |
| **Rank / Validate** | Hypothesis ranking, invariant checks, gates |
| **Report** | Human-readable output + structured metadata |

## 2. pr-review mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial) |
| 0 | `workflow/phase-0.md` | Detect |
| 1 | `workflow/phase-1.md` | Gather |
| 2 | `workflow/phase-2.md` | Analyze |
| 2–3 gate | `workflow/phase-2-3-gate.md` | Validate |
| 3–4 | `workflow/posting.md` | Report (post) |
| 5 | `workflow/phase-5.md` | Report |

Posting phases (3–4) are sub-steps of Report; Phase 5 executive summary is the primary deliverable.

### pr-gatekeeper mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial — webhook event filtering) |
| Gatekeep | `workflow/gatekeep.md` | Gather + Report (delegated entirely to pr-review's own phases) |

No Analyze/Correlate/Rank of its own — pr-gatekeeper's only original logic is the auto-post decision
(`reference/auto-post-policy.md`), which reconciles with pr-review's own Validate/Report phases rather
than replacing them.

## 3. incident-rca mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial) |
| 0 | `workflow/phase-0.md` | Detect |
| 0b | `workflow/phase-0b.md` | Gather (Jira anchor) |
| 1 | `workflow/phase-1.md` | Gather |
| 2 | `workflow/phase-2.md` | Correlate |
| 3 | `workflow/phase-3.md` | Correlate |
| 4 | `workflow/phase-4.md` | Rank / Validate |
| 5 | `workflow/phase-5.md` | Report |

Phase 0b is conditional — runs when user anchors on Jira ticket instead of explicit window.

### incident-triage-agent mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial — paging webhook event filtering, mode selection) |
| Triage | `workflow/triage.md` | Gather + Report (delegated to incident-rca + squad-map) |
| Postmortem | `workflow/postmortem.md` | Gather + Report (delegated to incident-rca + squad-map) |

No Analyze/Correlate/Rank of its own — all investigation and ownership analysis is incident-rca's and
squad-map's. The only original logic is the unattended-gate answering
(`reference/unattended-gate-policy.md`), which reconciles with both wrapped skills' own phases rather
than replacing them.

## 4. k8s mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Orchestrator | `workflow/orchestrator.md` | Detect + route |
| COLLECT | `workflow/collect-metrics.md` (+ modules) | Gather |
| NORMALIZE | (inline in orchestrator) | Gather |
| REASON | `workflow/reason.md`, `*-analysis.md` | Analyze |
| VALIDATE | `workflow/validate.md` | Validate |
| BUILD_GRAPH | `workflow/build-graph.md` | Rank |
| VALIDATE_INVARIANTS | `workflow/validate-invariants.md` | Validate |
| RENDER | `workflow/render.md`, `report.md` | Report |

Pipeline shorthand: **COLLECT → REASON → BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER**.

### squad-map mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial) |
| 0 | `workflow/phase-0.md` | Detect |
| 1 | `workflow/phase-1.md` | Gather + Analyze + Report |

Phase 0 is pure MCP capability detection. Phase 1 combines Gather (MCP queries / CODEOWNERS), Analyze
(reconciliation + confidence scoring), and Report (write `SQUAD_MAP.md`). No separate Correlate or
Validate — the skill is lightweight compared to multi-phase skills.

### who-owns-x-bot mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial) |
| Lookup | `workflow/lookup.md` | Gather (delegated to squad-map) + Report (Slack reply) |

Thinnest skill in the repo — no Analyze, Correlate, or Validate step of its own; all ownership analysis
is squad-map's. Report here means "format one Slack message," not "write a markdown deliverable."

### new-hire-guide mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial) |
| Run tour | `workflow/run-tour.md` | Gather (delegated to squad-map + domain-comprehension) + Analyze (squad-column matching, zero-match handling) + Report (`ONBOARDING_TOUR.md`) |

Like who-owns-x-bot, no Analyze/Correlate/Validate of its own beyond the squad-column-matching and
zero-match logic in Run tour — squad-to-repo resolution is squad-map's, comprehension is
domain-comprehension's. Report here means "curate and link `ONBOARDING_TOUR.md`," not re-run either
wrapped skill's own analysis.

### release-readiness-checker mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial) |
| Run check | `workflow/run-check.md` | Gather (MR-range resolution, delegated pr-review/k8s/incident-rca invocations) + Analyze (verdict aggregation, overall Ready/Not-ready derivation) + Report (`RELEASE_READINESS_REPORT.md`) |

The MR-range resolver (§ Run check step 1) is this skill's one genuinely new Gather-equivalent logic —
every other Gather step is fully delegated. Analyze here is aggregation only (deriving one verdict from
three already-computed verdicts), never re-scoring any wrapped skill's own findings.

### domain-comprehension mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (partial) |
| Session 0 | `workflow/session-0.md` | Detect + Gather (census, classify, draft Q1–Q5) |
| Session 0b | `workflow/session-0b.md` → **squad-map** | Gather (ownership via squad-map delegation) |
| P0 | `workflow/phase-0.md` | Gather (inventory, config/relationship tables) |
| P0.25 | `workflow/phase-0-25.md` | Gather (contract inventory) |
| P0.5 | `workflow/phase-0-5.md` | Analyze (merged graph, mechanical insights) |
| P1 | `workflow/phase-1.md` | Analyze (per-repo deep dives, ownership cards) |
| P2 | `workflow/phase-2.md` | Correlate (E2E flow, state machine, divergence) |
| P2b | `workflow/phase-2b.md` | Validate (Datadog runtime validation) |
| P3 | `workflow/phase-3.md` | Analyze (core domain deep dive) |
| P3b | `workflow/phase-3b.md` | Validate (adversarial fraud/compliance review) |
| P4 | `workflow/phase-4.md` | Rank (quality, ops, RUNBOOK, Top 10 smells) |
| P5 | `workflow/phase-5.md` | Report (EXEC_SUMMARY final synthesis, DoD) |

The most complex pipeline — 12+ phases spanning all canonical categories. Session 0 is unique to this
skill (bootstrap census + five questions). P2b and P3b are conditional on Datadog MCP availability.
User approval gate between P0.25 and P0.5 (mechanical scope checkpoint).

### mysql-to-postgres-sql mapping

| Step | File / script | Canonical |
|------|---------------|-----------|
| Inputs | `workflow/migrate-service.md` §1 | Detect (partial) |
| 1. Scan | `scripts/scan-mysql-dialect.sh` | Gather |
| 2. Classify | P0/P1/P2 tiers in `SKILL.md` | Analyze (risk priority — not confidence) |
| 3. Rewrite | `reference/function-translations.md` | Analyze |
| 4. Config | datasource / driver YAML | Analyze |
| 5. Verify | shadow compare on staging | Validate |
| 6. Gate | scan exit 0 before merge | Validate |

Single-workflow skill — no numbered phases. Optional domain pack load for org file paths; fleet rollup via
`templates/MIGRATION_STATUS.yaml`.

### migration-program-manager mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (`program_manifest`, `staleness_threshold_days`, `state_path`) |
| Run rollup | `workflow/run-rollup.md` | Gather (read `MIGRATION_STATUS.yaml` + `SQUAD_MAP.md` per workspace, never invoked live) + Analyze (squad join, staleness computation, rank/group) + Report (`MIGRATION_PROGRAM_REPORT.md` + `migration_program_rollup.json`) |

Not exempt from Analyze the way a pure scheduling wrapper is — this skill has real Analyze logic of its
own: the squad join (path/name match against `SQUAD_MAP.md`), the staleness computation against its own
persisted state, and the rank/group by squad. Same reasoning as release-readiness-checker's mapping above:
aggregation over already-computed inputs is still Analyze, not a pass-through.

### cost-optimization-sprint-planner mapping

| Phase | File | Canonical |
|-------|------|-----------|
| Inputs | `workflow/inputs.md` | Detect (`sweep_scope`, `cost_rate`, `max_deployments_per_run`, `deadline`, `session_token_budget`) |
| Run sweep | `workflow/run-sweep.md` | Gather (optional namespace/deployment waste-ranking pre-filter query pass, then N delegated k8s-overprovisioning-datadog invocations) + Analyze (squad join, rank by `monthly_savings_total`) + Report (`COST_OPTIMIZATION_SPRINT_REPORT.md` + `cost_optimization_sprint_rollup.json`) |

Same reasoning as migration-program-manager's and release-readiness-checker's mappings above — not
exempt, since the pre-filter ranking query pass and the squad join/rank are this skill's own Analyze
logic, not a pass-through of k8s-overprovisioning-datadog's own analysis (which stays entirely its own,
unmodified, inside each delegated invocation).

## 5. Cross-skill analogies

| Concept | pr-review | incident-rca | k8s | domain-comprehension | squad-map | mysql-to-postgres-sql |
|---------|-----------|--------------|-----|----------------------|-----------|----------------------|
| MCP profile | Phase 0 announces GitLab + posting mode | Phase 0: `Datadog ✅ \| KubeSense …` line | Orchestrator prerequisites + Datadog profile | Session 0b: `GitLab ✅ \| Datadog ✅` line | Phase 0: `GitLab ✅ \| Datadog ✅` line | No MCP — `rg` scan gate |
| Boundary / scope | `review_boundary` — files, MR IID | `from_time`/`to_time`/`service` window | deployment + namespace + env + metrics window | `workspace_root` + repo census + `domain-config.yaml` | `workspace_root` + repo list | `service_path` + scan root |
| Minimum evidence gate | phase-2-3 gate before posting | Phase 4 empty signals → blocked report | `STOP_REASON` when invariants fail or evidence insufficient | P0.5 user approval gate (mechanical scope checkpoint) | Config HARD STOP — no proceed without `squad_path_segment` | Scan exit 0 before merge |
| Gather equivalent | Phase 1 — fetch diff, inventory | Phase 1 — metrics, logs, change stories | COLLECT — 7d Datadog series + manifest | Session 0 + P0 — census, classify, inventory | Phase 1 Steps 2–4 — GitLab + Datadog queries | Scan — dialect hit list |
| Analyze equivalent | Phase 2 — detectors, rubrics | Phases 2–3 — correlate deploy ↔ errors | REASON — sizing analysis modules | P0.5–P3 — graphs, flows, deep dives | Phase 1 Step 5 — reconciliation + confidence | Classify + rewrite SQL + config |
| Report equivalent | Phase 5 executive summary + metadata | Phase 5 RCA report + evidence JSON | RENDER — Human Report + decision graph | P5 — `EXEC_SUMMARY.md` + all deliverables | Phase 1 Step 1 — `SQUAD_MAP.md` | `SERVICE_PG_MIGRATION.md` + `assessment_metadata` |

When writing cross-skill examples, use analogies above: "pr-review Phase 1 ≈ k8s COLLECT ≈ rca Phase 1 ≈ domain-comprehension Session 0 + P0 ≈ squad-map Phase 1 Steps 2–4 ≈ mysql Scan step".

## 6. Artifact glossary

| Artifact | Skill | Produced in |
|----------|-------|-------------|
| `review_boundary` | pr-review | Phase 1 |
| `capability_profile` | pr-review | Phase 1 |
| `review_metadata` | pr-review | Phase 5 |
| `error_signals` | incident-rca | Phase 1 |
| `infra_signals` | incident-rca | Phase 1 |
| `evidence_links` | incident-rca | Phases 1–4 |
| `mcp_profile` | incident-rca | Phase 0 |
| `decision_graph` | k8s | BUILD_GRAPH |
| `validated_graph` | k8s | VALIDATE_INVARIANTS |
| `dora_report` | k8s | RENDER |
| `mcp_profile` | squad-map | Phase 0 |
| `SQUAD_MAP.md` | squad-map | Phase 1 |
| `domain-config.yaml` | domain-comprehension | Session 0 |
| `manifest.yaml` | domain-comprehension | Every phase |
| `EXEC_SUMMARY.md` | domain-comprehension | P5 |
| `BOUNDED_CONTEXTS.md` | domain-comprehension | P1–P3 |
| `DEPENDENCY_GRAPH.md` | domain-comprehension | P0.5–P2 |
| `BUSINESS_FLOWS.md` | domain-comprehension | P2 |
| `RISK_MAP.md` | domain-comprehension | P4 |
| `SERVICE_PG_MIGRATION.md` | mysql-to-postgres-sql | migrate workflow closeout |
| `MIGRATION_STATUS.yaml` | mysql-to-postgres-sql | fleet workspace root (from template) |
| `assessment_metadata` | domain-comprehension, squad-map, mysql-to-postgres-sql | P5 / Phase 1 / migrate closeout |
| `org_rollup_item` | migration-program-manager and cost-optimization-sprint-planner (both implemented) | see [org-rollup-schema.md](org-rollup-schema.md); normalizes `MIGRATION_STATUS.yaml` (`pg_migration_gate` adapter) and `decision_graph` (`k8s_waste` adapter) |
| `MIGRATION_PROGRAM_REPORT.md` | migration-program-manager | Run rollup |
| `migration_program_rollup.json` | migration-program-manager | Run rollup |
| `migration_program_state.json` | migration-program-manager | Run rollup (persisted across runs, owned exclusively by this skill) |
| `COST_OPTIMIZATION_SPRINT_REPORT.md` | cost-optimization-sprint-planner | Run sweep |
| `cost_optimization_sprint_rollup.json` | cost-optimization-sprint-planner | Run sweep |
