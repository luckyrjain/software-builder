# Phase outputs (normative)

**Mandatory.** Each comprehension phase is **incomplete** until every listed artifact exists with required
fields populated or explicitly marked `UNKNOWN` with reason. Two agents following this skill must produce
the same artifact set; content may differ only where evidence differs.

Completion gate: [phase-completion-gate.md](phase-completion-gate.md). Machine state: `manifest.yaml`
([manifest-schema.md](manifest-schema.md)). Machine domain model:
[machine-domain-model.md](machine-domain-model.md). Large workspaces:
[large-scale-execution.md](large-scale-execution.md).

---

## Session 0 — Bootstrap

| Output | Location | Required fields |
|--------|----------|-----------------|
| Domain config | `domain-config.yaml` | All schema fields or defaults |
| Workspace inventory | `PROGRESS.md` § Repo status | Repo, branch, SHA, tier (provisional), [classification](repo-classification.md) |
| Discovery budget | root `manifest.yaml` + `PROGRESS.md` | Profile/limits + consumed repositories/search queries/deep reads initialized; manifest is machine source of truth |
| Known omissions (seed) | `KNOWN_OMISSIONS.md` | MCP gaps, bulk excludes |
| Entry services (provisional) | `{map_file}` § Inventory stub | Repo, entry-point type, file path |
| Known domains / scope | `domain-config.yaml` `scope` | include_keywords, seed_repos |
| Missing repositories | `UNKNOWNS.md` | Expected but absent repos |
| Initial unknowns | `UNKNOWNS.md` | ≥0 rows; five questions DRAFT in `EXEC_SUMMARY.md` |
| Evidence summary (stub) | `EXEC_SUMMARY.md` + `manifest.evidence_summary` | Counters initialized to 0 |
| Deliverable stubs | All `templates/` copies, including `PRD.md` and machine YAMLs | Non-empty headers/schema only |

---

## Session 0b — Squad enrichment

| Output | Location | Required fields |
|--------|----------|-----------------|
| MCP profile | `SQUAD_MAP.md` header | GitLab/Datadog status |
| Squad map | `SQUAD_MAP.md` | Per in-scope repo: GitLab squad, Datadog team, confidence |

Skip allowed when both MCP ❌ — document skip reason in header; record in `KNOWN_OMISSIONS.md`.

---

## P0 — Inventory

| Output | Location | Required fields |
|--------|----------|-----------------|
| Repository census | `{map_file}` § Inventory | Full table: classification enum + evidence per repo |
| Technology stack | `{map_file}` § Inventory | Per repo: languages, frameworks, build tooling |
| Bounded contexts (initial) | `BOUNDED_CONTEXTS.md` | Context name, repos, confidence |
| Config surface | `{map_file}` § Inventory | Config table (names only) |
| Repo relationships | `{map_file}` § Inventory | Relationship table |
| `manifest.repos[]` | `manifest.yaml` | name, branch, sha, tier, classification, inventory: complete |
| Discovery budget checkpoint | root `manifest.yaml` + `PROGRESS.md` | Configured + consumed counters synchronized; PARTIAL if exhausted before gate |

---

## P0.25 — Contracts

| Output | Location | Required fields |
|--------|----------|-----------------|
| Contract inventory | `{map_file}` § Contracts | Full contract table |
| API catalog | `API_CATALOG.md` | method, path, producer, consumers, implementation, exercise |
| Event catalog | `EVENT_CATALOG.md` | topic, schema, producer, consumers, implementation, exercise |
| Machine API/event schema | `API_EVENT_SCHEMA.yaml` | source revision + stable API/event records with owner/direction/contract/evidence/confidence |
| Error code catalog | `{map_file}` § Contracts | Code, message, HTTP status, repo, evidence |

---

## P0.5 — Mechanical model

| Output | Location | Required fields |
|--------|----------|-----------------|
| Mechanical insights | `{map_file}` § Mechanical Insights | Top files, endpoints, cycles, essential files |
| Service call graph | `DEPENDENCY_GRAPH.md` § Service call | Mermaid + confidence |
| Machine dependency graph (initial) | `DEPENDENCY_GRAPH.yaml` | focal perspective + source/target/direction/interaction/criticality/evidence/confidence |
| Graph manifest | `.understand-anything/manifest.json` | Tier 0/1 entries ok or failed |
| Metrics | `.understand-anything/metrics.csv` | Present or N/A with reason |

---

## P1 — Deep dives

| Output | Location | Required fields |
|--------|----------|-----------------|
| Per-repo deep dives | `{map_file}` § Per-Repo Deep Dives | One subsection per in-scope application repo |
| Bounded contexts (refined) | `BOUNDED_CONTEXTS.md` | Context cards + logical context Mermaid |
| Data ownership (initial) | `DATA_OWNERSHIP.md` | Per entity: authoritative source, repository methods, replicas, caches |
| Machine data ownership (initial) | `DATA_OWNERSHIP_GRAPH.yaml` | evidenced nodes/edges + owner/evidence/confidence |
| Capability traceability (initial) | `CAPABILITY_TRACEABILITY.yaml` | capability → repos/code locations/owner/evidence/confidence |
| Domain glossary | `DOMAIN_GLOSSARY.md` | Terms, definitions, evidence paths |
| Ownership cards | `{map_file}` § Per-Repo Deep Dives | Owns / does-not-own per repo |
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence |
| Auth & Gateway | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence |

