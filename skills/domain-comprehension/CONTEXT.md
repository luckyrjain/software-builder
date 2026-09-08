# Target System Analysis

Vocabulary for describing **customer systems** — the repositories, services, and business domains a skill analyzes inside a **target workspace**. This context is produced and consumed by domain-comprehension, squad-map, prd-architect, and org-wide rollup skills. It is not vocabulary for the Software Builder platform itself; see [../CONTEXT.md](../CONTEXT.md).

## Scope boundary

**Target workspace**:
The repository or multi-repo workspace under analysis. Artifacts from this context are written into the target workspace (e.g. `docs/domain-comprehension/<domain-slug>/`, `SQUAD_MAP.md` at workspace root) unless a skill explicitly scopes otherwise.

_Avoid_: Platform repo, software-builder checkout (unless that is the declared target)

**Engagement**:
A domain-comprehension run over a target workspace — tracked in root `manifest.yaml` with delivery mode, artifact root, and completion status. An engagement is resumable; it is not a one-shot chat turn.

_Avoid_: Session (too generic), project (overloaded)

## Architecture discovery

**Bounded context**:
A coherent business area with its own ubiquitous language and data ownership within a target workspace. Identified from repo boundaries, package roots, API namespaces, and domain language in code — not from folder names alone.

_Avoid_: Module, microservice (a service may span or split contexts), package (implementation unit, not a domain boundary)

**Context map**:
The relationships between bounded contexts — who calls whom via API, events, or shared data. Edges require evidence; a shared library does not imply a shared context.

_Avoid_: Architecture diagram (may omit ownership and confidence), dependency graph (technical only)

**Edge context**:
A thin boundary layer (BFF, adapter, gateway) that routes or translates — marked as edge, not core domain. Bank and integration adapters are supporting contexts, not primary business areas.

_Avoid_: Frontend, API layer (too vague without the thin-boundary meaning)

**Data ownership**:
Which bounded context is authoritative for writes to each entity or table. Other contexts reference by ID or consume events; they do not silently share write authority.

_Avoid_: Source of truth (acceptable in prose but prefer data ownership for normative cards)

## Requirements artifacts

**As-built PRD**:
A current-state requirements document reverse-engineered from executable evidence. Requirements carry stable IDs (`FR-*`, `BR-*`, `NFR-*`) and status Observed | Inferred | Unknown with citations. Never manufactures future roadmap, personas, KPIs, or acceptance criteria not grounded in evidence.

_Avoid_: PRD (alone — always qualify as-built), spec (too generic)

**Future-state PRD**:
A forward-looking product requirements document for something not yet built — produced by prd-architect, not domain-comprehension. May include MVP scope, build/no-build verdict, and build-readiness gating.

_Avoid_: Proposal, pitch deck (not a requirements artifact)

**Five questions**:
The mandatory evidence spine for domain-comprehension — what the system is, who uses it, critical path, data ownership, and failure modes. Each answer carries its own confidence; overall confidence is capped by the weakest answer.

_Avoid_: FAQ, checklist (implies optional items)

## Ownership

**Squad**:
An owning team for a repository or runtime service. Resolved from org evidence (GitLab group hierarchy) and runtime evidence (Datadog service team tags). Assignments carry confidence; conflicts between sources are flagged, not silently merged.

_Avoid_: Team (too generic), owner (person vs team ambiguous)

**Org squad**:
Ownership inferred from GitLab group hierarchy, project namespace, or CODEOWNERS.

_Avoid_: GitLab team (implementation detail)

**Runtime squad**:
Ownership inferred from Datadog (or equivalent) service `team` tags on live telemetry.

_Avoid_: On-call team (operational rotation, not ownership mapping)

**Squad map**:
The `SQUAD_MAP.md` artifact listing repos and services with org squad, runtime squad, confidence, and conflict flags. Source of truth for ownership lookups by squad-map, who-owns-x-bot, and Session 0b of domain-comprehension.

_Avoid_: Org chart, RACI (different artifacts)

## Program and cost rollups

**Org rollup**:
A cross-workspace aggregation of homogeneous items (migration status rows, cost-savings rows) with provenance fingerprints. Consumed by aggregators and digests; not a substitute for live analysis of a single workspace.

_Avoid_: Dashboard, executive summary (presentation without provenance)

**Migration status**:
Per-service progress toward PostgreSQL cutover (or similar program), recorded in workspace-local `MIGRATION_STATUS.yaml` and rolled up org-wide by migration-program-manager.

_Avoid_: Migration plan (forward-looking; status is as-built progress)

**Cost sweep item**:
One ranked savings opportunity from a deployment-level rightsizing assessment, aggregated org-wide by cost-optimization-sprint-planner.

_Avoid_: Recommendation (too generic without the rollup context)

## Evidence status

**Observed**:
Directly supported by executable source, configuration, tests, or runtime telemetry tied to a code path.

_Avoid_: Verified (implies human sign-off), confirmed

**Inferred**:
Plausible from multiple indirect signals but not directly executable in one place.

_Avoid_: Assumed, likely

**Unknown**:
Insufficient evidence to state; preferred over speculation in all target-system artifacts.

_Avoid_: TBD, pending

**Delivery mode**:
How much of domain-comprehension's artifact set a run must produce — QUICK, FULL, RESUME, DELTA, ADD_REPO, COMPLIANCE_RETROFIT, or PROPOSAL_CHECK. Modes constrain scope; they are not quality levels.

_Avoid_: Depth setting, tier
