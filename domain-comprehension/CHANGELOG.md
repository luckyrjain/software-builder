# domain-comprehension changelog

For earlier history, see the `## domain-comprehension` sections in the repository root `CHANGELOG.md`.

## 1.1.0 — bounded discovery budgets, DELTA/ADD_REPO stale-PRD gate, machine domain-model handoff (2026-08-17)

- Discovery (repository/search-query/deep-file-read) is now bounded per delivery-mode profile
  (`QUICK`/`FULL`/`DELTA`/`ADD_REPO`/`CUSTOM`), with defaults and the stop-on-exhaustion contract in
  `reference/domain-model-contract.yaml`.
- DELTA/ADD_REPO can mark `artifacts[id=prd].status: stale` when source revisions, contracts, data
  ownership, dependency semantics, or capability ownership drift from the retained baseline, blocking
  `--strict FIRST_PASS_COMPLETE` until the PRD is regenerated or the row explicitly stays `stale`.
- Added four P5 machine domain-model YAML deliverables (`API_EVENT_SCHEMA.yaml`,
  `DATA_OWNERSHIP_GRAPH.yaml`, `DEPENDENCY_GRAPH.yaml`, `CAPABILITY_TRACEABILITY.yaml`) for
  deterministic current-state handoff to `prd-architect`.

See the root `CHANGELOG.md`'s `## domain-comprehension` entry dated 2026-08-17 for full detail.
