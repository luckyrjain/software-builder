---
workflow_version: 1.9
phase: 0
produces:
  - inventory
  - config_surface_table
  - repo_relationship_table
consumes:
  - domain_config_yaml
  - exec_summary_draft
  - squad_map
---

# Comprehension Phase P0 — Inventory

For **each in-scope repo/module**, document in `{map_file}` § Inventory:

- Purpose, languages, frameworks, build/run tooling, classification
- **Squad:** GitLab squad, Datadog team, owner confidence — from `SQUAD_MAP.md` (Session 0b)
- Top-level structure (2–3 levels)
- **Entry points:** HTTP/gRPC servers, consumers, scheduled jobs, CLIs, lambdas — with file paths
- **External dependencies:** DBs, caches, queues, third-party APIs — grep for datasource-specific env
  vars explicitly: `rg -o --no-filename 'spring\.datasource\.\w+|DATABASE_URL|DB_HOST|DB_NAME|jdbc:\w+'
  -g 'application*.y*ml' -g '.env*' <repo>` (names only, never values, per the Config surface table's
  existing rule)
- Submodules / shared library references

## Repo inventory table (required)

| Repo | Tier | Classification | GitLab squad | Datadog team | Owner confidence | Purpose |
|------|------|----------------|--------------|--------------|------------------|---------|

Populate squad columns from `SQUAD_MAP.md`. If Session 0b skipped, use UNKNOWN.

## Config surface table (required)

| Key / Env var | Repo | Purpose | Prod-only? | Evidence |
|---------------|------|---------|------------|----------|

List names only — **never secret values**. See the External dependencies grep hint above for the
datasource-specific pattern.

## Repo relationship table (required)

| From repo | Relationship | To repo / external | Evidence |
|-----------|--------------|-------------------|----------|

Evidence types: HTTP client, shared table, queue, shared package import.

## Existing Memory Banks (optional)

When `memory_bank.consume_existing: true` and a repo has `memory-bank/*.md`:

1. Cross-check claims against P0 inventory (build files, Helm, entry points).
2. Record corroborated vs contradicted items in deep-dive notes or `UNKNOWNS.md`.
3. Do **not** promote memory-bank-only claims to HIGH without code evidence.

See [memory-bank-integration.md](../reference/memory-bank-integration.md).

## Sub-agents

Batch up to **4 parallel** `explore` agents per repo batch.
Coordinator starts P0.25 contract grep on Tier 0/1 repos while inventory batches run.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Repository census | `{map_file}` § Inventory | Repo, tier, classification, evidence per repo | Phase incomplete |
| Technology stack | `{map_file}` § Inventory | Per repo: languages, frameworks, build tooling | Phase incomplete |
| Bounded contexts (initial) | `BOUNDED_CONTEXTS.md` | Context name, repos, confidence | Phase incomplete |
| Config surface table | `{map_file}` § Inventory | Key/env var, repo, purpose, prod-only flag | Phase incomplete |
| Repo relationships table | `{map_file}` § Inventory | From repo, relationship type, to repo, evidence | Phase incomplete |
| `manifest.repos[]` | `manifest.yaml` | name, branch, sha, tier, classification, inventory: complete | Phase incomplete |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · outputs: [phase-outputs.md § P0](../reference/phase-outputs.md#p0-inventory)
