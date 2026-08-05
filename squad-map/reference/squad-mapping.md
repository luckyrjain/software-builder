# Squad mapping — GitLab groups + Datadog teams

**Normative.** Builds `SQUAD_MAP.md` at workspace root.

## Two ownership lenses

| Lens | Source | Meaning |
|------|--------|---------|
| **Org squad** | GitLab `namespace.full_path` | Where the repo lives in GitLab hierarchy |
| **Runtime squad** | Datadog service `team` tag | Who owns the deployed service in observability |

Both are recorded. They often align; mismatches are flagged, not silently resolved.

## GitLab mapping

### Resolve project path

1. `git -C <repo_dir> remote get-url origin` → parse `host:group/subgroup/project.git` or URL path
2. If no remote or ambiguous: `search_repositories(search=<repo-folder-name>)`
3. `get_project(project_id=<path>)` → read `path_with_namespace` or `namespace.full_path`

### Extract squad from group prefix

Config ([config-schema.md](config-schema.md)):

```yaml
ownership:
  gitlab:
    org_prefix: acme              # for group_prefixes only — not squad indexing
    squad_path_segment: 2            # see config-schema.md § squad_path_segment indexing
    group_prefixes:                  # optional bulk discovery
      - acme/disbursement
```

**Indexing rule:** [config-schema.md § squad_path_segment indexing](config-schema.md#squadpathsegment-indexing-normative).

If path has fewer segments than configured → squad **UNKNOWN**; record full namespace.

### Bulk discovery

When `group_prefixes` set:

```
list_group_projects(group_id: "acme/disbursement", include_subgroups: true)
```

Maps all GitLab projects under prefix → seed cross-check against local census (repos without local checkout still listed as GitLab-only if relevant).

## Datadog mapping

Config:

```yaml
ownership:
  datadog:
    service_aliases:
      disbursement-service: neo-disbursement-service
    domain_service_query: "name:disbursement*"   # optional bulk pass
```

### Per-repo query

```
search_datadog_services(
  query: "name:<service_name>*",
  detailed_output: true,
  telemetry: { intent: "Map repo <name> to Datadog team for squad mapping" }
)
```

- Prefer **exact** `name` match; then **fuzzy** match — longest prefix match (e.g. repo `payments-api`
  matching Datadog service `payments-api-worker` via prefix, no exact `payments-api` service present)
- Multiple services → pick highest traffic / exact name; list alternates in Notes column
- No match → Datadog team **UNKNOWN** (not inferred from repo name)

### Domain-wide query (optional)

After per-repo pass, one bulk query from `domain_service_query` or
`name:<include_keywords[0]>*` to catch services without local repos.

## Reconciliation

| Scenario | Confidence | Likely owner for UNKNOWNS |
|----------|------------|---------------------------|
| Both present, equal (case-insensitive) | **HIGH** | that squad/team |
| Both present, differ | **MEDIUM** + `⚠️ conflict` | Datadog team (runtime); note GitLab in conflict table |
| GitLab only | **MEDIUM** | GitLab squad |
| Datadog only | **MEDIUM** | Datadog team |
| Fuzzy service alias match | **LOW** | best match + gap note |
| Neither | **UNKNOWN** | leave blank |

**Never HIGH** when GitLab and Datadog disagree — cap at MEDIUM.

## SQUAD_MAP.md tables

### Main table

| Repo | GitLab namespace | GitLab squad | Datadog service | Datadog team | Confidence | Evidence |
|------|------------------|--------------|-----------------|--------------|------------|----------|

Evidence: `GitLab get_project path` and/or `Datadog search_datadog_services query`.

### Conflicts

| Repo | GitLab squad | Datadog team | Notes |
|------|--------------|--------------|-------|

## Downstream integration

When invoked from **domain-comprehension**, copy squad columns into `{map_file}` § Inventory repo table:

`| Repo | … | GitLab squad | Datadog team | Owner confidence |`

## Degraded mode

| Missing | Fallback |
|---------|----------|
| GitLab MCP | Datadog team only; CODEOWNERS fallback in Phase 1 |
| Datadog MCP | GitLab squad only |
| Both | `SQUAD_MAP.md` stub with UNKNOWN rows; CODEOWNERS fallback (confidence LOW) |
