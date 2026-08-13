# Domain config schema

**Normative.** Written to `docs/domain-comprehension/<domain-slug>/domain-config.yaml` at Session 0.
The directory is created when absent. The default `scope.artifact_root` is
`docs/domain-comprehension/<domain.name>`; callers may override it with another relative path.

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
  default_excluded_classifications:
    - documentation
    - archived
    - tooling
  conditional_repos:
    - <repo-name>
  artifact_root: docs/domain-comprehension/<domain-slug>
                                   # relative to workspace root; create when absent.
                                   # Default is docs/domain-comprehension/<domain.name>.
                                   # Parallel runs may append a run_id subdirectory.
                                   # manifest.yaml stays at workspace root and records
                                   # engagement.artifact_root.

context:
  regulatory_notes: <optional free text>
  product_lines:
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
  flow_critical_gates:
    - <repo-name>

deliverables:
  map_file: DOMAIN_MAP.md
  core_section: Core Domain Deep Dive

runbook_procedures:
  - trace_end_to_end
  - replay_retry
  - reconcile_mismatch
  - clear_stuck
  - investigate_no_effect
  - emergency_stop

ownership:
  gitlab:
    org_prefix: <org>
    squad_path_segment: 2
    group_prefixes:
      - <org/domain-group>
  datadog:
    service_aliases:
      <repo-name>: <service-name>
    domain_service_query: "name:<keyword>*"

architecture_validation:
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []
  critical_paths:
    - name: <path-label>
      services: [service-a, service-b, service-c]

memory_bank:
  consume_existing: true
  export_mode: optional
  init_tool: none
  merge_strategy: hand_wins
  per_repo_export: tier_0_1_only

api_tooling:
  export_mode: never
  otp_helper: auto
  envs: [qa, uat, prod]
```

See [run-scoped-artifacts.md](run-scoped-artifacts.md),
[memory-bank-integration.md](memory-bank-integration.md), and
[api-tooling-integration.md](api-tooling-integration.md).

## Map file naming

| `domain.name` | `deliverables.map_file` |
|---------------|-------------------------|
| `disbursement` | `DISBURSEMENT_MAP.md` (recommended) |
| `auth` | `AUTH_MAP.md` or `DOMAIN_MAP.md` |
| unset | `DOMAIN_MAP.md` |

## Default five questions

| ID | Question |
|----|----------|
| Q1 | What component performs the **core side effect** of this domain? |
| Q2 | What prevents **duplicate processing** (idempotency / dedup)? |
| Q3 | What is the **source of truth** for domain state? |
| Q4 | How is **reconciliation or consistency** performed across systems? |
| Q5 | What happens when the **primary operation fails**? |

## Domain packs

Pre-fill config from [domain-packs/](domain-packs/). User overrides win.
