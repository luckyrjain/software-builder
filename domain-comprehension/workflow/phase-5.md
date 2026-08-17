---
workflow_version: 2.0
phase: 5
produces:
  - final_five_questions
  - as_built_prd
  - prd_requirement_traceability
  - api_event_schema_final
  - data_ownership_graph_final
  - dependency_graph_final
  - capability_traceability_final
  - stale_prd_status
  - overall_confidence_final
  - engineering_leader_summary
  - architecture_decisions
  - repo_map_table
  - evidence_summary_final
  - section_confidences
  - progress_status
consumes:
  - quality_ops_section
  - runbook
  - top_smells
  - change_risk_map
  - evidence_summary
  - core_domain_deep_dive
  - fraud_compliance_review
  - business_flows
  - state_machine
  - api_catalog
  - event_catalog
  - data_ownership
---

# Comprehension Phase P5 — Delivery and handoff

Final evidence review, as-built PRD synthesis, machine-model reconciliation, section confidence calibration,
and delivery checklist.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Final five questions | `EXEC_SUMMARY.md` | COMPLETE or UNKNOWN each — no DRAFT allowed | Phase incomplete |
| As-built PRD | `PRD.md` | Current-state scope, actors, capabilities, requirements/rules/NFRs, workflows, state, interfaces, data, dependencies, controls, operations, failures, constraints, risks/gaps, traceability, open product-intent questions | Phase incomplete |
| PRD requirement traceability | `PRD.md` § Requirement traceability | Every `FR-*`, `BR-*`, `NFR-*` cites evidence and has confidence/status | Phase incomplete |
| API/event machine schema | `API_EVENT_SCHEMA.yaml` | source revisions + stable API/event records with evidence/confidence | Phase incomplete in FULL |
| Data ownership machine graph | `DATA_OWNERSHIP_GRAPH.yaml` | source revisions + evidenced nodes/edges/owner/confidence | Phase incomplete in FULL |
| Dependency machine graph | `DEPENDENCY_GRAPH.yaml` | focal perspective + direction/interaction/criticality/evidence/confidence | Phase incomplete in FULL |
| Capability traceability | `CAPABILITY_TRACEABILITY.yaml` | capability → repos/code locations/owner/evidence/confidence | Phase incomplete in FULL |
| DELTA/ADD_REPO PRD freshness | root `manifest.yaml` PRD artifact row + `PROGRESS.md` | manifest `ok` after clean comparison/regeneration; `stale` immediately on stale condition + human reason/evidence | Phase incomplete if unchecked or stale |
| Overall confidence | `EXEC_SUMMARY.md` | Question table + overall band | Phase incomplete |
| Engineering leader summary | `EXEC_SUMMARY.md` § Engineering Leader Summary | Per [engineering-leader-summary.md](../reference/engineering-leader-summary.md) | Phase incomplete |
| Architecture decisions | `ARCHITECTURE_DECISIONS.md` | ADRs or UNKNOWN | Phase incomplete |
| Repo map table | `EXEC_SUMMARY.md` | classification + squad + tier + branch + SHA per repo | Phase incomplete |
| Evidence summary (final) | `EXEC_SUMMARY.md` + manifest | All counters populated (non-zero where evidence exists) | Phase incomplete |
| Section confidences | `EXEC_SUMMARY.md` | Per major section | Phase incomplete |
| PROGRESS.md status | `PROGRESS.md` | `FIRST_PASS_COMPLETE` or explicit PARTIAL reason | Phase incomplete |

## As-built PRD synthesis

Use [templates/PRD.md](../templates/PRD.md) as the required skeleton. The PRD is a projection of the
completed comprehension evidence into a requirements-oriented document; do not perform a second,
independent product-discovery pass that can drift from the domain artifacts.

1. Set the scope to the in-scope service(s), bounded context, or domain from `domain-config.yaml` and the
   final inventory. A service-only run is valid; do not invent a larger product boundary.
2. Derive actors/consumers and capabilities from evidenced entry points, callers/consumers, contracts,
   flows, and ownership. Human personas are only named when authoritative evidence supports them.
3. Create stable requirement IDs:
   - `FR-*` for externally or internally observable functional behavior;
   - `BR-*` for business rules, eligibility/validation rules, invariants, limits, and state-transition
     preconditions;
   - `NFR-*` for evidenced operational/correctness properties such as idempotency, consistency, ordering,
     retries, rate limits, security, availability behavior, scaling constraints, and recovery behavior.
4. For each requirement record evidence, scope, confidence, and status:
   - `Observed` — directly established by executable code, contract/schema, config, or authoritative
     documentation under [evidence-precedence.md](../reference/evidence-precedence.md);
   - `Inferred` — not stated directly but supported by multiple corroborating signals; explain the
     inference and keep confidence no higher than its weakest material support;
   - `Unknown` — evidence is insufficient or contradictory. Preserve the question in `UNKNOWNS.md`.
5. Reconcile `BUSINESS_FLOWS.md`, `STATE_MACHINE.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`,
   `DATA_OWNERSHIP.md`, `{map_file}`, `DEPENDENCY_GRAPH.md`, `ARCHITECTURE_DECISIONS.md`, `RISK_MAP.md`,
   `RUNBOOK.md`, tests/config, and runtime validation. If two artifacts disagree, show the contradiction;
   do not silently choose one.