---

## P2 — Flow

| Output | Location | Required fields |
|--------|----------|-----------------|
| Trigger catalog | `{map_file}` § Flow | All trigger types + entry repo |
| Runtime sequence | `{map_file}` § Flow | Numbered narrative + sequence Mermaid (happy + failure) |
| Business flows | `BUSINESS_FLOWS.md` | **≥3** journeys per [business-flows.md](business-flows.md) |
| Critical path | `{map_file}` § Flow + [critical-path.md](critical-path.md) | Vertical chain diagram |
| State machine | `STATE_MACHINE.md` | States, transitions, Mermaid |
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config, plus per-env base URL (BFF + direct ingress) |
| Machine dependency graph (refined) | `DEPENDENCY_GRAPH.yaml` | sync/async boundaries + upstream/downstream semantics + evidence-backed criticality |
| Sync/async boundaries | `{map_file}` § Flow | Boundary table |
| Code/graph divergence | `{map_file}` § Flow | Classified edges |

Diagrams: [required-diagrams.md](required-diagrams.md).

---

## P2b — Runtime validation (Datadog and/or KubeSense)

| Output | Location | Required fields |
|--------|----------|-----------------|
| Runtime validation | `{map_file}` § Runtime validation (Datadog) **or** stub+link to `E2E_FLOW.md` § Runtime validation | Three-way table per hop (full table in map or supplement) |
| KubeSense log evidence | `{map_file}` § Runtime validation (Datadog) | Exact quoted error strings, workload, namespace, filter SQL — required when KubeSense ✅ |
| Runtime graph | `DEPENDENCY_GRAPH.md` § Runtime | Datadog-confirmed edges |
| Machine dependency runtime reconciliation | `DEPENDENCY_GRAPH.yaml` | runtime-confirmed/divergent edges retain evidence/confidence; no telemetry-only intent invention |
| Exercise updates | API/event catalogs + business flows | `runtime_confirmed` where applicable |
| Datadog subgraphs | `.understand-anything/diagrams/datadog-service-deps.md` | Per entry service |

---

## P3 — Core domain deep dive

| Output | Location | Required fields |
|--------|----------|-----------------|
| Core section | `{map_file}` § core_section | Idempotency, routing, failure, etc. |
| Implementation matrix | `EXEC_SUMMARY.md` | implementation + exercise axes |
| Data ownership (refined) | `DATA_OWNERSHIP.md` | Complete entity table |
| Machine data ownership (refined) | `DATA_OWNERSHIP_GRAPH.yaml` | authoritative writer/source + replicas/caches/indexes/consumers reconciled |
| Capability traceability (refined) | `CAPABILITY_TRACEABILITY.yaml` | material capabilities mapped to all evidenced code locations |
| Draft five questions | `EXEC_SUMMARY.md` | Updated through P3 |
| Overall confidence | `EXEC_SUMMARY.md` + `manifest.overall_confidence` | Per [confidence-rubric.md](confidence-rubric.md) |

Enums: [implementation-status.md](implementation-status.md). Precedence: [evidence-precedence.md](evidence-precedence.md).

---

## P3b — Adversarial

| Output | Location | Required fields |
|--------|----------|-----------------|
| Fraud & compliance | `{map_file}` § Fraud & Compliance | Control, exists?, confidence, gaps |

---

## P4 — Quality & ops

| Output | Location | Required fields |
|--------|----------|-----------------|
| Quality & ops | `{map_file}` § Quality & Ops | Tests, observability, correlation IDs, debt, feature toggles, non-entity Redis/ES usage |
| Runbook | `RUNBOOK.md` | All procedures or explicit ⚠️ absent |
| Smells (full) | `RISK_MAP.md` § Architectural smells | Complete scan |
| Top smells | `RISK_MAP.md` § Top smells | ≤10 ranked rows |
| Change impact | `BOUNDED_CONTEXTS.md` + `RISK_MAP.md` § Change impact | Per-context if-modified tables |
| Change-risk map | `RISK_MAP.md` § Change risk | Safe / Moderate / High / Unknown |
| Evidence summary | `EXEC_SUMMARY.md` + manifest | All counters updated |

---

## P5 — Synthesis

