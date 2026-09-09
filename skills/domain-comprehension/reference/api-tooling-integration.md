# API tooling integration

Optional **Postman/curl runnable export** from domain-comprehension deliverables. Normative when
`domain-config.yaml` `api_tooling.export_mode` is `optional` or `p5`.

## Inputs (do not re-derive — cite existing deliverables)

| Field | Source |
|-------|--------|
| Endpoints, request/response schema | `API_CATALOG.md` (P0.25) |
| Auth headers per route-prefix | `{map_file}` § Per-Repo Deep Dives → Auth & Gateway (P1) |
| Base URLs per env | `DEPENDENCY_GRAPH.md` § Deployment → Base URLs (P2) |
| App version / config values | `domain-config.yaml`, per-repo config surface (P0/P1) |

## Collection structure

- One collection at `postman/postman_collection.json`, one numbered top-level folder per in-scope
  repo/service (`1 - <repo-name>`, `2 - <repo-name>`, ...).
- Each folder: Happy Path Runner sub-folder + per-domain Negative Tests sub-folder.
- Collection variables: `signatureSalt`, `appVersion`, `versionCode`, `directBaseUrl` (only for prefixes
  where P1 recorded a debug-ingress path), plus `jwt` and `userId` (populated by a sign-in request's test
  script for chaining) — never a literal secret value, only variable placeholders.
- `baseUrl` = the BFF column from `DEPENDENCY_GRAPH.md` § Deployment → Base URLs, not raw ingress, unless
  no BFF was found (`UNKNOWN` in that table) — then note it in `postman/README.md` and use direct ingress
  as a documented fallback.

## Generating the deliverable set

1. Copy `templates/postman/environment.defaults.json`, `gen_postman.py`, `postman_collection.json`,
   `README.md` (and `fetch_otp_from_redis.py` if `otp_helper` resolves to on) into `workspace_root/postman/`.
2. Fill `environment.defaults.json`'s `envs.<env>` blocks from `DEPENDENCY_GRAPH.md` § Deployment → Base
   URLs and P1 Auth & Gateway (salt env-var **names**, never values).
3. Build out `postman_collection.json`'s `item` array from `API_CATALOG.md`, one numbered folder per repo.
4. Run `python3 gen_postman.py --all --patch-collection` inside `postman/` to generate the per-env files
   and sync `appVersion`/`versionCode` into the collection from `environment.defaults.json`'s `active_env`.
5. Set manifest `api_tooling_export` → `ok` once all required files are present and step 4 ran clean.

## `ADD_REPO` interaction

`ADD_REPO`'s P5 re-run (already unconditional per its procedure) checks `api_tooling.export_mode` same as
`FULL`. When on, it **appends** a new numbered folder for the onboarded repo to the existing
`postman_collection.json` rather than regenerating the whole file — consistent with `ADD_REPO`'s
incremental philosophy. If the new repo's collection variables collide with an existing name (e.g. two
repos both need a variable called `signatureSalt` with different values), suffix the new repo's variable
with its repo name (`signatureSalt_<repo>`) rather than overwriting — note the collision in
`RISK_MAP.md` § Merge Conflicts using the same `open`/`resolved` convention `ADD_REPO` already established.

## Do not

- Do not write live secrets, tokens, or salt **values** anywhere — env var names only.
- Do not run Newman or otherwise execute requests against a live environment — generation only.
- Do not invent an auth header or base URL not backed by P1/P2 evidence — leave a commented placeholder and
  note it in `UNKNOWNS.md`.
