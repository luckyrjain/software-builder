# squad-map-config.yaml schema

**Normative.** Config resolution order:

1. `squad-map-config.yaml` at workspace root
2. Else `domain-config.yaml` → read `ownership:` block only (domain-comprehension integration)
3. Else ask user for required fields before Phase 0

## Schema

```yaml
# squad-map-config.yaml (optional top-level fields)
workspace_root: /path/to/repos    # default: user-provided or cwd
repos:                            # optional explicit list; else auto-discover git dirs
  - api-disbursement
  - disbursement-service

ownership:
  gitlab:
    org_prefix: <org>             # scopes group_prefixes bulk discovery — not squad indexing
    squad_path_segment: 2         # 1-based index into full namespace.full_path (split on /)
    group_prefixes:               # optional bulk list_group_projects
      - <org/domain-group>
  datadog:
    service_aliases:              # repo folder name → Datadog service name
      <repo-name>: <service-name>
    domain_service_query: "name:<keyword>*"   # optional bulk search_datadog_services
  monorepo_service_dirs:            # per-repo service subdirectories — consumed by both MCP mapping
    <repo-name>:                    # (Step 2) and CODEOWNERS fallback (Step 7)
      - src/payments
      - src/notifications
```

## Required fields

| Field | Required | Default |
|-------|----------|---------|
| `ownership.gitlab.squad_path_segment` | When GitLab ✅ | Ask user |
| `ownership.gitlab.org_prefix` | No | none — scopes `group_prefixes` only; does not affect `squad_path_segment` indexing |
| `ownership.gitlab.group_prefixes` | No | [] |
| `ownership.datadog.service_aliases` | No | {} |
| `ownership.datadog.domain_service_query` | No | none |
| `ownership.monorepo_service_dirs` | No | {} — when set, Phase 1 maps **each listed subdirectory** as a separate service row before CODEOWNERS fallback |

When `monorepo_service_dirs` lists multiple paths for one repo, emit one `SQUAD_MAP.md` row per
subdirectory (repo name suffix: for `<repo-name>: [src/payments, src/notifications]` above, rows
`<repo-name>/payments` and `<repo-name>/notifications`). GitLab squad is shared; Datadog team may differ
per alias in `service_aliases`.

When neither config file exists, collect `squad_path_segment` and optional aliases from the user before
any MCP query.

## `squad_path_segment` indexing (normative)

Split `namespace.full_path` on `/` and take segment `squad_path_segment` (1-based) from the **full**
path. `org_prefix` does **not** strip segments before indexing — it scopes `group_prefixes` for bulk
discovery only.

Example: `mpokket/disbursement/api-disbursement` with `squad_path_segment: 2` → squad **`disbursement`**.

If path has fewer segments than configured → squad **UNKNOWN**; record full namespace.

### Finding your own value (before writing a config file)

The example above uses someone else's namespace — find yours instead of guessing:

1. `git remote get-url origin` in one of your repos — e.g.
   `https://gitlab.example.com/mpokket/disbursement/api-disbursement.git`.
2. Take the path after the host and strip `.git`: `mpokket/disbursement/api-disbursement`.
3. Split on `/` and count 1-based: segment 1 = `mpokket`, segment 2 = `disbursement`, segment 3 =
   `api-disbursement`. Pick the segment that names your **squad/team**, not the org or the repo itself
   — usually segment 2 in a two-level group structure, but confirm against your own GitLab group
   nesting since this varies by org.
4. Repeat on 2–3 repos from different squads to confirm the same segment index gives a different,
   correct squad name each time.

**A wrong value doesn't fail loudly** — it produces a plausible-but-wrong squad name for every repo
(e.g. always resolving to the org name, or to the repo name). If most or all repos come back with the
**same** squad, or with an unexpectedly high **Conflicts** count against Datadog teams that should
agree, recheck `squad_path_segment` first before trusting the output.

## Example

Uses this repo's own org (mpokket) since it's a real structure to anchor the example to — replace every
value with your own org/squad/service names, this isn't a fixed convention.

```yaml
ownership:
  gitlab:
    org_prefix: mpokket
    squad_path_segment: 2
    group_prefixes:
      - mpokket/disbursement
  datadog:
    service_aliases:
      disbursement-service: neo-disbursement-service
    domain_service_query: "name:disbursement*"
```