| Output | Location | Required fields |
|--------|----------|-----------------|
| Final five questions | `EXEC_SUMMARY.md` | COMPLETE or UNKNOWN each |
| As-built PRD | `PRD.md` | Scope/type, actors, capabilities, `FR-*`/`BR-*`/`NFR-*`, journeys, state/lifecycle, interfaces, data ownership, dependencies, controls, deployment/ops, failures, constraints, risks/gaps, requirement traceability, open product-intent questions |
| PRD traceability | `PRD.md` § Requirement traceability | Every `FR-*`, `BR-*`, `NFR-*` maps to evidence; unsupported statements marked `Inferred` or `Unknown` |
| Machine API/event schema (final) | `API_EVENT_SCHEMA.yaml` | reconciled current-state records + source revisions/evidence/confidence |
| Machine data ownership (final) | `DATA_OWNERSHIP_GRAPH.yaml` | reconciled current-state nodes/edges + source revisions/evidence/confidence |
| Machine dependency graph (final) | `DEPENDENCY_GRAPH.yaml` | reconciled current-state dependency semantics + source revisions/evidence/confidence |
| Capability traceability (final) | `CAPABILITY_TRACEABILITY.yaml` | reconciled capability→code ownership + source revisions/evidence/confidence |
| Stale-PRD result | root `manifest.yaml` PRD artifact row + `PROGRESS.md` (DELTA/ADD_REPO) | manifest `ok` after clean comparison/regeneration or `stale` immediately on stale condition; human reason/evidence required; silent `ok` retention forbidden |
| Overall confidence | `EXEC_SUMMARY.md` | Question table + overall band |
| Engineering leader summary | `EXEC_SUMMARY.md` § Engineering Leader Summary | [engineering-leader-summary.md](engineering-leader-summary.md) |
| Architecture decisions | `ARCHITECTURE_DECISIONS.md` | ADRs or UNKNOWN |
| Repo map table | `EXEC_SUMMARY.md` | classification + squad + tier + branch + SHA |
| Evidence summary (final) | `EXEC_SUMMARY.md` + manifest | All counters populated |
| Section confidences | `EXEC_SUMMARY.md` | Per major section |
| `PROGRESS.md` | `FIRST_PASS_COMPLETE` | All checkpoints; impossible while manifest PRD status is `stale` |
| Per-repo Memory Bank | `<repo>/memory-bank/*.md` | When `memory_bank.export_mode: p5` — see [memory-bank-integration.md](memory-bank-integration.md) |
| `manifest` `memory_bank_export` | `manifest.yaml` | `ok` \| `waived` \| `n_a` per export_mode |
| Postman/curl export | `postman/*` | When `api_tooling.export_mode: p5` — see [api-tooling-integration.md](api-tooling-integration.md) |
| `manifest` `api_tooling_export` | `manifest.yaml` | `ok` \| `waived` \| `n_a` per export_mode |

P5 machine reconciliation follows [machine-domain-model.md](machine-domain-model.md). A missing required machine
artifact or stale PRD in FULL mode makes P5 incomplete/PARTIAL. DELTA/ADD_REPO must refresh affected
projections, run the stale-PRD gate, and synchronize the PRD manifest row before claiming the retained PRD is
current.

`PRD.md` is current-state/as-built. Do not infer desired future behavior, roadmap, business priority,
product goals, personas, KPI targets, or SLO targets from code/runtime observations. When authoritative
product documentation supplies one of these, cite it under normal evidence precedence; otherwise record
it as a product-intent unknown.

---

## Cross-cutting rules

1. **Section confidence** = minimum of supporting evidence blocks.
2. **Overall confidence** = minimum of five questions + weakest section.
3. **UNKNOWN > speculation** — empty required table → phase incomplete.
4. **KNOWN_OMISSIONS** ≠ **UNKNOWNS** — scope limits vs unanswered questions.
5. **Diagrams** — missing required diagram → incomplete unless waived with reason in omissions/unknowns.
6. **Evidence summary** — update `manifest.evidence_summary` every phase end.
7. **PRD traceability** — every `FR-*`, `BR-*`, and `NFR-*` must cite implementation/contract/config/test/runtime or authoritative documentation evidence; contradictions stay visible.
8. **Machine traceability** — every populated machine record/edge/capability carries evidence/confidence and source revision; contradictions remain visible rather than being averaged or overwritten.
9. **Discovery budget** — persist configured/consumed counters in manifest machine state and mirror to `PROGRESS.md`; limit exhaustion before completion produces PARTIAL + `UNKNOWNS.md`, never silent overrun.
10. **PRD freshness** — DELTA/ADD_REPO sets manifest PRD status `stale` before any current-state claim when a stale condition fires; only a clean regeneration/comparison restores `ok`.
11. **Time & Effort** — refresh `EXEC_SUMMARY.md` § Time & Effort every phase end: append/update that
   phase's row from `manifest.phases.<key>.completed_at`, measured against the previous non-skipped
   completed phase (first completed phase's elapsed is `—` — no prior anchor, never fabricate one) and
   formatted as `<h>h <m>m` (e.g. `1h 12m`); set `engagement.model_used` at Session 0 if knowable (leave
   `null`/`UNKNOWN` otherwise — never guess).