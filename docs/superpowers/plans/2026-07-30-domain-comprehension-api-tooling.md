# Domain Comprehension `api_tooling` Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional `api_tooling` P5 export to the `domain-comprehension` skill — a runnable Postman collection + curl-equivalent tooling generated from comprehension deliverables, gated the same way the existing Memory Bank export is.

**Architecture:** Documentation change to the skill's config schema, P1/P2/P5 workflow files, and a new `reference/api-tooling-integration.md` procedure doc (mirrors `memory-bank-integration.md`) — plus real, generic, tested code shipped as copyable templates (`templates/postman/gen_postman.py`, `fetch_otp_from_redis.py`) and a small content-validation gate in the existing `scripts/validate_manifest_yaml.py`.

**Tech Stack:** Markdown (skill instructions), JSON (Postman collection/environment shape), Python 3 stdlib only for `gen_postman.py` and the validator addition, Python 3 + lazily-imported `redis` for `fetch_otp_from_redis.py`, pytest for all new tests.

## Global Constraints

- Skill source of truth is `/Users/luckyjain/Projects/ai-skills/domain-comprehension/` inside this worktree (`/Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/`) — not `~/.claude/skills/domain-comprehension/`.
- No secrets, tokens, or credential **values** anywhere — env var names / `${VAR}` placeholders only (matches the project's own MCP-config convention already in use).
- `gen_postman.py` and the validator addition are stdlib-only — no new third-party dependency. `fetch_otp_from_redis.py` imports `redis` lazily (inside the function that needs it, not at module top level) so importing the module — and therefore testing it — never requires the `redis` package to be installed (confirmed not installed in this environment).
- Every markdown edit must keep `scripts/lint-dangling-md-links.sh` clean (run from repo root).
- `templates/` files are **not validated by their own JSON/Python syntax at Session-0-copy time** by any existing tooling — so this plan's own tests are the only correctness check; each JSON template must be confirmed valid JSON and each Python template must be confirmed syntactically valid and importable as part of its task.
- `workflow_version` bumps: `workflow/phase-1.md` `1.2` → `1.3`, `workflow/phase-2.md` `1.2` → `1.3`, `workflow/phase-5.md` `1.4` → `1.5`.

---

### Task 1: Config + manifest schema plumbing

**Files:**
- Modify: `domain-comprehension/templates/domain-config.yaml`
- Modify: `domain-comprehension/reference/domain-config-schema.md`
- Modify: `domain-comprehension/templates/manifest.yaml`
- Modify: `domain-comprehension/reference/manifest-schema.md`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: the `api_tooling` config block name/shape (`export_mode: never|optional|p5`, `otp_helper: auto|always|never`, `envs: [...]`) and the `api_tooling_export` manifest artifact id — every later task references these exact names.

- [ ] **Step 1: `templates/domain-config.yaml` — add the `api_tooling` block**

Find the end of the file:
```yaml
memory_bank:
  consume_existing: true
  export_mode: optional  # never | optional | p5
  init_tool: none        # none | templates-only | cursor-bank
  merge_strategy: hand_wins
  per_repo_export: tier_0_1_only
```

Append immediately after it:
```yaml

api_tooling:
  export_mode: never     # never | optional | p5
  otp_helper: auto        # auto | always | never
  envs: [qa, uat, prod]
```

- [ ] **Step 2: `reference/domain-config-schema.md` — document the block**

Find (the existing `memory_bank:` schema block, ends with the fenced code block's closing backticks
followed by a `See [memory-bank-integration.md]...` line and a `## Map file naming` heading):
```markdown
memory_bank:                      # optional — per-repo Cursor Memory Bank (P5 export)
  consume_existing: true          # Session 0 / P0: existing memory-bank/ as LOW evidence
  export_mode: optional           # never | optional | p5
  init_tool: none                 # none | templates-only | cursor-bank
  merge_strategy: hand_wins       # .generated/ refreshes appendix only
  per_repo_export: tier_0_1_only  # tier_0_only | tier_0_1_only | all_application
```

Replace with (adds the new block inside the same fenced code block, before the closing fence):
```markdown
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

Then, immediately after the fenced code block's closing ` ``` `, find:
```markdown
See [memory-bank-integration.md](memory-bank-integration.md).
```
Replace with:
```markdown
See [memory-bank-integration.md](memory-bank-integration.md) and
[api-tooling-integration.md](api-tooling-integration.md).
```

(The link target `api-tooling-integration.md` is created in Task 4 — this file will dangling-link-check
clean only after Task 4 lands; if running tasks in strict sequence per this plan, Task 4 comes after this,
so run the repo-wide link check in Task 10, not per-task, for this specific file.)

- [ ] **Step 3: `templates/manifest.yaml` — add the `api_tooling_export` artifact**

Find:
```yaml
  - id: memory_bank_export
    path: memory-bank/
    phase: p5
    required: false
    status: n_a
```

Replace with:
```yaml
  - id: memory_bank_export
    path: memory-bank/
    phase: p5
    required: false
    status: n_a
  - id: api_tooling_export
    path: postman/
    phase: p5
    required: false
    status: n_a
```

- [ ] **Step 4: `reference/manifest-schema.md` — document the artifact**

Find:
```markdown
Optional artifacts: `memory_bank_export` — per Tier 0/1 repo at `<repo>/memory-bank/` when
`memory_bank.export_mode` is not `never` ([memory-bank-integration.md](memory-bank-integration.md)).
Manifest `path` is `memory-bank/` (convention); status `ok` when all export-target repos are populated.
```

Replace with:
```markdown
Optional artifacts: `memory_bank_export` — per Tier 0/1 repo at `<repo>/memory-bank/` when
`memory_bank.export_mode` is not `never` ([memory-bank-integration.md](memory-bank-integration.md)).
Manifest `path` is `memory-bank/` (convention); status `ok` when all export-target repos are populated.

Optional artifacts: `api_tooling_export` — `postman/` deliverable set when `api_tooling.export_mode` is not
`never` ([api-tooling-integration.md](api-tooling-integration.md)). Manifest `path` is `postman/`
(convention); status `ok` when all required files (collection, env files, generator config/script, README,
OTP script if applicable) are present and `postman/postman_collection.json` is valid JSON.
```

- [ ] **Step 5: Verify**

```bash
cd domain-comprehension
python3 -c "import yaml; yaml.safe_load(open('templates/domain-config.yaml'))" && echo "domain-config.yaml valid YAML"
python3 -c "import yaml; yaml.safe_load(open('templates/manifest.yaml'))" && echo "manifest.yaml valid YAML"
python3 -m pytest tests/test_validate_manifest.py -k test_minimal_template_validates -v
```
Expected: both YAML files parse; `test_minimal_template_validates` still passes (the new `api_tooling_export`
artifact has `status: n_a`, which is a valid `ARTIFACT_STATUS` value, and `phase: p5`, a valid `PHASE_KEYS`
value — no validator change needed for this to pass).

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/templates/domain-config.yaml domain-comprehension/reference/domain-config-schema.md domain-comprehension/templates/manifest.yaml domain-comprehension/reference/manifest-schema.md
git commit -m "feat(domain-comprehension): add api_tooling config block and manifest artifact"
```

---

### Task 2: P1 — Auth & Gateway subsection

**Files:**
- Modify: `domain-comprehension/workflow/phase-1.md`

**Interfaces:**
- Consumes: nothing new
- Produces: the per-repo "Auth & Gateway" subsection name and its Redis-OTP-evidence convention — Task 4's `otp_helper: auto` resolution and Task 6/7's generator both reference this subsection by name.

- [ ] **Step 1: Bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.2
```
to:
```
workflow_version: 1.3
```

- [ ] **Step 2: Add the required-output row**

Find:
```markdown
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence | Phase incomplete — empty allowed with note |
```

Replace with:
```markdown
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence | Phase incomplete — empty allowed with note |
| Auth & Gateway (when `api_tooling.export_mode` != `never`) | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence | Phase incomplete only when export_mode requires it — otherwise skip, no note needed |
```

- [ ] **Step 3: Add the investigation recipes section**

Find:
```markdown
## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
```

Replace with:
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

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md)
```

- [ ] **Step 4: Verify**

```bash
grep -n "Auth & Gateway\|otp_helper\|Redis OTP" domain-comprehension/workflow/phase-1.md
```
Expected: at least 4 matches (required-output row, section heading, otp_helper mention, Redis OTP recipe).

- [ ] **Step 5: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-1.md
```
Expected: no output, exit 0 (no new links introduced in this file).

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/workflow/phase-1.md
git commit -m "feat(domain-comprehension): add P1 Auth & Gateway investigation recipes"
```

---

### Task 3: P2 — Deployment graph base-URL extension

**Files:**
- Modify: `domain-comprehension/workflow/phase-2.md`
- Modify: `domain-comprehension/templates/DEPENDENCY_GRAPH.md`

**Interfaces:**
- Consumes: nothing new
- Produces: the `DEPENDENCY_GRAPH.md` § Deployment → "Base URLs (api_tooling)" table name/shape — Task 4's export procedure and Task 7's `environment.defaults.json` shape are both sourced from this table's `Env | BFF base URL | Direct ingress` columns.

- [ ] **Step 1: Bump workflow_version**

Edit `domain-comprehension/workflow/phase-2.md` line 2 from:
```
workflow_version: 1.2
```
to:
```
workflow_version: 1.3
```

- [ ] **Step 2: Extend the Deployment graph required-output row**

Find:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config | Phase incomplete — UNKNOWN allowed with reason |
```

