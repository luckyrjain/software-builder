# Memory Bank integration

Optional **per-repo Cursor Memory Bank** export from domain-comprehension deliverables. Normative when
`domain-config.yaml` `memory_bank.export_mode` is `optional` or `p5`.

## Three layers (do not conflate)

| Layer | Location | Producer | Role |
|-------|----------|----------|------|
| **Comprehension** | `workspace_root` deliverables | P0–P5 | Domain truth — evidence-backed, cross-repo |
| **Generated skeleton** | `<repo>/memory-bank/.generated/` | `/understand` graph or `make memory-bank` | Structural index — layers, package map, provenance |
| **Agent memory bank** | `<repo>/memory-bank/*.md` | P5 export (this skill) | Per-repo coding playbook for downstream agents |

`npx cursor-bank init` only creates an **empty** `memory-bank/` directory and copies `.cursor/rules`
(PLAN/ACT). Rich content comes from **agent population** ("initialize memory bank") or from **P5 export**
here — not from init alone.

**Do not** run a separate "initialize memory bank" pass when `memory_bank.export_mode: p5` — P5 export
projects the same semantic work into Memory Bank format.

## Config (`domain-config.yaml`)

```yaml
memory_bank:
  consume_existing: true       # Session 0 / P0: read existing memory-bank/ as LOW evidence
  export_mode: optional        # never | optional | p5
  init_tool: none              # none | templates-only | cursor-bank
  merge_strategy: hand_wins    # generated refreshes .generated/ + appendix only; never wholesale replace
  per_repo_export: tier_0_1_only   # tier_0_only | tier_0_1_only | all_application
```

| `export_mode` | Behavior |
|---------------|----------|
| `never` | No per-repo memory-bank writes; manifest artifact `memory_bank_export` → `n_a` |
| `optional` | P5 export when user requests or `engagement` notes it; artifact `waived` if skipped |
| `p5` | Required P5 output for each export-target repo; artifact `ok` when all targets done |

| `init_tool` | Behavior |
|-------------|----------|
| `none` (default) | Create `memory-bank/` dirs and files directly — **no** `.cursor/rules` copied into app repos |
| `templates-only` | Copy [templates/memory-bank/](../templates/memory-bank/) stubs into each target repo |
| `cursor-bank` | Run `npx cursor-bank init` per target repo **only** if team wants PLAN/ACT rules there |

## Session 0 — consume existing banks

During repo census, for each in-scope repo:

1. If `<repo>/memory-bank/*.md` exists → record in `PROGRESS.md` § Memory banks (repo, files present,
   last modified if visible).
2. If `<repo>/memory-bank/.generated/` exists → record graph export present.
3. Treat all memory-bank claims as **LOW** confidence until corroborated in P0+ ([evidence-precedence.md](evidence-precedence.md)).
4. Do **not** inflate confidence because prose looks detailed.

## P0 — corroborate

When `memory_bank.consume_existing: true`, cross-check memory-bank claims against P0 inventory
(`build.gradle`, Helm, controllers). Mismatches → `UNKNOWNS.md` or lower confidence on export slice.

## P5 — export procedure

For each repo in `manifest.repos[]` matching `per_repo_export`:

1. **Refresh skeleton** (if P0.5 graphs exist):
   - Regenerate `<repo>/memory-bank/.generated/` via agent-governance `make memory-bank SERVICE=<name>`
     when available, **or** derive layer appendix from workspace
     `.understand-anything/<repo>-knowledge-graph.json`.
   - Log graph label warnings (wrong domain names in tour text) in export footnotes or `UNKNOWNS.md`.

2. **Init** (if `init_tool` requires): `templates-only` or `cursor-bank` per table above.

3. **Project semantic content** from comprehension deliverables (merge, do not blind overwrite human
   edits in `activeContext.md` / `progress.md` unless file is still stub):

| Memory Bank file | Comprehension sources | Notes |
|------------------|----------------------|-------|
| `projectbrief.md` | `{map_file}` § Per-Repo Deep Dive, `EXEC_SUMMARY` Q1 | Add provenance header (graph SHA, `analyzedAt`) |
| `systemPatterns.md` | `API_CATALOG`, `EVENT_CATALOG`, P2 flows, P1 patterns | Append `## Architecture layers (auto-generated)` from `.generated/` |
| `techContext.md` | P0 inventory, `build.gradle`/Helm evidence | Infra + integrations tables |
| `productContext.md` | `BUSINESS_FLOWS`, `DOMAIN_GLOSSARY` | Mark UNKNOWN where product intent not in code |
| `activeContext.md` | `UNKNOWNS`, `RISK_MAP`, audit inputs | Stub OK; **do not invent** audit findings |
| `progress.md` | Link workspace `PROGRESS.md` + repo checklist | Session-oriented — minimal auto-sync |

4. **Merge rules** (`merge_strategy: hand_wins`):
   - Write semantic sections from comprehension.
   - Refresh structure only in `.generated/` and the auto-generated appendix.
   - Never replace full `systemPatterns.md` with `.generated/` alone.
   - Preserve non-stub human content in `activeContext.md` / `progress.md`.

5. **Evidence block** — every non-trivial conclusion in exported files:

```
Evidence:   <repo>/path:Line or :Symbol
Conclusion: ...
Confidence: HIGH | MEDIUM | LOW | UNKNOWN
```

6. Update `manifest.yaml` artifact `memory_bank_export`:
   - `ok` — all export-target repos have six core files with non-stub semantic content (except allowed stubs).
   - `waived` — `export_mode: optional` and user skipped.
   - `n_a` — `export_mode: never`.

## Understand vs Memory Bank (scope boundary)

| Capability | `/understand` (P0.5) | P5 Memory Bank export |
|------------|----------------------|------------------------|
| Package / layer index | Yes | Appendix only |
| API tables, dual flows, integrations | No — use P0.25 / P1 | Yes |
| Product intent | No | From `BUSINESS_FLOWS` (MEDIUM) |
| Cross-repo domain view | `domain-graph.json` | Workspace deliverables |
| Ops / audit context | No | Stub + human input |

Enhance **understand** only for graph quality (labels, tour accuracy) — not for cursor-bank-level prose.

## Worked example (autodebit-service)

Agent-populated memory bank (via cursor-bank workflow) beat graph-only `.generated/` on API tables,
dual debit flows, and integrations. Graph export won on 16 architecture layers and guided tour.
**P5 export** combines both: curated tables from comprehension + layer appendix from `.generated/`.

## DELTA mode

When repo SHA changes and P5 re-runs:

1. Regenerate `.generated/` for changed repos.
2. Re-project semantic slices from updated comprehension rows.
3. Preserve human `activeContext.md` / `progress.md` sections unless user requests full refresh.

## Allowed writes

Per-repo `memory-bank/**` is an **allowed write** when `memory_bank.export_mode` is not `never`.
Do not modify other application source.
