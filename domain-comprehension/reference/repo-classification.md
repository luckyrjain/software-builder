# Repository classification (normative)

**Required in:** Session 0, P0 inventory, `manifest.yaml` `repos[]`, `EXEC_SUMMARY.md` repo map.

Every in-scope repository **must** have exactly one classification. **No other values allowed.**

| Classification | Definition | Graph role |
|----------------|------------|------------|
| **application** | Deployable service with business logic | Bounded-context owner candidate; service/runtime graphs |
| **library** | Shared code consumed by services | Dependency node only — not a context owner |
| **sdk** | Client SDK for external or internal APIs | Dependency node; catalog as consumer/producer helper |
| **shared_model** | DTOs, enums, shared types without runtime | Dependency node; data-ownership reference |
| **infrastructure** | Platform, mesh, gateways, shared infra | Deployment graph; context boundary |
| **schema** | Migrations, protos, OpenAPI-only repos | Contract source; event/API catalogs |
| **configuration** | Helm, env templates, feature flags | Deployment graph; config precedence |
| **tooling** | CLIs, generators, one-off scripts | Exclude from service graphs unless on critical path |
| **documentation** | Docs-only repos | Exclude from graphs; cite in KNOWN_OMISSIONS if referenced |
| **experimental** | Prototype, spike, non-prod | Low tier default; flag in RISK_MAP |
| **archived** | Deprecated, no active deploy | Inventory only; no runtime validation |

## Evidence

Record classification evidence: `Evidence: <repo>/pom.xml|package.json|Dockerfile|README:line`.

Re-classify in P0 if Session 0 was provisional.

## Service graph filter (default)

Include in **service call** and **runtime** graphs:

- `application`, `infrastructure`, `schema` (as contract nodes)

Exclude unless referenced on critical path:

- `library`, `sdk`, `shared_model`, `tooling`, `documentation`, `configuration`, `experimental`, `archived`

Override in `domain-config.yaml`:

```yaml
scope:
  default_excluded_classifications:
    - documentation
    - archived
    - tooling
```

## Convergence

Sort repos **ascending by name** in all tables. Use this enum verbatim — no synonyms (`service` → `application`).
