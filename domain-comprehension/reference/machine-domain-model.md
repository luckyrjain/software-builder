# Machine domain model generation

Normative schema: [domain-model-contract.yaml](domain-model-contract.yaml). Human-readable artifacts remain
canonical narrative evidence; the YAML files are deterministic projections for automation and cross-skill
handoff. Never create a machine fact that is not supported by the same evidence/confidence rules as the
Markdown deliverables.

## Bootstrap

Session 0 copies these stubs from `templates/` into `artifact_root` for every normal engagement so the root
manifest's `stub` artifact rows remain valid:

- `API_EVENT_SCHEMA.yaml`
- `DATA_OWNERSHIP_GRAPH.yaml`
- `DEPENDENCY_GRAPH.yaml`
- `CAPABILITY_TRACEABILITY.yaml`

FULL runs populate and reconcile them through the owning phases. QUICK keeps them as unpopulated stubs unless
the user explicitly requests machine output; their presence does not make them QUICK deliverables. For
DELTA/ADD_REPO, retain existing populated files only after the stale checks below.

Every file records analyzed `source_revision` data once populated. If a repo revision is unknown, record
UNKNOWN/null per the artifact shape; never substitute the current local branch without evidence.

## Phase ownership

| Phase | Machine output | Source narrative/evidence |
|---|---|---|
| P0/P0.25 | `API_EVENT_SCHEMA.yaml` initial API/event records | inventory, `API_CATALOG.md`, `EVENT_CATALOG.md`, committed contracts |
| P0.5/P2/P2b | `DEPENDENCY_GRAPH.yaml` | mechanical graph, flow, deployment/runtime validation |
| P1/P3 | `DATA_OWNERSHIP_GRAPH.yaml` | `DATA_OWNERSHIP.md`, schema/migration/repository evidence |
| P1/P3/P5 | `CAPABILITY_TRACEABILITY.yaml` | bounded contexts, ownership cards, code locations, PRD capabilities |
| P5 | all four | final reconciliation, source revisions, confidence/staleness validation |

## API and event projection

One externally or internally relevant API/event contract becomes one stable record. Required fields come from
the schema contract. `direction` is inbound/outbound relative to the owning service. Contract text identifies
the method+path or topic+schema/version. Consumers/producers that are not evidenced remain UNKNOWN rather than
being inferred from naming alone.

## Data ownership projection

Create nodes for services and evidenced data assets only. Create an ownership/access edge only when a write,
read, cache/index population, migration, repository method, or runtime signal supports it. `owner` means the
authoritative writer/source-of-truth owner, not merely a consumer. Multiple evidenced writers stay visible and
feed the existing Multiple writers smell.

## Dependency projection

Set `perspective` to the focal service or bounded context for the run. Each edge records:

- `source` and `target` — actual caller/producer and callee/consumer;
- `direction` — `upstream` when the dependency is required by the focal perspective, `downstream` when the
  focal perspective supplies/feeds it;
- `interaction` — `synchronous` or `asynchronous` based on the evidenced transport/control flow;
- `criticality` — CRITICAL/HIGH/MEDIUM/LOW/UNKNOWN from user impact plus recovery dependency; and
- evidence/confidence.

Do not derive criticality from call frequency alone. If direction, interaction, or criticality cannot be
supported, use UNKNOWN.

## Capability-to-code projection

Each material business/domain capability maps to the repositories and concrete code locations that implement
or enforce it. Preserve evidence/confidence and ownership. A capability spanning multiple repos lists all
evidenced locations rather than choosing a single convenient owner.

## P5 reconciliation gate

Before P5 completes in FULL mode:

1. Parse all four YAML artifacts and confirm `schema_version: 1`.
2. Confirm source revisions cover every in-scope application repo or explicitly record the gap.
3. Confirm every populated machine record/edge/capability has evidence and confidence.
4. Reconcile API/event records with catalogs, ownership graph with `DATA_OWNERSHIP.md`, dependency graph with
   `DEPENDENCY_GRAPH.md`/runtime evidence, and capability traceability with PRD/bounded-context evidence.
5. Apply deterministic confidence aggregation from `domain-model-contract.yaml`; never average upward.
6. Any contradiction remains visible as Conflicted/UNKNOWN/LOW according to evidence precedence; do not
   silently choose the nicer representation.
7. Confirm the manifest PRD artifact row is `ok`, never `stale`, before claiming the baseline is current.

A missing required machine artifact or stale PRD in FULL mode makes the run PARTIAL/incomplete.

## DELTA / ADD_REPO stale-PRD gate

Compare the previous source revisions and machine artifacts against the refreshed projections. `PRD.md` is
stale when any configured `stale_when` condition in `domain-model-contract.yaml` fires, including behavior or
contract changes, authoritative data-owner changes, critical dependency semantics changes, or capability
ownership/code-location changes.

As soon as a stale condition fires, set root `manifest.yaml` `artifacts[id=prd].status: stale` **before** any
handoff or completion claim. The stale file remains on disk and its human-readable reason/evidence is recorded
in `PROGRESS.md`/handoff. Required outcome is exactly one of:

- regenerate/update the affected PRD requirements/traceability, re-run the comparison, then restore the
  manifest PRD row to `ok`; or
- leave the manifest PRD row `stale`, keep the engagement/affected phase incomplete, and block claims that
  the PRD represents current state.

Silently preserving a stale PRD as manifest `ok` is forbidden.

## prd-architect handoff

Pass `PRD.md`, its manifest freshness status, the four machine artifacts, and source revision metadata. The
consumer may propose a future state but must preserve the observed baseline and explicitly identify changes.
A `stale` PRD must **not** be claimed or used as current-state baseline evidence — hand it off only as
non-current/stale evidence. The consumer must keep Build Readiness **Not Ready** until the PRD is regenerated
to manifest `ok` or independently re-verified current against source revisions. Disclosure alone does not make
a stale PRD current. Contract:
[../../prd-architect/reference/current-state-evidence-contract.yaml](../../prd-architect/reference/current-state-evidence-contract.yaml).