Replace with:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config; when `api_tooling.export_mode` != `never`, also per-env base URL (BFF + direct ingress) | Phase incomplete — UNKNOWN allowed with reason |
```

- [ ] **Step 3: `templates/DEPENDENCY_GRAPH.md` — add the Base URLs subsection**

Find:
```markdown
## Deployment graph

Service → runtime placement (K8s, namespace, ingress). Produced P2.

```mermaid
graph LR
```

**View:** deployment · **Confidence:**
```

Replace with:
```markdown
## Deployment graph

Service → runtime placement (K8s, namespace, ingress). Produced P2.

```mermaid
graph LR
```

**View:** deployment · **Confidence:**

### Base URLs (api_tooling)

Populated only when `api_tooling.export_mode` != `never`. Sources: `application*.yml`, Jenkinsfile, K8s
ingress manifests.

| Env | BFF base URL | Direct ingress (debug only) | Evidence |
|-----|--------------|------------------------------|----------|
```

- [ ] **Step 4: Verify**

```bash
grep -n "Base URLs (api_tooling)\|BFF base URL" domain-comprehension/templates/DEPENDENCY_GRAPH.md
grep -n "api_tooling" domain-comprehension/workflow/phase-2.md
```
Expected: both files show matches.

- [ ] **Step 5: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-2.md domain-comprehension/templates/DEPENDENCY_GRAPH.md
```
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/workflow/phase-2.md domain-comprehension/templates/DEPENDENCY_GRAPH.md
git commit -m "feat(domain-comprehension): add per-env base URL capture to P2 Deployment graph"
```

---

### Task 4: P5 export section + new reference doc + deliverable index row

**Files:**
- Modify: `domain-comprehension/workflow/phase-5.md`
- Create: `domain-comprehension/reference/api-tooling-integration.md`
- Modify: `domain-comprehension/reference/deliverable-templates.md`

**Interfaces:**
- Consumes: `api_tooling.export_mode` / `otp_helper` / `envs` config names from Task 1; the P1 Auth & Gateway subsection from Task 2; the `DEPENDENCY_GRAPH.md` § Deployment → Base URLs table from Task 3.
- Produces: the `postman/` deliverable file list (`postman_collection.json`, `postman_environment.<env>.json`, `environment.defaults.json`, `gen_postman.py`, `fetch_otp_from_redis.py`, `README.md`) — Task 5 (SKILL.md) and Task 6/7/8 (actual template files) both reference this exact file list.

- [ ] **Step 1: Bump workflow_version**

Edit `domain-comprehension/workflow/phase-5.md` line 2 from:
```
workflow_version: 1.4
```
to:
```
workflow_version: 1.5
```

- [ ] **Step 2: Add the API tooling export section**

Find:
```markdown
When `export_mode: never`, set manifest `memory_bank_export` → `n_a`.