6. Treat telemetry as behavioral corroboration only. Observed traffic volume, p95 latency, error rate,
   replica count, or throughput is **not** an intended KPI/SLO/NFR target unless a source/config/contract
   explicitly establishes it as such.
7. Do not manufacture product intent from implementation: no invented problem statement, goals,
   non-goals, personas, roadmap, success metric, target SLO, MVP boundary, prioritization, or future
   acceptance criteria. Put unrecoverable intent into `PRD.md` § Open product-intent questions and
   `UNKNOWNS.md`.
8. Populate `PRD.md` § Requirement traceability with every `FR-*`, `BR-*`, and `NFR-*`. No requirement
   may exist only in prose without a corresponding traceability row.
9. Apply the same safe-rendering and prompt-injection boundary as all other deliverables.

## Machine-domain reconciliation

Run [machine-domain-model.md](../reference/machine-domain-model.md) before completion. In FULL mode, parse
and reconcile all four machine artifacts against the narrative catalogs/graphs and current source revisions.
Every populated machine record/edge/capability retains evidence and confidence; missing or contradictory
fields become UNKNOWN/Conflicted according to evidence precedence rather than being guessed.

For DELTA/ADD_REPO, compare previous versus refreshed source revisions and machine projections using
`stale_prd_detection` in [domain-model-contract.yaml](../reference/domain-model-contract.yaml). If any stale
condition fires, set root `manifest.yaml` `artifacts[id=prd].status: stale` immediately and record the reason
and evidence in `PROGRESS.md`. Update the affected PRD requirements/traceability and restore manifest `ok` only
after a clean comparison; otherwise keep the phase/engagement incomplete. Never claim an unchecked or stale
PRD is current, and never leave a known-stale PRD as manifest `ok`.

The machine files plus `PRD.md` and its manifest freshness status form the current-state handoff to
**prd-architect**. That skill may propose a future state, but it must preserve observed evidence and make every
change explicit.

## Memory Bank export (optional)

When `domain-config.yaml` `memory_bank.export_mode` is `p5` or (`optional` and user requested export):

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Per-repo memory banks | `<repo>/memory-bank/*.md` | Six core files per export-target repo | Required when `export_mode: p5` |
| Generated appendix | `<repo>/memory-bank/.generated/` | Refreshed when P0.5 graphs exist | Recommended |
| Manifest artifact | `manifest.yaml` `memory_bank_export` | `ok` \| `waived` \| `n_a` | Update every P5 |

**Procedure:** [memory-bank-integration.md](../reference/memory-bank-integration.md).

**Do not** run a separate cursor-bank "initialize memory bank" pass when P5 export completes — export
projects comprehension deliverables into Memory Bank format.

When `export_mode: never`, set manifest `memory_bank_export` → `n_a`.

## API tooling export (optional)

When `domain-config.yaml` `api_tooling.export_mode` is `p5` or (`optional` and user requested export):

| Output | Location | Required fields | Note |
|--------|----------|------------------|------|
| Postman collection | `postman/postman_collection.json` | Numbered folder per in-scope repo/service, built from `API_CATALOG.md` + P1 Auth & Gateway + P2 Deployment base URLs | Required when `export_mode: p5` |
| Per-env environment files | `postman/postman_environment.<env>.json` (one per `api_tooling.envs`) | Importable, base URL from § Deployment | Required |
| Generator config | `postman/environment.defaults.json` | Not imported — `gen_postman.py` input | Required |
| Generator script | `postman/gen_postman.py` | Regenerates env files, patches collection (`appVersion`/`versionCode` sync) | Required |
| OTP helper | `postman/fetch_otp_from_redis.py` | Only when `api_tooling.otp_helper` resolves to on (see below) | Conditional |
| README | `postman/README.md` | Import steps, Happy Path, Newman command | Required |
| Manifest artifact | `manifest.yaml` `api_tooling_export` | `ok` \| `waived` \| `n_a` | Update every P5 |

**`otp_helper` resolution:** `always` → always write it; `never` → never; `auto` (default) → write it only
if any in-scope repo's P1 Auth & Gateway subsection recorded Redis OTP-pattern usage — cite the evidence in
the script's header comment.

**Procedure:** [api-tooling-integration.md](../reference/api-tooling-integration.md).

**Evidence rule:** every request in the collection traces to an `API_CATALOG.md` row. A route with no
evidenced auth model (P1 recorded `UNKNOWN`) gets a commented-out placeholder header in the collection —
never an invented value.

When `export_mode: never`, set manifest `api_tooling_export` → `n_a`.

## Phase packet merge (when used)

When earlier phases wrote [phase packets](../reference/run-scoped-artifacts.md#smaller-phase-packets)
(`{artifact_root}/packets/P0-inventory.md`, etc. — QUICK delivery or `repos_in_scope` > 50) instead of
editing `{map_file}` directly, merge every packet into the canonical deliverables under
`artifact_root` now, before PRD synthesis and the completion-gate checklist below: fold each packet's
findings into `EXEC_SUMMARY.md` and `{map_file}` in the same section structure a non-packet run would have
produced. Packets are working notes, not a second source of truth — once merged, the manifest's
required-artifact checks (`EXEC_SUMMARY.md`, `{map_file}`) are what's authoritative, exactly as in a run
that never used packets.

## Post-action Jira paste

Optional — on completion, offer the Jira summary paste (never post without explicit user confirmation) per
[post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md) §3b.

## Definition of Done

[phase-completion-gate.md](../reference/phase-completion-gate.md)
