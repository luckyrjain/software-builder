# Domain Comprehension — `api_tooling` Export (Runnable Postman/curl)

**Date:** 2026-07-30
**Skill:** `domain-comprehension`

---

## Problem statement

The org's `Extract Service Knowledge Base` prompt (a single-service extraction workflow, superseded in
places by `domain-comprehension`) produces a `postman/` deliverable set — a runnable Postman collection,
per-env environment files, a regeneration script, and (when relevant) an OTP-fetch helper — so a human can
immediately exercise the service's API without hand-building requests. `domain-comprehension` has no
equivalent: it stops at `API_CATALOG.md` (a markdown description of endpoints), never producing anything
runnable.

Closing this gap was ruled out earlier as "against the read-only mandate" — that was wrong. The skill's
read-only rule protects **application source in the analyzed repos**; it has never restricted what gets
written under `workspace_root` (the skill already writes `EXEC_SUMMARY.md`, `manifest.yaml`,
`.understand-anything/**`, and per-repo `memory-bank/**` there). A Postman collection is just another
`workspace_root` deliverable, gated the same way Memory Bank export already is.

While scoping this, a second, real gap surfaced: nothing in `domain-comprehension` today captures
**per-environment base URLs (BFF vs. direct ingress)** or **gateway auth headers per route-prefix** —
both required to build a *runnable* collection. `P2`'s `DEPENDENCY_GRAPH.md` § Deployment captures
service→cluster/namespace placement, not base URLs. `P1`'s per-repo deep dive has no auth-model
subsection. This design adds both, evidence-gated, alongside the Postman export itself.

---

## Scope

**In:** `domain-config.yaml` `api_tooling` block; P1 Auth & Gateway subsection; P2 Deployment graph base-URL
extension; P5 `api_tooling` export (collection + 3 env files + generator config + generator script + README
+ conditional OTP script); manifest artifact; `ADD_REPO` incremental append behavior; allowed-writes update.

**Out:** actually running Newman/executing requests (the skill stays read-only on **application** systems —
generating a runnable artifact is in scope, *invoking* it against a live environment is not); OTP/Redis
credentials or secrets of any kind (env var **names** only, matching the existing DB-env-var convention);
non-HTTP protocols (gRPC/Kafka Postman equivalents are out of scope for v1).

---

## Config (`domain-config.yaml`) — mirrors `memory_bank` exactly

```yaml
api_tooling:
  export_mode: never           # never | optional | p5
  otp_helper: auto             # auto | always | never — auto = only if Redis OTP usage found in P1
  envs: [qa, uat, prod]         # which postman_environment.<env>.json files to generate
```

| `export_mode` | Behavior |
|---|---|
| `never` (default) | No `postman/` writes; manifest artifact `api_tooling_export` → `n_a` |
| `optional` | P5 export when user requests it; artifact `waived` if skipped |
| `p5` | Required P5 output; artifact `ok` when all 7 (or 6, if no OTP) files present |

Same three-value shape as `memory_bank.export_mode` — same operator muscle memory, same manifest-artifact
pattern (`ok` \| `waived` \| `n_a`).

---

## Section 1 — P1: Auth & Gateway subsection

### `workflow/phase-1.md`

Add a new required-output row (after "Smells (initial)"):

```markdown
| Auth & Gateway (when `api_tooling.export_mode` != `never`) | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence | Phase incomplete only when export_mode requires it — otherwise skip, no note needed |
```

Add an "Investigation recipes" section (new, mirrors `phase-0-25.md`'s existing style) before "Checkpoint":

```markdown
## Investigation recipes (Auth & Gateway — only when `api_tooling.export_mode` != `never`)

Per repo, per route-prefix:

- **Signature/JWT filters:** `rg -l 'SignatureVerificationFilter|JwtAuthFilter|WebSecurityConfig|@PreAuthorize' --glob '!test*'`
- **Header names:** `rg -o 'X-Signature|X-App-Version|Authorization|User-Id|Profession-Type' config/ src/ | sort -u`
- **Env bypass rules:** `rg -l 'signature.*bypass|dev.*whitelist|sit.*skip' --glob '!test*' application*.yml`
- **Salt/secret source (name only, never value):** `rg -n 'signature\.salt|SIGNATURE_SALT' application*.yml`
- **Redis OTP usage (for `api_tooling.otp_helper: auto` resolution):** `rg -l 'otp.*redis|redis.*otp|OtpService|OTP_TTL' --glob '!test*'` — record repo name + evidence path if found, `none found` if not. This is the only signal `otp_helper: auto` uses.

Record per route-prefix: required headers, JWT vs signature vs none, environment bypass rules, salt env-var
**name**, and (once per repo, not per-prefix) whether Redis OTP usage was found. `UNKNOWN` with reason when
no filter class is found for a prefix that clearly has protected routes (do not assume "no auth" from
absence of evidence).
```

---

## Section 2 — P2: Deployment graph base-URL extension

### `workflow/phase-2.md`

Extend the existing Deployment graph row (do not add a new row — this is the same artifact, more fields):

```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config; when `api_tooling.export_mode` != `never`, also per-env base URL (BFF + direct ingress) | Phase incomplete — UNKNOWN allowed with reason |
```

### `reference/required-diagrams.md` row 3 gets a one-line addendum (base-URL table sits alongside the
existing deployment diagram, not a new diagram — no new required-diagrams row).