## Definition of Done
```

Replace with:
```markdown
When `export_mode: never`, set manifest `memory_bank_export` → `n_a`.

## API tooling export (optional)

When `domain-config.yaml` `api_tooling.export_mode` is `p5` or (`optional` and user requested export):

| Output | Location | Required fields | Note |
|--------|----------|------------------|------|
| Postman collection | `postman/postman_collection.json` | Numbered folder per in-scope repo/service, built from `API_CATALOG.md` + P1 Auth & Gateway + P2 Deployment base URLs | Required when `export_mode: p5` |
| Per-env environment files | `postman/postman_environment.<env>.json` (one per `api_tooling.envs`) | Importable, base URL from § Deployment | Required |
| Generator config | `postman/environment.defaults.json` | Not imported — `gen_postman.py` input | Required |
| Generator script | `postman/gen_postman.py` | Regenerates env files, patches collection (`appVersion`/`versionCode` sync) | Required |
| OTP helper | `postman/fetch_otp_from_redis.py` | Only when `api_tooling.otp_helper` resolves to on (see below) | Conditional |
| README | `postman/README.md` | Import steps, Happy Path, Newman command | Required |
| Manifest artifact | `manifest.yaml` `api_tooling_export` | `ok` \| `waived` \| `n_a` | Update every P5 |

**`otp_helper` resolution:** `always` → always write it; `never` → never; `auto` (default) → write it only
if any in-scope repo's P1 Auth & Gateway subsection recorded Redis OTP-pattern usage — cite the evidence in
the script's header comment.

**Procedure:** [api-tooling-integration.md](../reference/api-tooling-integration.md).

**Evidence rule:** every request in the collection traces to an `API_CATALOG.md` row. A route with no
evidenced auth model (P1 recorded `UNKNOWN`) gets a commented-out placeholder header in the collection —
never an invented value.

When `export_mode: never`, set manifest `api_tooling_export` → `n_a`.

## Definition of Done
```

- [ ] **Step 3: Create `reference/api-tooling-integration.md`**

Write the full file:

```markdown
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
  where P1 recorded a debug-ingress path) — never a literal secret value, only variable placeholders.
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
```

- [ ] **Step 4: `reference/deliverable-templates.md` — add the row**

Find:
```markdown
| `<repo>/memory-bank/*.md` | Optional P5 — per-repo Memory Bank export ([memory-bank-integration.md](memory-bank-integration.md)) |

Export templates (not copied at Session 0): [templates/memory-bank/](../templates/memory-bank/).
```

Replace with:
```markdown
| `<repo>/memory-bank/*.md` | Optional P5 — per-repo Memory Bank export ([memory-bank-integration.md](memory-bank-integration.md)) |
| `postman/*` | Optional P5 — Postman/curl export ([api-tooling-integration.md](api-tooling-integration.md)) |

Export templates (not copied at Session 0): [templates/memory-bank/](../templates/memory-bank/),
[templates/postman/](../templates/postman/).
```

- [ ] **Step 5: Verify**

```bash
grep -n "api_tooling\|api-tooling-integration" domain-comprehension/workflow/phase-5.md domain-comprehension/reference/deliverable-templates.md
test -f domain-comprehension/reference/api-tooling-integration.md && echo "file exists"
```
Expected: matches in both modified files; new file exists.

- [ ] **Step 6: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-5.md domain-comprehension/reference/deliverable-templates.md domain-comprehension/reference/domain-config-schema.md
```
Expected: no output, exit 0. (Task 1's `api-tooling-integration.md` link in `domain-config-schema.md` now
resolves since this task creates the file — this is the deferred link-check from Task 1 Step 2.)

Note: this link-check will show `templates/postman/` as a dangling reference from `deliverable-templates.md`
only if the script checks directory links — it checks `.md` file links only (per its `grep -oE` pattern
matching `\.md(#anchor)?`), so a directory link like `[templates/postman/](../templates/postman/)` is not
checked by this script and will not fail. No action needed.

- [ ] **Step 7: Commit**

```bash
git add domain-comprehension/workflow/phase-5.md domain-comprehension/reference/api-tooling-integration.md domain-comprehension/reference/deliverable-templates.md
git commit -m "feat(domain-comprehension): add P5 api_tooling export section and integration doc"
```

---

### Task 5: SKILL.md updates

**Files:**
- Modify: `domain-comprehension/SKILL.md`

**Interfaces:**
- Consumes: `api_tooling.export_mode` from Task 1, `api-tooling-integration.md` from Task 4.
- Produces: nothing new consumed by later tasks.

- [ ] **Step 1: Extend "Allowed writes only"**

