# Domain config schema

**Normative.** Written to `workspace_root/domain-config.yaml` at Session 0.

```yaml
domain:
  name: <slug>                    # e.g. disbursement → DISBURSEMENT_MAP.md
  display_name: <Human Name>
  description: <one line>

workspace:
  root: <absolute path>
  layout: sibling-repos | monorepo | single-repo

scope:
  include_keywords: [<grep/repo name terms>]
  exclude_patterns: [<glob or substring>]
  seed_repos: [<optional hints — agent still verifies>]
  default_excluded_classifications:   # optional — see repo-classification.md
    - documentation
    - archived
    - tooling
  conditional_repos:              # include only if grep finds domain refs
    - <repo-name>
  artifact_root: <relative path>  # optional — see run-scoped-artifacts.md. Set for parallel runs
                                   # or large workspaces so this run's deliverables don't clobber
                                   # another run's. Default when unset:
                                   # .domain-comprehension/{run_id}/ (run_id = ISO-8601 UTC
                                   # timestamp at Session 0 start, or a caller-supplied slug).
                                   # manifest.yaml always stays directly at workspace_root — record
                                   # the resolved value as engagement.artifact_root there.

context:
  regulatory_notes: <optional free text>
  product_lines:                  # architecture signals to investigate
    - name: <line>
      hints: [<repo names, route prefixes, package patterns>]

five_questions:
  - id: Q1
    question: <critical question for this domain>
    search_terms: [<grep seeds>]
  # Q2–Q5 required

critical_path_tiers:
  tier_0:
    label: <e.g. Side-effect executor>
    definition: <what belongs here>
    provisional: [<repo names>]
  tier_1:
    label: <e.g. Orchestration>
    definition: ...
    provisional: []
  tier_2:
    label: <e.g. Recon / ops>
    definition: ...
    provisional: []
  tier_3:
    label: <e.g. BFF / gates>
    definition: ...
    provisional: []
  flow_critical_gates:            # Tier 3 repos that block core flow — trace in P2
    - <repo-name>

deliverables:
  map_file: DOMAIN_MAP.md         # or {NAME}_MAP.md when name set
  core_section: Core Domain Deep Dive   # P3 section title

runbook_procedures:               # optional override of P4 defaults
  - trace_end_to_end
  - replay_retry
  - reconcile_mismatch
  - clear_stuck
  - investigate_no_effect
  - emergency_stop

ownership:                        # Session 0b — squad mapping (optional)
  gitlab:
    org_prefix: <org>             # strip leading path segment
    squad_path_segment: 2         # 1-based index → squad name from namespace path
    group_prefixes:               # optional bulk list_group_projects
      - <org/domain-group>
  datadog:
    service_aliases:              # repo folder name → Datadog service name
      <repo-name>: <service-name>
    domain_service_query: "name:<keyword>*"   # optional bulk search_datadog_services

architecture_validation:          # P2b — Datadog runtime architecture (optional)
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []              # default: Tier 0/1 Datadog names from SQUAD_MAP
  critical_paths:
    - name: <path-label>
      services: [service-a, service-b, service-c]

memory_bank:                      # optional — per-repo Cursor Memory Bank (P5 export)
  consume_existing: true          # Session 0 / P0: existing memory-bank/ as LOW evidence
  export_mode: optional           # never | optional | p5
  init_tool: none                 # none | templates-only | cursor-bank
  merge_strategy: hand_wins       # .generated/ refreshes appendix only
  per_repo_export: tier_0_1_only  # tier_0_only | tier_0_1_only | all_application

api_tooling:                      # optional — per-engagement Postman/curl export (P5 export)
  export_mode: never              # never | optional | p5
  otp_helper: auto                # auto | always | never
  envs: [qa, uat, prod]           # which postman_environment.<env>.json files to generate
```

See [memory-bank-integration.md](memory-bank-integration.md) and
[api-tooling-integration.md](api-tooling-integration.md).

## Map file naming

| `domain.name` | `deliverables.map_file` |
|---------------|-------------------------|
| `disbursement` | `DISBURSEMENT_MAP.md` (recommended) |
| `auth` | `AUTH_MAP.md` or `DOMAIN_MAP.md` |
| unset | `DOMAIN_MAP.md` |

## Default five questions (generic)

Use when user does not supply questions; confirm in Session 0:

| ID | Question |
|----|----------|
| Q1 | What component performs the **core side effect** of this domain? |
| Q2 | What prevents **duplicate processing** (idempotency / dedup)? |
| Q3 | What is the **source of truth** for domain state? |
| Q4 | How is **reconciliation or consistency** performed across systems? |
| Q5 | What happens when the **primary operation fails**? |

## Domain packs

Pre-fill config from [domain-packs/](domain-packs/). User overrides win.