Add to `DEPENDENCY_GRAPH.md`'s template (`templates/DEPENDENCY_GRAPH.md`) § Deployment, only populated when
the flag is on:

```markdown
### Base URLs (api_tooling)

| Env | BFF base URL | Direct ingress (debug only) | Evidence |
|-----|--------------|------------------------------|----------|
```

Sources: `application*.yml`, Jenkinsfile, K8s ingress manifests — same sources the extraction prompt used,
now evidence-cited like every other domain-comprehension table.

---

## Section 3 — P5: `api_tooling` export

### `workflow/phase-5.md`

Add a new section, sibling to "Memory Bank export (optional)":

```markdown
## API tooling export (optional)

When `domain-config.yaml` `api_tooling.export_mode` is `p5` or (`optional` and user requested export):

| Output | Location | Required fields | Note |
|--------|----------|------------------|------|
| Postman collection | `postman/postman_collection.json` | Numbered folder per in-scope repo/service, built from `API_CATALOG.md` + P1 Auth & Gateway + P2 Deployment base URLs | Required when `export_mode: p5` |
| Per-env environment files | `postman/postman_environment.<env>.json` (one per `api_tooling.envs`) | Importable, base URL from § Deployment | Required |
| Generator config | `postman/environment.defaults.json` | Not imported — `gen_postman.py` input | Required |
| Generator script | `postman/gen_postman.py` | Regenerates env files, patches collection (auth header injection) | Required |
| OTP helper | `postman/fetch_otp_from_redis.py` | Only when `api_tooling.otp_helper` resolves to on (see below) | Conditional |
| README | `postman/README.md` | Import steps, Happy Path, Newman command | Required |
| Manifest artifact | `manifest.yaml` `api_tooling_export` | `ok` \| `waived` \| `n_a` | Update every P5 |

**`otp_helper` resolution:** `always` → always write it; `never` → never; `auto` (default) → write it only
if any in-scope repo's P1 Auth & Gateway subsection recorded Redis OTP-pattern usage (Section 1's new
grep recipe, added specifically to feed this decision) — cite the evidence in the script's header comment.

**Procedure:** [api-tooling-integration.md](../reference/api-tooling-integration.md).

**Evidence rule:** every request in the collection traces to an `API_CATALOG.md` row. A route with no
evidenced auth model (P1 recorded `UNKNOWN`) gets a commented-out placeholder header in the collection —
never an invented value.

When `export_mode: never`, set manifest `api_tooling_export` → `n_a`.
```

---

## Section 4 — `reference/api-tooling-integration.md` (new file, mirrors `memory-bank-integration.md`)