Find:
```markdown
**Allowed writes only:**

- Markdown deliverables + `domain-config.yaml` + **`manifest.yaml`** (every phase) + `.understand-anything/**`
- Per-repo `memory-bank/**` when `memory_bank.export_mode` is not `never`
  ([memory-bank-integration.md](reference/memory-bank-integration.md))
```

Replace with:
```markdown
**Allowed writes only:**

- Markdown deliverables + `domain-config.yaml` + **`manifest.yaml`** (every phase) + `.understand-anything/**`
- Per-repo `memory-bank/**` when `memory_bank.export_mode` is not `never`
  ([memory-bank-integration.md](reference/memory-bank-integration.md))
- `postman/**` when `api_tooling.export_mode` is not `never`
  ([api-tooling-integration.md](reference/api-tooling-integration.md))
```

- [ ] **Step 2: Add a "Key tools explained" bullet**

Find:
```markdown
- **Cursor Memory Bank** (optional P5) — project per-repo `memory-bank/*.md` from comprehension
  deliverables + `.generated/` graph appendix. `npx cursor-bank init` is scaffolding only; P5 export
  replaces a separate "initialize memory bank" pass. See [memory-bank-integration.md](reference/memory-bank-integration.md).
```

Replace with:
```markdown
- **Cursor Memory Bank** (optional P5) — project per-repo `memory-bank/*.md` from comprehension
  deliverables + `.generated/` graph appendix. `npx cursor-bank init` is scaffolding only; P5 export
  replaces a separate "initialize memory bank" pass. See [memory-bank-integration.md](reference/memory-bank-integration.md).

- **API tooling export** (optional P5) — `postman/` runnable Postman collection + curl-equivalent generator
  from comprehension deliverables (`API_CATALOG.md`, P1 Auth & Gateway, P2 Deployment base URLs). See
  [api-tooling-integration.md](reference/api-tooling-integration.md).
```

- [ ] **Step 3: Add a line under the "Minimum viable deliverables by delivery_mode" table**

Find:
```markdown
For a **first-time quick orientation**, only `domain-config.yaml` and `EXEC_SUMMARY.md` are needed.
The full deliverable set (20+ files) is the target for `FULL` mode across multiple sessions.
```

Replace with:
```markdown
For a **first-time quick orientation**, only `domain-config.yaml` and `EXEC_SUMMARY.md` are needed.
The full deliverable set (20+ files) is the target for `FULL` mode across multiple sessions.

`api_tooling.export_mode` (like `memory_bank.export_mode`) is independent of `delivery_mode` — it applies
whenever P5 runs, including under `ADD_REPO`.
```

- [ ] **Step 4: Verify**

```bash
grep -n "api_tooling\|API tooling export\|postman/\*\*" domain-comprehension/SKILL.md
```
Expected: at least 4 matches.

- [ ] **Step 5: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/SKILL.md
```
Expected: no output, exit 0.

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/SKILL.md
git commit -m "docs(domain-comprehension): cross-reference api_tooling export from SKILL.md"
```

---

### Task 6: `templates/postman/` skeleton files (JSON + README, no executable code)

**Files:**
- Create: `domain-comprehension/templates/postman/environment.defaults.json`
- Create: `domain-comprehension/templates/postman/postman_collection.json`
- Create: `domain-comprehension/templates/postman/README.md`

**Interfaces:**
- Consumes: the deliverable file list from Task 4.
- Produces: the exact `environment.defaults.json` shape (`active_env`, `envs.<name>.{baseUrl,directBaseUrl,appVersion,versionCode,signatureSalt}`) and the collection's base `variable` key names (`baseUrl`, `directBaseUrl`, `appVersion`, `versionCode`, `signatureSalt`, `jwt`, `userId`) — Task 7's `gen_postman.py` reads/writes exactly these keys, and its tests build fixtures matching this shape.

- [ ] **Step 1: Create `templates/postman/environment.defaults.json`**

```json
{
  "active_env": "qa",
  "envs": {
    "qa": {
      "baseUrl": "https://qa-api.example.com/<bff>/<service>",
      "directBaseUrl": "https://qa-<service>.example.ai",
      "appVersion": "1.0.0",
      "versionCode": "100",
      "signatureSalt": "${SIGNATURE_SALT_QA}"
    },
    "uat": {
      "baseUrl": "https://uat-api.example.com/<bff>/<service>",
      "directBaseUrl": "https://uat-<service>.example.ai",
      "appVersion": "1.0.0",
      "versionCode": "100",
      "signatureSalt": "${SIGNATURE_SALT_UAT}"
    },
    "prod": {
      "baseUrl": "https://api.example.com/<bff>/<service>",
      "directBaseUrl": "https://<service>.example.ai",
      "appVersion": "1.0.0",
      "versionCode": "100",
      "signatureSalt": "${SIGNATURE_SALT_PROD}"
    }
  }
}
```

- [ ] **Step 2: Create `templates/postman/postman_collection.json`**

```json
{
  "info": {
    "name": "<SERVICE_NAME> API",
    "description": "Generated by domain-comprehension P5 api_tooling export. See ../../reference/api-tooling-integration.md.",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [],
  "variable": [
    { "key": "baseUrl", "value": "", "type": "string" },
    { "key": "directBaseUrl", "value": "", "type": "string" },
    { "key": "appVersion", "value": "", "type": "string" },
    { "key": "versionCode", "value": "", "type": "string" },
    { "key": "signatureSalt", "value": "", "type": "string" },
    { "key": "jwt", "value": "", "type": "string" },
    { "key": "userId", "value": "", "type": "string" }
  ]
}
```

- [ ] **Step 3: Create `templates/postman/README.md`**

````markdown
# Postman / curl tooling

Generated by domain-comprehension's `api_tooling` P5 export. See
[api-tooling-integration.md](../../reference/api-tooling-integration.md) for how this is built and what
evidence backs each request.

## Import

1. Postman → Import → `postman_collection.json`
2. Postman → Import → the `postman_environment.<env>.json` file(s) for the environment(s) you need
3. Select the imported environment in Postman's environment dropdown (top right)

## Regenerating environment files

Environment files are generated from `environment.defaults.json` — do **not** hand-edit
`postman_environment.*.json` directly, edit `environment.defaults.json` and re-run:

```bash
python3 gen_postman.py --all                  # regenerate every env file
python3 gen_postman.py --env qa                # regenerate just one
python3 gen_postman.py --patch-collection      # sync appVersion/versionCode from active_env into the collection
```

## Happy Path

Run the "Happy Path Runner" folder in the imported collection top-to-bottom in the Postman Collection
Runner, using the environment matching your target.

## Newman

```bash
newman run postman_collection.json -e postman_environment.qa.json --insecure
```

## OTP flows

If this service uses Redis-backed OTPs, use `fetch_otp_from_redis.py` — see that file's `--help` for
usage. It never hardcodes a Redis key pattern; pass this service's exact pattern via `--key-pattern`
(found in this engagement's `{map_file}` § Per-Repo Deep Dives → Auth & Gateway).
````

- [ ] **Step 4: Verify all three files**

```bash
python3 -c "import json; json.load(open('domain-comprehension/templates/postman/environment.defaults.json'))" && echo "environment.defaults.json valid JSON"
python3 -c "import json; json.load(open('domain-comprehension/templates/postman/postman_collection.json'))" && echo "postman_collection.json valid JSON"
test -f domain-comprehension/templates/postman/README.md && echo "README.md exists"
```
Expected: both JSON files parse; README exists.

- [ ] **Step 5: Commit**

```bash
git add domain-comprehension/templates/postman/environment.defaults.json domain-comprehension/templates/postman/postman_collection.json domain-comprehension/templates/postman/README.md
git commit -m "feat(domain-comprehension): add postman template skeleton (env config, collection, README)"
```

---

### Task 7: `gen_postman.py` (TDD)

**Files:**
- Create: `domain-comprehension/templates/postman/gen_postman.py`
- Create: `domain-comprehension/tests/test_gen_postman.py`

**Interfaces:**
- Consumes: the `environment.defaults.json` shape and `postman_collection.json` `variable` key names from Task 6.
- Produces: `generate_environment(env_name, env_config) -> dict`, `generate_env_file(defaults, env_name, out_dir) -> Path`, `patch_collection(defaults, collection) -> dict`, `main(argv=None) -> int` — no other task calls these directly, but Task 10's smoke check runs this script end-to-end.

- [ ] **Step 1: Write the failing tests**

Create `domain-comprehension/tests/test_gen_postman.py`:

```python
"""Tests for templates/postman/gen_postman.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "templates" / "postman"))

from gen_postman import (  # noqa: E402
    build_environment,
    generate_env_file,
    main,
    patch_collection,
)


def _defaults() -> dict:
    return {
        "active_env": "qa",
        "envs": {
            "qa": {
                "baseUrl": "https://qa-api.example.com/bff/svc",
                "appVersion": "1.0.0",
                "versionCode": "100",
            },
            "uat": {
                "baseUrl": "https://uat-api.example.com/bff/svc",
                "appVersion": "2.0.0",
                "versionCode": "200",
            },
        },
    }


def test_build_environment_structure() -> None:
    env = build_environment("qa", _defaults()["envs"]["qa"])
    assert env["name"] == "qa"
    assert env["_postman_variable_scope"] == "environment"
    values_by_key = {v["key"]: v for v in env["values"]}
    assert values_by_key["baseUrl"]["value"] == "https://qa-api.example.com/bff/svc"
    assert values_by_key["baseUrl"]["enabled"] is True
    assert values_by_key["appVersion"]["type"] == "default"


def test_generate_env_file_writes_valid_json(tmp_path: Path) -> None:
    out_path = generate_env_file(_defaults(), "qa", tmp_path)
    assert out_path == tmp_path / "postman_environment.qa.json"
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert data["name"] == "qa"


def test_generate_env_file_unknown_env_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        generate_env_file(_defaults(), "staging", tmp_path)


def test_patch_collection_updates_existing_variable() -> None:
    collection = {
        "variable": [
            {"key": "appVersion", "value": "0.0.0", "type": "string"},
            {"key": "baseUrl", "value": "unchanged", "type": "string"},
        ]
    }
    patched = patch_collection(_defaults(), collection)
    by_key = {v["key"]: v for v in patched["variable"]}
    assert by_key["appVersion"]["value"] == "1.0.0"
    assert by_key["baseUrl"]["value"] == "unchanged"


def test_patch_collection_adds_missing_variable() -> None:
    collection = {"variable": [{"key": "appVersion", "value": "0.0.0", "type": "string"}]}
    patched = patch_collection(_defaults(), collection)
    keys = {v["key"] for v in patched["variable"]}
    assert "versionCode" in keys
    by_key = {v["key"]: v for v in patched["variable"]}
    assert by_key["versionCode"]["value"] == "100"


def test_patch_collection_missing_active_env_raises() -> None:
    defaults = {"envs": {"qa": {"appVersion": "1.0.0"}}}
    with pytest.raises(KeyError):
        patch_collection(defaults, {"variable": []})


def test_patch_collection_unknown_active_env_raises() -> None:
    defaults = {"active_env": "staging", "envs": {"qa": {"appVersion": "1.0.0"}}}
    with pytest.raises(KeyError):
        patch_collection(defaults, {"variable": []})


def test_main_all_generates_every_env_file(tmp_path: Path) -> None:
    defaults_path = tmp_path / "environment.defaults.json"
    defaults_path.write_text(json.dumps(_defaults()), encoding="utf-8")
    exit_code = main(["--all", "--defaults", str(defaults_path), "--out-dir", str(tmp_path)])
    assert exit_code == 0
    assert (tmp_path / "postman_environment.qa.json").is_file()
    assert (tmp_path / "postman_environment.uat.json").is_file()


def test_main_patch_collection(tmp_path: Path) -> None:
    defaults_path = tmp_path / "environment.defaults.json"
    defaults_path.write_text(json.dumps(_defaults()), encoding="utf-8")
    collection_path = tmp_path / "postman_collection.json"
    collection_path.write_text(json.dumps({"variable": []}), encoding="utf-8")

    exit_code = main(
        [
            "--patch-collection",
            "--defaults",
            str(defaults_path),
            "--collection",
            str(collection_path),
        ]
    )
    assert exit_code == 0
    patched = json.loads(collection_path.read_text(encoding="utf-8"))
    by_key = {v["key"]: v for v in patched["variable"]}
    assert by_key["appVersion"]["value"] == "1.0.0"


def test_main_no_flags_prints_help_and_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "usage" in captured.out.lower()


def test_main_missing_defaults_file_returns_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["--all", "--defaults", str(tmp_path / "nope.json"), "--out-dir", str(tmp_path)])
    assert exit_code == 1
    captured = capsys.readouterr()
    assert "not found" in captured.err
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd domain-comprehension
python3 -m pytest tests/test_gen_postman.py -v
```
Expected: collection error / `ModuleNotFoundError: No module named 'gen_postman'` — the module doesn't
exist yet. This is the RED state.

- [ ] **Step 3: Implement `templates/postman/gen_postman.py`**

```python
#!/usr/bin/env python3
"""Regenerate postman_environment.<env>.json files and patch collection variables
from environment.defaults.json. See ../../reference/api-tooling-integration.md.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULTS_PATH = HERE / "environment.defaults.json"
COLLECTION_PATH = HERE / "postman_collection.json"

# Collection variables this script is allowed to patch — anything else in
# postman_collection.json is hand-authored and left untouched.
PATCHABLE_COLLECTION_KEYS = ("appVersion", "versionCode")


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def build_environment(env_name: str, env_config: dict[str, Any]) -> dict[str, Any]:
    """Build a Postman environment JSON structure for one env block."""
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"postman-env-{env_name}")),
        "name": env_name,
        "values": [
            {"key": key, "value": str(value), "type": "default", "enabled": True}
            for key, value in env_config.items()
        ],
        "_postman_variable_scope": "environment",
    }


def generate_env_file(defaults: dict[str, Any], env_name: str, out_dir: Path) -> Path:
    envs = defaults.get("envs", {})
    if env_name not in envs:
        raise KeyError(f"no '{env_name}' block in environment.defaults.json envs")
    env_json = build_environment(env_name, envs[env_name])
    out_path = out_dir / f"postman_environment.{env_name}.json"
    _write_json(out_path, env_json)
    return out_path


def patch_collection(defaults: dict[str, Any], collection: dict[str, Any]) -> dict[str, Any]:
    """Sync PATCHABLE_COLLECTION_KEYS in collection['variable'] from the active env's defaults."""
    active_env = defaults.get("active_env")
    if not active_env:
        raise KeyError("environment.defaults.json missing 'active_env'")
    envs = defaults.get("envs", {})
    if active_env not in envs:
        raise KeyError(f"active_env '{active_env}' has no block in envs")
    active_values = envs[active_env]

    variables = collection.setdefault("variable", [])
    existing_by_key = {v.get("key"): v for v in variables if isinstance(v, dict)}
    for key in PATCHABLE_COLLECTION_KEYS:
        if key not in active_values:
            continue
        value = str(active_values[key])
        if key in existing_by_key:
            existing_by_key[key]["value"] = value
        else:
            variables.append({"key": key, "value": value, "type": "string"})
    return collection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", help="Generate postman_environment.<env>.json for one env")
    parser.add_argument("--all", action="store_true", help="Generate for every env in environment.defaults.json")
    parser.add_argument(
        "--patch-collection",
        action="store_true",
        help="Sync appVersion/versionCode into postman_collection.json from active_env",
    )
    parser.add_argument("--defaults", type=Path, default=DEFAULTS_PATH, help="Path to environment.defaults.json")
    parser.add_argument("--collection", type=Path, default=COLLECTION_PATH, help="Path to postman_collection.json")
    parser.add_argument(
        "--out-dir", type=Path, default=HERE, help="Directory to write postman_environment.<env>.json files"
    )
    args = parser.parse_args(argv)

    if not args.env and not args.all and not args.patch_collection:
        parser.print_help()
        return 1

    if not args.defaults.is_file():
        print(f"error: {args.defaults} not found", file=sys.stderr)
        return 1
    defaults = _load_json(args.defaults)

    if args.env:
        try:
            path = generate_env_file(defaults, args.env, args.out_dir)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {path}")

    if args.all:
        for env_name in defaults.get("envs", {}):
            path = generate_env_file(defaults, env_name, args.out_dir)
            print(f"wrote {path}")

    if args.patch_collection:
        if not args.collection.is_file():
            print(f"error: {args.collection} not found", file=sys.stderr)
            return 1
        collection = _load_json(args.collection)
        try:
            collection = patch_collection(defaults, collection)
        except KeyError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        _write_json(args.collection, collection)
        print(f"patched {args.collection}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd domain-comprehension
python3 -m pytest tests/test_gen_postman.py -v
```
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add domain-comprehension/templates/postman/gen_postman.py domain-comprehension/tests/test_gen_postman.py
git commit -m "feat(domain-comprehension): add gen_postman.py generator with tests"
```

---

### Task 8: `fetch_otp_from_redis.py` (TDD, lightweight — no live Redis dependency)

**Files:**
- Create: `domain-comprehension/templates/postman/fetch_otp_from_redis.py`
- Create: `domain-comprehension/tests/test_fetch_otp_from_redis.py`

**Interfaces:**
- Consumes: nothing from other tasks (standalone script).
- Produces: `build_key(key_pattern, identifier) -> str` — no other task calls this directly.

- [ ] **Step 1: Write the failing tests**

Create `domain-comprehension/tests/test_fetch_otp_from_redis.py`:

```python
"""Tests for templates/postman/fetch_otp_from_redis.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "templates" / "postman" / "fetch_otp_from_redis.py"
sys.path.insert(0, str(ROOT / "templates" / "postman"))

from fetch_otp_from_redis import build_key, main  # noqa: E402


def test_build_key_substitutes_identifier() -> None:
    assert build_key("otp:{identifier}", "919999999999") == "otp:919999999999"


def test_build_key_missing_placeholder_raises() -> None:
    with pytest.raises(ValueError):
        build_key("otp:fixed", "919999999999")


def test_main_missing_required_args_exits_nonzero() -> None:
    with pytest.raises(SystemExit) as exc_info:
        main([])
    assert exc_info.value.code != 0


def test_script_compiles_without_redis_installed() -> None:
    with pytest.raises(ImportError):
        import redis  # noqa: F401
    result = subprocess.run(
        [sys.executable, "-m", "py_compile", str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_module_imports_without_redis_installed() -> None:
    # Importing the module itself must not require `redis` — only calling
    # fetch_otp() should. This is what makes --help usable without the
    # redis package installed.
    import fetch_otp_from_redis

    assert hasattr(fetch_otp_from_redis, "fetch_otp")
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd domain-comprehension
python3 -m pytest tests/test_fetch_otp_from_redis.py -v
```
Expected: `ModuleNotFoundError: No module named 'fetch_otp_from_redis'` — RED state. (The
`test_script_compiles_without_redis_installed` test's own `pytest.raises(ImportError)` sanity-check for
`import redis` should already pass, confirming the environment genuinely lacks `redis` — this proves the
later `test_module_imports_without_redis_installed` test is meaningful, not vacuous.)

- [ ] **Step 3: Implement `templates/postman/fetch_otp_from_redis.py`**

```python
#!/usr/bin/env python3
"""Fetch an OTP value from Redis for manual/Postman testing.

Never hardcodes a Redis key pattern or credentials — pass this service's exact
key pattern via --key-pattern (see this engagement's {map_file} section Per-Repo
Deep Dives -> Auth & Gateway for the real pattern, e.g. 'otp:{identifier}').

Connection config comes from env vars only:
  REDIS_HOST, REDIS_PORT (default 6379), REDIS_DB (default 0), REDIS_PASSWORD (optional)
"""

from __future__ import annotations

import argparse
import os
import sys


def build_key(key_pattern: str, identifier: str) -> str:
    if "{identifier}" not in key_pattern:
        raise ValueError("--key-pattern must contain the literal placeholder '{identifier}'")
    return key_pattern.format(identifier=identifier)


def fetch_otp(key: str) -> str | None:
    import redis  # imported lazily so --help works without the redis package installed

    client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "0")),
        password=os.environ.get("REDIS_PASSWORD") or None,
        decode_responses=True,
    )
    return client.get(key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--key-pattern",
        required=True,
        help="Redis key pattern with an '{identifier}' placeholder, e.g. 'otp:{identifier}'",
    )
    parser.add_argument(
        "--identifier", required=True, help="Phone number / user id / whatever this service keys OTPs by"
    )
    args = parser.parse_args(argv)

    try:
        key = build_key(args.key_pattern, args.identifier)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    value = fetch_otp(key)
    if value is None:
        print(f"no value at key {key!r} (not sent yet, or already expired)", file=sys.stderr)
        return 1

    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd domain-comprehension
python3 -m pytest tests/test_fetch_otp_from_redis.py -v
```
Expected: all 5 tests PASS. `test_main_missing_required_args_exits_nonzero` passes because `argparse`
raises `SystemExit(2)` on missing required arguments — the test only checks the exit code is non-zero, not
a specific value.

- [ ] **Step 5: Commit**

```bash
git add domain-comprehension/templates/postman/fetch_otp_from_redis.py domain-comprehension/tests/test_fetch_otp_from_redis.py
git commit -m "feat(domain-comprehension): add fetch_otp_from_redis.py helper with tests"
```

---

### Task 9: Validator content-check for `postman_collection.json`

**Files:**
- Modify: `domain-comprehension/scripts/validate_manifest_yaml.py`
- Modify: `domain-comprehension/tests/test_validate_manifest.py`

**Interfaces:**
- Consumes: the `api_tooling_export` artifact id from Task 1.
- Produces: `_validate_api_tooling_content(workspace_root: Path, *, artifacts: list[Any] | None) -> list[str]`, wired into `validate_manifest(..., check_content=True)` alongside the existing gates. Terminal task for this validator file — no other task depends on it.

- [ ] **Step 1: Write the failing tests**

Append to `domain-comprehension/tests/test_validate_manifest.py` (after the last existing test,
`test_check_content_merge_conflict_dash_evidence_not_mistaken_for_separator`):

```python
def _mark_api_tooling_ok(data: dict) -> None:
    for artifact in data["artifacts"]:
        if artifact["id"] == "api_tooling_export":
            artifact["status"] = "ok"
            return
    raise AssertionError("api_tooling_export artifact not found in template — run Task 1 first")


def test_check_content_api_tooling_ok_valid_collection_passes(tmp_path: Path) -> None:
    data = _minimal_manifest()
    _mark_api_tooling_ok(data)
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    postman_dir = tmp_path / "postman"
    postman_dir.mkdir()
    (postman_dir / "postman_collection.json").write_text(
        '{"info": {"name": "x"}, "item": []}', encoding="utf-8"
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("api_tooling_export" in e or "postman_collection.json" in e for e in errors)


def test_check_content_api_tooling_ok_missing_file_fails(tmp_path: Path) -> None:
    data = _minimal_manifest()
    _mark_api_tooling_ok(data)
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("postman/postman_collection.json is missing" in e for e in errors)


def test_check_content_api_tooling_ok_invalid_json_fails(tmp_path: Path) -> None:
    data = _minimal_manifest()
    _mark_api_tooling_ok(data)
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    postman_dir = tmp_path / "postman"
    postman_dir.mkdir()
    (postman_dir / "postman_collection.json").write_text("{not valid json", encoding="utf-8")
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("invalid JSON" in e for e in errors)


def test_check_content_api_tooling_n_a_skips_check(tmp_path: Path) -> None:
    data = _minimal_manifest()
    # api_tooling_export stays at its template default status: n_a
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("api_tooling_export" in e or "postman_collection.json" in e for e in errors)
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
cd domain-comprehension
python3 -m pytest tests/test_validate_manifest.py -k api_tooling -v
```
Expected: `test_check_content_api_tooling_ok_missing_file_fails` and
`test_check_content_api_tooling_ok_invalid_json_fails` FAIL (no error raised, the gate is a no-op — it
doesn't exist yet). The other two pass trivially (they assert absence of an error). Confirm the failure
message shows `assert False` / no matching error string.

- [ ] **Step 3: Implement `_validate_api_tooling_content`**

In `domain-comprehension/scripts/validate_manifest_yaml.py`, add `json` to the imports — find:
```python
import argparse
import sys
from pathlib import Path
from typing import Any
```
Replace with:
```python
import argparse
import json
import sys
from pathlib import Path
from typing import Any
```

Add the function immediately after `_validate_merge_conflicts_gate` (before `def validate_manifest(`):

```python
def _validate_api_tooling_content(
    workspace_root: Path,
    *,
    artifacts: list[Any] | None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifacts, list):
        return errors
    artifact = next(
        (a for a in artifacts if isinstance(a, dict) and a.get("id") == "api_tooling_export"),
        None,
    )
    if artifact is None or artifact.get("status") != "ok":
        return errors

    collection_path = workspace_root / "postman" / "postman_collection.json"
    if not collection_path.is_file():
        errors.append(
            "check-content: api_tooling_export marked ok but postman/postman_collection.json is missing"
        )
        return errors
    try:
        with collection_path.open(encoding="utf-8") as handle:
            collection = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"check-content: postman/postman_collection.json invalid JSON: {exc}")
        return errors
    if not isinstance(collection, dict) or "info" not in collection or "item" not in collection:
        errors.append("check-content: postman/postman_collection.json missing required 'info'/'item' keys")
    return errors
```

Wire it into `validate_manifest`'s `check_content` block — find:
```python
                errors.extend(
                    _validate_merge_conflicts_gate(
                        workspace_root,
                        phases=phases if isinstance(phases, dict) else None,
                    )
                )

    return errors
```

Replace with:
```python
                errors.extend(
                    _validate_merge_conflicts_gate(
                        workspace_root,
                        phases=phases if isinstance(phases, dict) else None,
                    )
                )
                errors.extend(
                    _validate_api_tooling_content(
                        workspace_root,
                        artifacts=data.get("artifacts") if isinstance(data.get("artifacts"), list) else None,
                    )
                )

    return errors
```

Also update the `--check-content` CLI help string — find:
```python
        help="Verify EXEC_SUMMARY.md sections, P2b runtime validation gate, and RISK_MAP.md merge-conflicts gate (requires --workspace-root)",
```
Replace with:
```python
        help="Verify EXEC_SUMMARY.md sections, P2b runtime validation gate, RISK_MAP.md merge-conflicts gate, and postman_collection.json validity (requires --workspace-root)",
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd domain-comprehension
python3 -m pytest tests/test_validate_manifest.py -k api_tooling -v
```
Expected: all 4 new tests PASS.

- [ ] **Step 5: Run the full `test_validate_manifest.py` suite for regressions**

```bash
cd domain-comprehension
python3 -m pytest tests/test_validate_manifest.py -v
```
Expected: all tests pass (22 pre-existing + 4 new = 26 total), no regressions.

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/scripts/validate_manifest_yaml.py domain-comprehension/tests/test_validate_manifest.py
git commit -m "feat(domain-comprehension): validator content-check for postman_collection.json"
```

---

### Task 10: Full-suite smoke check

**Files:** none modified — verification only.

**Interfaces:**
- Consumes: everything from Tasks 1–9.
- Produces: nothing (terminal task).

- [ ] **Step 1: Run the complete domain-comprehension test suite**

```bash
cd domain-comprehension
python3 -m pytest tests/ -v
```
Expected: all tests pass (includes `test_validate_manifest.py`, `test_validate_sub_agent_merge.py`,
`test_gen_postman.py`, `test_fetch_otp_from_redis.py`).

- [ ] **Step 2: Validate the template manifest itself still passes**

```bash
cd domain-comprehension
python3 scripts/validate_manifest_yaml.py templates/manifest.yaml
```
Expected: `ok: templates/manifest.yaml`.

- [ ] **Step 3: End-to-end smoke test of the generator against the shipped templates**

```bash
cd /tmp && rm -rf api-tooling-smoke && mkdir api-tooling-smoke && cd api-tooling-smoke
cp /Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/templates/postman/*.json .
cp /Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/templates/postman/gen_postman.py .
python3 gen_postman.py --all --patch-collection
python3 -c "import json; json.load(open('postman_environment.qa.json')); json.load(open('postman_environment.uat.json')); json.load(open('postman_environment.prod.json')); json.load(open('postman_collection.json')); print('all outputs valid JSON')"
cd / && rm -rf /tmp/api-tooling-smoke
```
Expected: `wrote .../postman_environment.qa.json` (and uat, prod), `patched .../postman_collection.json`,
then `all outputs valid JSON`. This proves the shipped template files and the shipped generator actually
work together end-to-end, not just against the unit tests' synthetic fixtures.

- [ ] **Step 4: Repo-wide dangling-link check on every file this plan touched**

```bash
cd /Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode
bash scripts/lint-dangling-md-links.sh \
  domain-comprehension/templates/domain-config.yaml \
  domain-comprehension/reference/domain-config-schema.md \
  domain-comprehension/reference/manifest-schema.md \
  domain-comprehension/workflow/phase-1.md \
  domain-comprehension/workflow/phase-2.md \
  domain-comprehension/templates/DEPENDENCY_GRAPH.md \
  domain-comprehension/workflow/phase-5.md \
  domain-comprehension/reference/api-tooling-integration.md \
  domain-comprehension/reference/deliverable-templates.md \
  domain-comprehension/SKILL.md \
  domain-comprehension/templates/postman/README.md
```
Expected: no output, exit code 0. (`.yaml` and `.json` files are skipped by this script's `.md`-only
pattern — no error even though they're listed; harmless to include them.)

- [ ] **Step 5: Confirm no unintended files changed**

```bash
git status --short domain-comprehension/ docs/
```
Expected: clean (everything from this plan already committed in Tasks 1–9).

No commit for this task — it's verification-only.