```markdown
# API tooling integration

Optional **Postman/curl runnable export** from domain-comprehension deliverables. Normative when
`domain-config.yaml` `api_tooling.export_mode` is `optional` or `p5`.

## Inputs (do not re-derive — cite existing deliverables)

| Field | Source |
|-------|--------|
| Endpoints, request/response schema | `API_CATALOG.md` (P0.25) |
| Auth headers per route-prefix | `{map_file}` § Per-Repo Deep Dives → Auth & Gateway (P1, this design's Section 1) |
| Base URLs per env | `DEPENDENCY_GRAPH.md` § Deployment → Base URLs (P2, this design's Section 2) |
| App version / config values | `domain-config.yaml`, per-repo config surface (P0/P1) |

## Collection structure

- One collection at `postman/postman_collection.json`, one numbered top-level folder per in-scope
  repo/service (`1 - <repo-name>`, `2 - <repo-name>`, ...).
- Each folder: Happy Path Runner sub-folder + per-domain Negative Tests sub-folder (matches the extraction
  prompt's convention).
- Collection variables: `signatureSalt`, `appVersion`, `versionCode`, `directBaseUrl` (only for prefixes
  where P1 recorded a debug-ingress path) — never a literal secret value, only variable placeholders.
- `baseUrl` = the BFF column from `DEPENDENCY_GRAPH.md` § Deployment → Base URLs, not raw ingress, unless
  no BFF was found (`UNKNOWN` in that table) — then note it in `postman/README.md` and use direct ingress
  as a documented fallback.

## `ADD_REPO` interaction

`ADD_REPO`'s P5 re-run (already unconditional per its procedure) checks `api_tooling.export_mode` same as
`FULL`. When on, it **appends** a new numbered folder for the onboarded repo to the existing
`postman_collection.json` rather than regenerating the whole file — consistent with `ADD_REPO`'s
incremental philosophy. If the new repo's collection variables collide with an existing name (e.g. two
repos both need a variable called `signatureSalt` with different values), suffix the new repo's variable
with its repo name (`signatureSalt_<repo>`) rather than overwriting — note the collision in
`RISK_MAP.md` § Merge Conflicts using the same `open`/`resolved` convention `ADD_REPO` already established,
since it's the same class of problem (two repos, one shared artifact, competing claims).

## Do not

- Do not write live secrets, tokens, or salt **values** anywhere — env var names only (same rule as the
  existing Database env vars section of `SOURCES`-equivalent deliverables).
- Do not run Newman or otherwise execute requests against a live environment — generation only.
- Do not invent an auth header or base URL not backed by P1/P2 evidence — leave a commented placeholder and
  note it in `UNKNOWNS.md`.
```

---

## Section 5 — Manifest, SKILL.md, deliverable index

### `reference/manifest-schema.md`

Add, alongside the existing `memory_bank_export` optional-artifact note:

```markdown
Optional artifacts: `api_tooling_export` — `postman/` deliverable set when `api_tooling.export_mode` is not
`never` ([api-tooling-integration.md](api-tooling-integration.md)). Manifest `path` is `postman/`
(convention); status `ok` when all required files (collection, env files, generator config/script, README,
OTP script if applicable) are present.
```

### `SKILL.md`

Extend "Allowed writes only" (currently lines 103-107):

```markdown
- Markdown deliverables + `domain-config.yaml` + **`manifest.yaml`** (every phase) + `.understand-anything/**`
- Per-repo `memory-bank/**` when `memory_bank.export_mode` is not `never`
  ([memory-bank-integration.md](reference/memory-bank-integration.md))
- `postman/**` when `api_tooling.export_mode` is not `never`
  ([api-tooling-integration.md](reference/api-tooling-integration.md))
```

Add to "Key tools explained" (sibling to the existing Cursor Memory Bank bullet):

```markdown
- **API tooling export** (optional P5) — `postman/` runnable Postman collection + curl-equivalent generator
  from comprehension deliverables (`API_CATALOG.md`, P1 Auth & Gateway, P2 Deployment base URLs). See
  [api-tooling-integration.md](reference/api-tooling-integration.md).
```

Add to "Minimum viable deliverables by delivery_mode" table: no new row needed (this is orthogonal to
`delivery_mode`, same as Memory Bank — it's a per-mode optional export, not a mode itself). Add one line
under the table's existing prose instead:

```markdown
`api_tooling.export_mode` (like `memory_bank.export_mode`) is independent of `delivery_mode` — it applies
whenever P5 runs, including under `ADD_REPO`.
```

### `reference/deliverable-templates.md`

Add to the "Split deliverables" table:

```markdown
| `postman/*` | Optional P5 — Postman/curl export ([api-tooling-integration.md](api-tooling-integration.md)) |
```

### `templates/domain-config.yaml`

Add, after the existing `memory_bank:` block:

```yaml
api_tooling:
  export_mode: never
  otp_helper: auto
  envs: [qa, uat, prod]
```

### `reference/domain-config-schema.md`

Add, after the existing `memory_bank:` schema block (line 90-96):

```markdown
api_tooling:                      # optional — per-engagement Postman/curl export (P5 export)
  export_mode: never              # never | optional | p5
  otp_helper: auto                # auto | always | never
  envs: [qa, uat, prod]           # which postman_environment.<env>.json files to generate
```

---

## Open items for implementation plan

- Exact `gen_postman.py` generator logic (what it actually regenerates, patch mechanics for JWT/signature
  injection) — needs a concrete script, not just a description; write it in the plan with real code, same
  standard as the `ADD_REPO` validator work.
- Whether `validate_manifest_yaml.py` needs a content-check for `postman/` (mirroring the merge-conflicts
  gate) — e.g. verify `postman_collection.json` is valid JSON and every request has a `baseUrl` reference
  when `api_tooling_export` is claimed `ok`. Recommend yes, same drift-prevention rationale as the
  merge-conflicts gate.
- Fixture data for `tests/fixtures/check-content/` if the above validator check is added.
