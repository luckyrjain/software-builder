# Domain Comprehension Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the domain-comprehension skill by adding investigation recipes to thin workflow files, co-locating required output tables in every workflow file, adding a DELTA delivery mode, workflow versioning, and two new domain packs.

**Architecture:** All changes are to markdown files inside `domain-comprehension/`. No code changes. Verification uses grep/wc to confirm expected sections exist in each file after editing.

**Tech Stack:** Markdown, YAML (domain packs), bash (verification commands)

## Global Constraints

- All workflow files must end at `workflow_version: 1.2` after this pass
- `## Required outputs` table must appear directly before `## Checkpoint` in every workflow file
- Domain pack files must follow the exact YAML section structure of `fintech-payout.md`
- Read-only rule: never modify application source in target workspaces — this skill is the target
- All paths are relative to `domain-comprehension/` unless stated otherwise

---

### Task 1: Rewrite `workflow/phase-0-25.md`

**Files:**
- Modify: `domain-comprehension/workflow/phase-0-25.md`

**Interfaces:**
- Consumes: `inventory` (repo list from P0)
- Produces: `contract_inventory` (API catalog, event catalog, contract table)

- [ ] **Step 1: Verify current state (failing test)**

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-25.md
```
Expected: `0` (section does not yet exist)

```bash
grep -c 'rg -l' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-25.md
```
Expected: `0` (no grep recipes yet)

- [ ] **Step 2: Rewrite the file**

Replace the entire contents of `domain-comprehension/workflow/phase-0-25.md` with:

```markdown
---
workflow_version: 1.2
phase: 0.25
produces:
  - contract_inventory
consumes:
  - inventory
---

# Comprehension Phase P0.25 — Cross-repo contracts

Centralize in `{map_file}` § Contracts. Run the grep recipes below per contract type across Tier 0/1
repos. Run parallel to the P0 tail when `inventory` Tier 0/1 rows are done.

## Investigation recipes

### HTTP / REST

```bash
# Find controllers and route definitions
rg -l 'swagger|openapi|@RestController|@RequestMapping|@GetMapping|@PostMapping|router\.' \
  --glob '!test*' --glob '!vendor' --glob '!node_modules' <repo>

# Find committed OpenAPI/Swagger spec files
find <repo> -name 'openapi.yaml' -o -name 'swagger.yaml' -o -name 'openapi.json' 2>/dev/null
```

### gRPC / Proto

```bash
rg -l '\.proto' --glob '!vendor' <repo>
find <repo> -name '*.proto' | head -20
```

### Events (Kafka, RabbitMQ, SQS, SNS)

```bash
# Find topic/queue/exchange names and event handlers
rg -l 'topic|exchange|queue|KafkaListener|@EventHandler|@SqsListener|@RabbitListener' \
  --glob '!test*' --glob '!vendor' <repo>

# Find topic name constants
rg -rn 'TOPIC|QUEUE|EXCHANGE' --glob '!test*' <repo> | grep -i 'const\|val \|final '
```

### Shared database tables

```bash
# Find table names in migrations
find <repo> -name '*.sql' | xargs rg -l 'CREATE TABLE' 2>/dev/null

# Cross-repo: for each table found, grep other repos
rg -l 'FROM <table_name>\|INSERT INTO <table_name>\|JOIN <table_name>' \
  --glob '!test*' --glob '!*.sql' <other_repo>
```

### Shared packages / internal libraries

```bash
# npm / pnpm
cat <repo>/package.json | grep '"@<org>/'

# Maven
grep -A1 '<groupId>com\.<org>' <repo>/pom.xml | grep '<artifactId>'

# Go modules
grep '<org>/' <repo>/go.mod
```

### Idempotency / correlation keys

```bash
rg -l 'idempotency.key|requestId|X-Idempotency|x-request-id|correlationId' \
  --glob '!test*' <repo>
```

## Producer vs. consumer detection

| Signal | Role |
|--------|------|
| HTTP server handler (`@RestController`, `router.post`, `func handler`) | **Producer** |
| HTTP client (`FeignClient`, `RestTemplate`, `fetch`, `axios`) | **Consumer** |
| Migration that creates the table (`CREATE TABLE`) | **Producer** |
| `SELECT / INSERT` referencing a table created in another repo | **Consumer** |
| `@KafkaListener` / `@SqsListener` / `@RabbitListener` | **Consumer** |
| `kafkaTemplate.send` / `sns.publish` / `rabbitTemplate.send` | **Producer** |

**Anti-patterns:**
- Do not mark a Feign client or Retrofit interface as a producer — find the handler on the server side
- Do not infer producer from HTTP client alone — verify the handler exists in the target repo
- Do not mark a shared library as a producer unless it owns the event topic or table schema

## Contract inventory table (required)

| Contract | Type | Producer repo | Consumer repo(s) | Schema location | Evidence |
|----------|------|--------------|------------------|-----------------|----------|

## Sub-agents

One `explore` agent, multi-repo grep across Tier 0/1 repos.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Contract inventory | `{map_file}` § Contracts | Contract, Type, Producer repo, Consumer repo(s), Schema location, Evidence | Phase incomplete |
| API catalog | `API_CATALOG.md` | method, path, producer, consumers, implementation, exercise | Phase incomplete |
| Event catalog | `EVENT_CATALOG.md` | topic, schema, producer, consumers, implementation, exercise | Phase incomplete — UNKNOWN rows with reason allowed |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · [phase-outputs.md § P0.25](../reference/phase-outputs.md#p025--contracts)
```

- [ ] **Step 3: Verify (passing tests)**

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-25.md
```
Expected: `1`

```bash
grep -c 'rg -l' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-25.md
```
Expected: `6` (six grep recipe lines)

```bash
grep 'workflow_version' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-25.md
```
Expected: `workflow_version: 1.2`

- [ ] **Step 4: Commit**

```bash
git add domain-comprehension/workflow/phase-0-25.md
git commit -m "feat(domain-comprehension): add grep recipes and required outputs to P0.25"
```

---

### Task 2: Rewrite `workflow/phase-3b.md`

**Files:**
- Modify: `domain-comprehension/workflow/phase-3b.md`

**Interfaces:**
- Consumes: `core_domain_deep_dive` (P3 output)
- Produces: `fraud_compliance_review` (control table in `{map_file}`)

- [ ] **Step 1: Verify current state (failing test)**

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3b.md
```
Expected: `0`

```bash
grep -c 'rg -l' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3b.md
```
Expected: `0`

- [ ] **Step 2: Rewrite the file**

Replace the entire contents of `domain-comprehension/workflow/phase-3b.md` with:

```markdown
---
workflow_version: 1.2
phase: 3b
produces:
  - fraud_compliance_review
consumes:
  - core_domain_deep_dive
---

# Comprehension Phase P3b — Fraud & compliance (adversarial)

**Sub-agent:** one read-only `generalPurpose` agent with checklist below.

**Required first step:** Re-read every P3 claim; attempt to **disprove** each with counter-evidence or a
bypass path in code. Only write `Exists? YES` after failing to find a bypass.

## Investigation recipes

### Replay / duplicate protection

```bash
rg -l 'ON CONFLICT|idempoten|dedup|requestId|UNIQUE.*constraint|duplicate.*key' \
  --glob '!test*' --glob '!vendor' <repo>
```

### Webhook spoofing / signature verification

```bash
rg -l 'signature|hmac|X-Hub-Signature|webhook.*secret|verify.*signature' \
  --glob '!test*' <repo>
```

### Hardcoded secrets

```bash
# Flag file paths only — never print values
rg -rn 'password\s*=\s*["'"'"'][^$\{]|api_key\s*=\s*["'"'"']|secret\s*=\s*["'"'"']' \
  config/ src/ --glob '!*.md' --glob '!*test*' <repo> | cut -d: -f1-2
```

### Audit trail / immutable log

```bash
rg -l '@Audit|auditLog|audit_trail|AuditEvent|immutable.*log|append.only' \
  --glob '!test*' <repo>
```

### PII in log statements

```bash
# Find log calls near PII field names
rg -l 'log\.(info|debug|warn|error)' --glob '!test*' <repo> | \
  xargs rg -l 'pan\b|aadhaar|phone|email|account.*number|card.*number' 2>/dev/null
```

### Maker–checker / dual control

```bash
rg -l 'approve|checker|dual.*control|four.*eye|second.*factor.*approval|makerChecker' \
  --glob '!test*' <repo>
```

### Privilege escalation

```bash
rg -l 'hasRole|@PreAuthorize|isAdmin|bypass.*auth|skipAuth|ADMIN.*role' \
  --glob '!test*' <repo>
```

## Controls checklist

For each control, attempt to **disprove** with a bypass path before recording `Exists? YES`.

- Replay / duplicate operations (beyond happy-path idempotency)
- Webhook spoofing / signature verification
- Maker–checker / dual control
- Compliance bypass paths (KYC/AML/sanctions as relevant)
- Privilege escalation (unauthorized trigger/approve)
- Manual override + audit trail
- Stale state, orphaned records, recon mismatches
- Audit log immutability; PII in logs (sample log statements)
- Cross-border / regulatory constraints from config
- **Hardcoded secrets** — flag paths only, **never print values**

## Output format

Write to `{map_file}` § Fraud & Compliance. One row per control:

| Control | Exists? | Evidence | Gaps | Confidence |
|---------|---------|----------|------|------------|

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Fraud & compliance table | `{map_file}` § Fraud & Compliance | Control, Exists?, Evidence, Gaps, Confidence | Phase incomplete |

## Checkpoint

[phase-completion-gate.md](../reference/phase-completion-gate.md) · [phase-outputs.md § P3b](../reference/phase-outputs.md#p3b--adversarial)
```

- [ ] **Step 3: Verify (passing tests)**

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3b.md
```
Expected: `1`

```bash
grep -c 'rg -l' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3b.md
```
Expected: `7`

```bash
grep 'workflow_version' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3b.md
```
Expected: `workflow_version: 1.2`

- [ ] **Step 4: Commit**

```bash
git add domain-comprehension/workflow/phase-3b.md
git commit -m "feat(domain-comprehension): add per-control grep recipes and required outputs to P3b"
```

---

### Task 3: Update `workflow/session-0b.md`

**Files:**
- Modify: `domain-comprehension/workflow/session-0b.md`

**Interfaces:**
- Consumes: `domain_config_yaml`, `domain_map_skeleton`
- Produces: `mcp_profile`, `squad_map`

- [ ] **Step 1: Verify current state (failing test)**

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0b.md
```
Expected: `0`

```bash
grep -c 'CODEOWNERS' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0b.md
```
Expected: `1` (the "fall back to CODEOWNERS in P1" mention — no actual procedure)

- [ ] **Step 2: Add CODEOWNERS fallback step and required outputs**

After the existing Step 6 block (the `## Conflicts` step ending with `do not cap overall mapping at HIGH when sources disagree.`) and before `## Checkpoint`, insert:

```markdown
## Step 7 — CODEOWNERS fallback (both MCP ❌ only)

Skip this step when GitLab ✅ or Datadog ✅.

When both MCP unavailable, derive squad ownership with confidence capped at LOW:

1. **CODEOWNERS file** — look for `.github/CODEOWNERS`, `CODEOWNERS`, or `docs/CODEOWNERS` at repo root:
   ```bash
   find <repo> -maxdepth 3 -name 'CODEOWNERS' 2>/dev/null
   ```
   Extract team handles from patterns covering the service entry directory
   (e.g., `src/payments/ @org/payments-team` → squad = `payments-team`).

2. **Git log top contributors** (last 90 days):
   ```bash
   git -C <repo> log --since=90.days.ago --pretty='%ae' -- <service-dir> \
     | sort | uniq -c | sort -rn | head -5
   ```
   Record top 2 email domains as squad hint (e.g., `@payments.example.com` → `payments`).

3. **Package manifest maintainers:**
   ```bash
   # npm
   cat <repo>/package.json | grep -A5 '"maintainers"'
   # Maven
   grep -A3 '<developers>' <repo>/pom.xml | head -10
   # Go — derive from module path org segment
   head -1 <repo>/go.mod
   ```

4. Record each repo in `SQUAD_MAP.md` with:
   - `GitLab namespace`: N/A
   - `GitLab squad`: UNKNOWN
   - `Datadog service`: UNKNOWN
   - `Datadog team`: UNKNOWN
   - `Owner confidence`: LOW
   - `Source`: CODEOWNERS (or GIT_LOG if no CODEOWNERS found)

5. All CODEOWNERS-derived ownership caps at LOW confidence — **never raise to MEDIUM** without a
   second independent signal.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| MCP profile | `SQUAD_MAP.md` header | GitLab status, Datadog status | Phase incomplete |
| Squad map | `SQUAD_MAP.md` | Repo, GitLab squad, Datadog team, Owner confidence, Conflict | Phase skipped — note in KNOWN_OMISSIONS.md |
```

- [ ] **Step 3: Verify (passing tests)**

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0b.md
```
Expected: `1`

```bash
grep -c 'CODEOWNERS' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0b.md
```
Expected: `≥5` (multiple references in the new step)

```bash
grep -c 'git -C.*log.*since=90' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0b.md
```
Expected: `1`

- [ ] **Step 4: Also bump workflow_version**

Change `workflow_version: 1.0` to `workflow_version: 1.2` in the frontmatter.

- [ ] **Step 5: Commit**

```bash
git add domain-comprehension/workflow/session-0b.md
git commit -m "feat(domain-comprehension): add CODEOWNERS fallback and required outputs to session-0b"
```

---

### Task 4: Update `workflow/inputs.md`

**Files:**
- Modify: `domain-comprehension/workflow/inputs.md`

**Interfaces:**
- Consumes: (nothing — parses from user message)
- Produces: `workspace_root`, `workspace_layout`, `domain_name`, `domain_config`, `delivery_mode`

- [ ] **Step 1: Verify current state (failing test)**

```bash
grep -c 'DELTA' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/inputs.md
```
Expected: `0`

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/inputs.md
```
Expected: `0`

- [ ] **Step 2: Add DELTA mode to the Delivery mode table**

Replace the existing `## Delivery mode` section:

```markdown
## Delivery mode

| Mode | Behavior |
|------|----------|
| `FULL` | All comprehension phases for all in-scope repos |
| `QUICK` | Session 0 + P0 + draft five questions only — no P0.5 mechanical pass |
| `RESUME` | Read `PROGRESS.md`; continue from Next action |
```

with:

```markdown
## Delivery mode

| Mode | Behavior |
|------|----------|
| `FULL` | All comprehension phases for all in-scope repos |
| `QUICK` | Session 0 + P0 + draft five questions only — no P0.5 mechanical pass |
| `RESUME` | Read `PROGRESS.md`; continue from Next action |
| `DELTA` | Re-run phases for repos whose HEAD SHA changed since last manifest |

### DELTA mode — procedure

Requires `manifest.yaml` with at least P0 complete. If not present, fall back to `FULL` with a warning.

1. Load `manifest.yaml`; for each `repos[]` entry run:
   ```bash
   git -C <repo-path> rev-parse HEAD
   ```
   Compare to `repos[].sha`. Build the **changed set** of repos where SHA differs.

2. Determine **affected phases** from the changed set:
   - **P0, P1**: re-run for every repo in the changed set
   - **P0.25**: re-run contract rows for changed repos only; carry forward unchanged repos' rows
   - **P2**: re-run if any Tier 0/1 repo changed (flow likely affected)
   - **P2b**: re-run if P2 re-ran and Datadog ✅
   - **P3**: re-run if the core-domain repo (from `domain_config.deliverables.core_section`) changed
   - **P3b**: re-run if P3 re-ran
   - **P4, P5**: always re-run after any upstream phase re-ran

3. Phases with no upstream changes keep their `complete` status in manifest unchanged.

4. At end: run `validate_manifest_yaml.py`; update `engagement.last_updated` and
   `engagement.next_action`.
```

- [ ] **Step 3: Add Required outputs section before the end of file**

Append before the final `## Environment constraints` section (or at the end of the file if no Checkpoint exists):

```markdown
## Required outputs

| Output | Source | If absent |
|--------|--------|-----------|
| `workspace_root` | User message or prompt | Ask user — cannot proceed |
| `workspace_layout` | Auto-detect or user-specified | Default to `sibling-repos` detection |
| `domain_name` | User message; confirm in Session 0 | Ask user |
| `delivery_mode` | User message | Default `FULL` |
| `domain_pack` | User message (optional) | Skip — no pack merge |
```

- [ ] **Step 4: Verify (passing tests)**

```bash
grep -c 'DELTA' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/inputs.md
```
Expected: `≥4`

```bash
grep -c '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/inputs.md
```
Expected: `1`

- [ ] **Step 5: Bump workflow_version**

Change `workflow_version: 1.0` to `workflow_version: 1.2` in the frontmatter.

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/workflow/inputs.md
git commit -m "feat(domain-comprehension): add DELTA mode and required outputs to inputs.md"
```

---

### Task 5: Add required outputs to `session-0.md`, `phase-0.md`, `phase-0-5.md`

**Files:**
- Modify: `domain-comprehension/workflow/session-0.md`
- Modify: `domain-comprehension/workflow/phase-0.md`
- Modify: `domain-comprehension/workflow/phase-0-5.md`

- [ ] **Step 1: Verify current state (failing test)**

```bash
grep -c '## Required outputs' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-5.md
```
Expected: all three show `0`

- [ ] **Step 2: Add Required outputs to `session-0.md`**

Insert directly before `## Classification` (the final section before the end of the file):

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Domain config | `domain-config.yaml` | All schema fields or defaults | Phase incomplete |
| Workspace inventory | `PROGRESS.md` § Repo status | Repo, branch, SHA, tier, classification | Phase incomplete |
| Known omissions (seed) | `KNOWN_OMISSIONS.md` | MCP gaps, bulk excludes | Phase incomplete — empty file not allowed |
| Entry services (provisional) | `{map_file}` § Inventory stub | Repo, entry-point type, file path | Phase incomplete |
| Initial unknowns | `UNKNOWNS.md` | ≥0 rows; five questions DRAFT in EXEC_SUMMARY.md | Phase incomplete |
| Evidence summary (stub) | `EXEC_SUMMARY.md` + manifest | All counters initialized to 0 | Phase incomplete |
| Deliverable stubs | All `templates/` copies at workspace root | Non-empty headers | Phase incomplete |
| `manifest.yaml` | workspace root | schema_version: 2, all phases pending | Phase incomplete |
```

Also change `workflow_version: 1.1` to `workflow_version: 1.2` in the frontmatter.

- [ ] **Step 3: Add Required outputs to `phase-0.md`**

Insert directly before `## Checkpoint`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Repository census | `{map_file}` § Inventory | Repo, tier, classification, evidence per repo | Phase incomplete |
| Technology stack | `{map_file}` § Inventory | Per repo: languages, frameworks, build tooling | Phase incomplete |
| Bounded contexts (initial) | `BOUNDED_CONTEXTS.md` | Context name, repos, confidence | Phase incomplete |
| Config surface table | `{map_file}` § Inventory | Key/env var, repo, purpose, prod-only flag | Phase incomplete |
| Repo relationships table | `{map_file}` § Inventory | From repo, relationship type, to repo, evidence | Phase incomplete |
| `manifest.repos[]` | `manifest.yaml` | name, branch, sha, tier, classification, inventory: complete | Phase incomplete |
```

Also change `workflow_version: 1.0` to `workflow_version: 1.2`.

- [ ] **Step 4: Add Required outputs to `phase-0-5.md`**

Insert directly before `## Checkpoint`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Mechanical insights | `{map_file}` § Mechanical Insights | Top 20 files, top 15 endpoints, domain flows, 10 essential files | Phase incomplete |
| Service call graph | `DEPENDENCY_GRAPH.md` § Service call | Mermaid diagram + confidence | Phase incomplete |
| Graph manifest | `.understand-anything/manifest.json` | Tier 0/1 entries: ok or failed with reason | Phase incomplete |
| Metrics | `.understand-anything/metrics.csv` | Present or N/A with reason | Phase incomplete — waived with reason allowed |
```

Also change `workflow_version: 1.0` to `workflow_version: 1.2`.

- [ ] **Step 5: Verify (passing tests)**

```bash
grep -c '## Required outputs' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-5.md
```
Expected: all three show `1`

```bash
grep 'workflow_version' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/session-0.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-0-5.md
```
Expected: all show `workflow_version: 1.2`

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/workflow/session-0.md \
        domain-comprehension/workflow/phase-0.md \
        domain-comprehension/workflow/phase-0-5.md
git commit -m "feat(domain-comprehension): add inline required outputs to session-0, P0, P0.5"
```

---

### Task 6: Add required outputs to `phase-1.md`, `phase-2.md`, `phase-2b.md`

**Files:**
- Modify: `domain-comprehension/workflow/phase-1.md`
- Modify: `domain-comprehension/workflow/phase-2.md`
- Modify: `domain-comprehension/workflow/phase-2b.md`

- [ ] **Step 1: Verify current state (failing test)**

```bash
grep -c '## Required outputs' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-1.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-2.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-2b.md
```
Expected: all three show `0`

- [ ] **Step 2: Add Required outputs to `phase-1.md`**

Insert directly before `## Checkpoint`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Per-repo deep dives | `{map_file}` § Per-Repo Deep Dives | One subsection per in-scope application repo | Phase incomplete |
| Ownership cards | `{map_file}` § Per-Repo Deep Dives | Owns / does-not-own per repo with evidence | Phase incomplete |
| Bounded contexts (refined) | `BOUNDED_CONTEXTS.md` | Context cards + logical context Mermaid | Phase incomplete |
| Data ownership (initial) | `DATA_OWNERSHIP.md` | Per entity: authoritative source, replicas, caches | Phase incomplete |
| Domain glossary | `DOMAIN_GLOSSARY.md` | Terms, definitions, evidence paths | Phase incomplete |
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence | Phase incomplete — empty allowed with note |
```

Also change `workflow_version: 1.0` to `workflow_version: 1.2`.

- [ ] **Step 3: Add Required outputs to `phase-2.md`**

Insert directly before `## Checkpoint`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Trigger catalog | `{map_file}` § Flow | All trigger types + entry repo | Phase incomplete |
| Runtime sequence | `{map_file}` § Flow | Numbered narrative + Mermaid sequence (happy + failure paths) | Phase incomplete |
| Business flows | `BUSINESS_FLOWS.md` | ≥3 journeys | Phase incomplete |
| Critical path | `{map_file}` § Flow | Vertical chain diagram | Phase incomplete |
| State machine | `STATE_MACHINE.md` | States, transitions, Mermaid stateDiagram-v2 | Phase incomplete |
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config | Phase incomplete — UNKNOWN allowed with reason |
| Sync/async boundary table | `{map_file}` § Flow | Step, sync/async, transport, timeout owner, evidence | Phase incomplete |
| Code/graph divergence | `{map_file}` § Flow | Classified edges: MISSING_IN_CODE \| DEAD_CODE \| DYNAMIC_DISPATCH \| UNKNOWN | Phase incomplete |
```

Also change `workflow_version: 1.1` to `workflow_version: 1.2`.

- [ ] **Step 4: Add Required outputs to `phase-2b.md`**

Insert directly before `## Checkpoint`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Runtime validation table | `{map_file}` § Flow → Runtime validation (Datadog) | From→To, Code (P2), Graph, Datadog, Verdict, Confidence, Evidence | Phase incomplete if Datadog ✅ |
| Runtime graph | `DEPENDENCY_GRAPH.md` § Runtime | Datadog-confirmed edges, Mermaid | Phase incomplete if Datadog ✅ |
| Exercise updates | `API_CATALOG.md`, `EVENT_CATALOG.md`, `BUSINESS_FLOWS.md` | `runtime_confirmed` where applicable | Phase incomplete if Datadog ✅ |
| Datadog subgraphs | `.understand-anything/diagrams/datadog-service-deps.md` | Per entry service | Phase incomplete if Datadog ✅ |
| Skip record | `{map_file}` § Flow stub + `KNOWN_OMISSIONS.md` | Skip reason | Required when Datadog ❌ |
```

Also change `workflow_version: 1.0` to `workflow_version: 1.2`.

- [ ] **Step 5: Verify (passing tests)**

```bash
grep -c '## Required outputs' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-1.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-2.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-2b.md
```
Expected: all three show `1`

```bash
grep 'workflow_version' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-1.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-2.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-2b.md
```
Expected: all show `workflow_version: 1.2`

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/workflow/phase-1.md \
        domain-comprehension/workflow/phase-2.md \
        domain-comprehension/workflow/phase-2b.md
git commit -m "feat(domain-comprehension): add inline required outputs to P1, P2, P2b"
```

---

### Task 7: Add required outputs to `phase-3.md`, `phase-4.md`, `phase-5.md`

**Files:**
- Modify: `domain-comprehension/workflow/phase-3.md`
- Modify: `domain-comprehension/workflow/phase-4.md`
- Modify: `domain-comprehension/workflow/phase-5.md`

- [ ] **Step 1: Verify current state (failing test)**

```bash
grep -c '## Required outputs' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-4.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-5.md
```
Expected: all three show `0`

- [ ] **Step 2: Add Required outputs to `phase-3.md`**

Insert directly before `## Checkpoint`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Core domain section | `{map_file}` § `core_section` | Idempotency, routing, failure, retry, concurrency, PII | Phase incomplete |
| Implementation matrix | `EXEC_SUMMARY.md` | implementation + exercise axes per [implementation-status.md](../reference/implementation-status.md) | Phase incomplete |
| Data ownership (refined) | `DATA_OWNERSHIP.md` | Complete entity table | Phase incomplete |
| Draft five questions | `EXEC_SUMMARY.md` | Updated through P3 — all five present | Phase incomplete |
| Overall confidence | `EXEC_SUMMARY.md` + `manifest.overall_confidence` | Per confidence-rubric.md | Phase incomplete |
```

Also change `workflow_version: 1.0` to `workflow_version: 1.2`.

- [ ] **Step 3: Add Required outputs to `phase-4.md`**

Insert directly before `## Checkpoint`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Quality & ops section | `{map_file}` § Quality & Ops | Tests, observability, correlation IDs, debt | Phase incomplete |
| Runbook | `RUNBOOK.md` | All procedures or explicit ⚠️ absent | Phase incomplete |
| Smells (full) | `RISK_MAP.md` § Architectural smells | Complete scan across all in-scope repos | Phase incomplete |
| Top smells | `RISK_MAP.md` § Top smells | ≤10 ranked rows by severity × business impact | Phase incomplete |
| Change impact | `BOUNDED_CONTEXTS.md` + `RISK_MAP.md` § Change impact | Per-context if-modified tables | Phase incomplete |
| Change-risk map | `RISK_MAP.md` § Change risk | Safe / Moderate / High / Unknown per service | Phase incomplete |
| Evidence summary | `EXEC_SUMMARY.md` + `manifest.evidence_summary` | All counters updated | Phase incomplete |
```

Also change `workflow_version: 1.1` to `workflow_version: 1.2`.

- [ ] **Step 4: Add Required outputs to `phase-5.md`**

Insert directly before `## Definition of Done`:

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Final five questions | `EXEC_SUMMARY.md` | COMPLETE or UNKNOWN each — no DRAFT allowed | Phase incomplete |
| Overall confidence | `EXEC_SUMMARY.md` | Question table + overall band | Phase incomplete |
| Engineering leader summary | `EXEC_SUMMARY.md` § Engineering Leader Summary | Per [engineering-leader-summary.md](../reference/engineering-leader-summary.md) | Phase incomplete |
| Architecture decisions | `ARCHITECTURE_DECISIONS.md` | ADRs or UNKNOWN | Phase incomplete |
| Repo map table | `EXEC_SUMMARY.md` | classification + squad + tier per repo | Phase incomplete |
| Evidence summary (final) | `EXEC_SUMMARY.md` + manifest | All counters populated (non-zero where evidence exists) | Phase incomplete |
| Section confidences | `EXEC_SUMMARY.md` | Per major section | Phase incomplete |
| PROGRESS.md status | `PROGRESS.md` | `FIRST_PASS_COMPLETE` | Phase incomplete |
```

Also change `workflow_version: 1.0` to `workflow_version: 1.2`.

- [ ] **Step 5: Verify (passing tests)**

```bash
grep -c '## Required outputs' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-4.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-5.md
```
Expected: all three show `1`

```bash
grep 'workflow_version' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-3.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-4.md \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/phase-5.md
```
Expected: all show `workflow_version: 1.2`

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/workflow/phase-3.md \
        domain-comprehension/workflow/phase-4.md \
        domain-comprehension/workflow/phase-5.md
git commit -m "feat(domain-comprehension): add inline required outputs to P3, P4, P5"
```

---

### Task 8: Workflow versioning + changelog

**Files:**
- Create: `domain-comprehension/reference/workflow-changelog.md`
- Verify: all 13 workflow files now at `workflow_version: 1.2`

- [ ] **Step 1: Verify all workflow files are at 1.2 (failing test — before this task)**

After completing Tasks 1–7, all files should be at 1.2 except possibly `phase-0-25.md` and `phase-3b.md` (handled in Tasks 1–2). Verify none remain at `1.0` or `1.1`:

```bash
grep -r 'workflow_version' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/
```
Expected: all 13 lines show `workflow_version: 1.2`

If any show `1.0` or `1.1`, fix them manually:
```bash
# Fix any remaining 1.0 files
sed -i '' 's/workflow_version: 1\.0/workflow_version: 1.2/g' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/*.md

# Fix any remaining 1.1 files
sed -i '' 's/workflow_version: 1\.1/workflow_version: 1.2/g' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/*.md
```

- [ ] **Step 2: Create `reference/workflow-changelog.md`**

Create the file at `domain-comprehension/reference/workflow-changelog.md`:

```markdown
# Workflow changelog

| Version | Date | Files | Change |
|---------|------|-------|--------|
| 1.0 | initial | all | Base workflow files |
| 1.1 | 2026-06 | phase-2.md, phase-4.md | phase-2: divergence gate, product-line matrix, gate sequence diagram, sub-flows; phase-4: change-risk map section |
| 1.2 | 2026-07-01 | all | Inline `## Required outputs` table in all 13 workflow files; P0.25: investigation grep recipes + producer/consumer heuristics; P3b: per-control grep recipes + adversarial output format; session-0b: CODEOWNERS fallback (Step 7); inputs.md: DELTA delivery mode |

## Versioning rule

Increment the **minor version** on any behavioral change to a workflow file: new steps, new required
outputs, new decision tables, new investigation recipes. Patch version is not used — workflow files
are instructions, not code.

When bumping: update every file in the same commit, add a row to this table.
```

- [ ] **Step 3: Verify (passing tests)**

```bash
grep -c 'workflow_version: 1.2' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/*.md | \
  grep -v ':0'
```
Expected: 13 files, all showing count `1`

```bash
wc -l /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/workflow-changelog.md
```
Expected: `> 10`

- [ ] **Step 4: Commit**

```bash
git add domain-comprehension/workflow/*.md \
        domain-comprehension/reference/workflow-changelog.md
git commit -m "feat(domain-comprehension): bump all workflow files to v1.2, add workflow-changelog.md"
```

---

### Task 9: Add `auth-identity` domain pack

**Files:**
- Create: `domain-comprehension/reference/domain-packs/auth-identity.md`
- Modify: `domain-comprehension/reference/domain-packs/README.md`

- [ ] **Step 1: Verify current state (failing test)**

```bash
ls /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/
```
Expected: only `README.md` and `fintech-payout.md`

- [ ] **Step 2: Create `auth-identity.md`**

Create `domain-comprehension/reference/domain-packs/auth-identity.md`:

```markdown
# Domain pack: auth-identity

Pack for authentication, authorization, identity, and session management domains.

Merge into `domain-config.yaml` at Session 0.

## domain

```yaml
domain:
  name: auth
  display_name: Auth & Identity
  description: Authentication, authorization, session lifecycle, and identity federation
```

## scope

```yaml
scope:
  include_keywords:
    - auth
    - identity
    - token
    - session
    - permission
    - role
    - oauth
    - oidc
    - saml
    - jwt
    - sso
  exclude_patterns:
    - '*-mock*'
    - '*-stub*'
  seed_repos: []          # fill in with your repo names
  conditional_repos: []   # e.g., rate-limiting-service, audit-service
```

## context

```yaml
context:
  regulatory_notes: Replace with applicable compliance scope (GDPR, SOC2, etc.)
  product_lines:
    - name: web
      hints: [web-auth, browser-session, cookie]
    - name: mobile
      hints: [mobile-token, device-auth, biometric]
    - name: service-to-service
      hints: [service-account, client-credentials, m2m]
```

## five_questions

```yaml
five_questions:
  - id: Q1
    question: How are tokens issued and what are their lifetimes?
    search_terms:
      - generateToken
      - issueToken
      - createSession
      - TokenResponse
      - expires_in
      - access_token
      - refresh_token
      - jwt
      - sign
  - id: Q2
    question: How are permissions and roles enforced at the service boundary?
    search_terms:
      - hasRole
      - hasPermission
      - @PreAuthorize
      - checkPermission
      - authorize
      - scope
      - role
      - policy
      - RBAC
      - ABAC
  - id: Q3
    question: How is session/token revocation propagated across services?
    search_terms:
      - revoke
      - invalidate
      - logout
      - blacklist
      - denylist
      - introspect
      - token.*revok
      - session.*destroy
  - id: Q4
    question: How does MFA / step-up authentication work?
    search_terms:
      - mfa
      - totp
      - otp
      - step.up
      - secondFactor
      - challenge
      - biometric
      - device.*verify
  - id: Q5
    question: How are third-party identity providers federated?
    search_terms:
      - saml
      - oidc
      - oauth
      - sso
      - federation
      - idp
      - assertion
      - sub.*claim
      - jwks
      - well-known
```

## critical_path_tiers

```yaml
critical_path_tiers:
  tier_0:
    label: Token issuance + validation
    definition: Issues tokens or validates them on every authenticated request
    provisional: []   # e.g., auth-service, token-service
  tier_1:
    label: Session store + JWKS
    definition: Required for token validation and revocation
    provisional: []   # e.g., session-store, jwks-endpoint-service
  tier_2:
    label: MFA + federation
    definition: Required for elevated auth flows and SSO
    provisional: []   # e.g., mfa-service, idp-gateway
  tier_3:
    label: Audit + rate-limiting
    definition: Auth observability and abuse prevention
    provisional: []   # e.g., audit-service, rate-limiter
  flow_critical_gates:
    - []   # e.g., token-service, permission-service
```

## deliverables

```yaml
deliverables:
  map_file: AUTH_MAP.md
  core_section: Token & Session Lifecycle
```

## ownership

```yaml
ownership:
  gitlab:
    org_prefix: ''          # fill in
    squad_path_segment: 2
    group_prefixes: []      # fill in
  datadog:
    service_aliases: {}
    domain_service_query: "name:auth*"
```

## architecture_validation

```yaml
architecture_validation:
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []
  critical_paths:
    - name: token-issuance-happy-path
      services: []    # fill in: e.g., [api-gateway, auth-service, token-service]
    - name: token-validation-path
      services: []    # fill in: e.g., [api-gateway, jwks-service]
    - name: revocation-propagation
      services: []    # fill in: e.g., [auth-service, session-store, dependent-services]
```

## Architecture signals to investigate

| Signal | What to determine |
|--------|-------------------|
| Token issuance | Which service signs — is there a dedicated token service or embedded auth? |
| JWKS rotation | How often keys rotate; is rotation zero-downtime? |
| Revocation store | Redis / DB / distributed cache — propagation delay |
| MFA bypass paths | Are there admin overrides or service-account exemptions? |
| Session vs stateless | Are sessions stored server-side or purely JWT-stateless? |

## Business flows (minimum 3 for P2)

Seed journeys for `BUSINESS_FLOWS.md`:

| Journey | Trigger | Terminal |
|---------|---------|----------|
| User login (password) | Credentials submitted | Access + refresh token issued |
| Token refresh | Refresh token presented | New access token or session expired |
| MFA step-up | High-risk action triggered | MFA verified or step-up denied |
| SSO / federation | IdP assertion received | Local session created |
| Logout / revocation | User logout or admin revoke | Token blacklisted, session destroyed |

## P3b adversarial hints

- **Token replay after revocation:** issue a token, revoke it, confirm it cannot be used on dependent services
- **Privilege escalation:** can a `user` role claim obtain a `admin` scope token?
- **JWKS rotation window:** is there a gap where old and new keys are both valid beyond the intended window?
- **Stale session after password reset:** confirm active tokens are revoked on password/credential change
- **Federation `sub` collision:** can two IdP users share the same `sub` claim after IdP migration?
```

- [ ] **Step 3: Add row to `README.md`**

In `domain-comprehension/reference/domain-packs/README.md`, replace the Available packs table:

```markdown
| Pack | File | Use when |
|------|------|----------|
| fintech-payout | [fintech-payout.md](fintech-payout.md) | Disbursement, payout, bank rails, recon |
```

with:

```markdown
| Pack | File | Use when |
|------|------|----------|
| fintech-payout | [fintech-payout.md](fintech-payout.md) | Disbursement, payout, bank rails, recon |
| auth-identity | [auth-identity.md](auth-identity.md) | Authentication, authorization, session management, SSO/federation |
| e-commerce-checkout | [e-commerce-checkout.md](e-commerce-checkout.md) | Cart, checkout, order, inventory, fulfillment, refunds |
```

- [ ] **Step 4: Verify (passing tests)**

```bash
ls /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/auth-identity.md
```
Expected: file present

```bash
grep -c '## P3b adversarial hints' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/auth-identity.md
```
Expected: `1`

```bash
grep -c 'five_questions' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/auth-identity.md
```
Expected: `1`

- [ ] **Step 5: Commit**

```bash
git add domain-comprehension/reference/domain-packs/auth-identity.md \
        domain-comprehension/reference/domain-packs/README.md
git commit -m "feat(domain-comprehension): add auth-identity domain pack"
```

---

### Task 10: Add `e-commerce-checkout` domain pack

**Files:**
- Create: `domain-comprehension/reference/domain-packs/e-commerce-checkout.md`
- Modify: `domain-comprehension/reference/domain-packs/README.md` (already updated in Task 9 — verify row exists)

- [ ] **Step 1: Verify current state (failing test)**

```bash
ls /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/e-commerce-checkout.md 2>/dev/null || echo "missing"
```
Expected: `missing`

- [ ] **Step 2: Create `e-commerce-checkout.md`**

Create `domain-comprehension/reference/domain-packs/e-commerce-checkout.md`:

```markdown
# Domain pack: e-commerce-checkout

Pack for cart, checkout, order management, inventory, fulfillment, and refund domains.

Merge into `domain-config.yaml` at Session 0.

## domain

```yaml
domain:
  name: checkout
  display_name: Checkout & Orders
  description: Cart to confirmed order, payment capture, inventory, fulfillment, and returns
```

## scope

```yaml
scope:
  include_keywords:
    - cart
    - order
    - checkout
    - inventory
    - payment
    - fulfil
    - refund
    - shipment
    - coupon
    - promo
  exclude_patterns:
    - '*-mock*'
    - '*-stub*'
  seed_repos: []          # fill in with your repo names
  conditional_repos: []   # e.g., fraud-detection-service, loyalty-service
```

## context

```yaml
context:
  regulatory_notes: Replace with applicable scope (PCI-DSS, regional tax, etc.)
  product_lines:
    - name: digital
      hints: [digital-goods, instant-delivery, no-shipping]
    - name: physical
      hints: [warehouse, fulfillment-center, logistics]
    - name: marketplace
      hints: [seller, vendor, third-party-fulfillment]
```

## five_questions

```yaml
five_questions:
  - id: Q1
    question: How does a cart become a confirmed order?
    search_terms:
      - placeOrder
      - confirmOrder
      - checkoutSession
      - cart.*convert
      - order.*create
      - CartService
      - OrderService
  - id: Q2
    question: When and how is payment captured?
    search_terms:
      - capturePayment
      - chargeCard
      - authorize
      - capture
      - PaymentIntent
      - paymentCapture
      - settle
  - id: Q3
    question: How is inventory reserved and released?
    search_terms:
      - reserveInventory
      - reserve
      - hold
      - release.*inventory
      - stock
      - quantity.*available
      - oversell
  - id: Q4
    question: How does fulfillment or shipping get triggered?
    search_terms:
      - fulfil
      - shipOrder
      - pickPack
      - warehouseJob
      - dispatch
      - tracking
      - courier
  - id: Q5
    question: How are cancellations and refunds handled?
    search_terms:
      - cancel
      - refund
      - reversal
      - compensat
      - return
      - chargeback
      - void
```

## critical_path_tiers

```yaml
critical_path_tiers:
  tier_0:
    label: Order + payment execution
    definition: Confirms the order and captures payment — money changes hands here
    provisional: []   # e.g., order-service, payment-service
  tier_1:
    label: Inventory + fulfillment
    definition: Required to complete the order after payment
    provisional: []   # e.g., inventory-service, fulfillment-service
  tier_2:
    label: Notifications + recon
    definition: Post-order communications, reporting, reconciliation
    provisional: []   # e.g., notification-service, order-recon
  tier_3:
    label: Storefront + BFF
    definition: Entry points, cart, promotions, search
    provisional: []   # e.g., storefront-bff, cart-service, promo-service
  flow_critical_gates:
    - []   # e.g., fraud-check-service, inventory-service
```

## deliverables

```yaml
deliverables:
  map_file: CHECKOUT_MAP.md
  core_section: Order & Payment
```

## ownership

```yaml
ownership:
  gitlab:
    org_prefix: ''          # fill in
    squad_path_segment: 2
    group_prefixes: []      # fill in
  datadog:
    service_aliases: {}
    domain_service_query: "name:order*"
```

## architecture_validation

```yaml
architecture_validation:
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []
  critical_paths:
    - name: checkout-happy-path
      services: []    # fill in: e.g., [storefront-bff, order-service, payment-service, inventory-service]
    - name: refund-path
      services: []    # fill in: e.g., [order-service, payment-service, inventory-service]
    - name: fulfillment-path
      services: []    # fill in: e.g., [order-service, fulfillment-service, logistics-service]
```

## Architecture signals to investigate

| Signal | What to determine |
|--------|-------------------|
| Cart ownership | Is cart state in the storefront BFF, a dedicated cart service, or the order service? |
| Payment timing | Is payment authorized at checkout or only captured at fulfillment? |
| Inventory reservation | Pessimistic (reserve on add-to-cart) vs optimistic (reserve at order confirm)? |
| Async fulfillment | Is fulfillment triggered synchronously in the order flow or via event/queue? |
| Marketplace split | For marketplace: does the platform capture or does each seller capture separately? |

## Business flows (minimum 3 for P2)

Seed journeys for `BUSINESS_FLOWS.md`:

| Journey | Trigger | Terminal |
|---------|---------|----------|
| Standard checkout | Cart submitted | Order confirmed, payment captured, fulfillment queued |
| Order cancellation | User cancels pre-fulfillment | Order cancelled, payment voided/refunded |
| Refund | Return requested or chargeback | Refund issued, inventory restocked |
| Failed payment retry | Payment capture fails | Retry or order cancelled |
| Partial fulfillment | One item out of stock | Partial ship + partial refund or backorder |

## P3b adversarial hints

- **Double-charge on retry:** if the payment capture request times out, can it be replayed without idempotency protection?
- **Inventory oversell race:** can two concurrent checkout sessions reserve the last unit simultaneously?
- **Coupon stacking:** can multiple discount codes be applied in one order beyond policy limits?
- **Partial fulfillment without refund:** if only some items ship, is the partial refund automated or manual?
- **Payment capture before inventory confirm:** can money be taken for an item that cannot be fulfilled?
```

- [ ] **Step 3: Verify README has the e-commerce row**

```bash
grep 'e-commerce-checkout' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/README.md
```
Expected: one line with the pack row

- [ ] **Step 4: Verify the pack file**

```bash
grep -c '## P3b adversarial hints' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/e-commerce-checkout.md
```
Expected: `1`

```bash
grep -c 'five_questions' \
  /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/e-commerce-checkout.md
```
Expected: `1`

- [ ] **Step 5: Final verification — all 18 files changed**

```bash
# All workflow files at 1.2
grep -r 'workflow_version' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/ | grep -v '1\.2'
```
Expected: no output (all at 1.2)

```bash
# All workflow files have Required outputs section
grep -rL '## Required outputs' /Users/luckyjain/Projects/ai-skills/domain-comprehension/workflow/
```
Expected: no output (all files have the section)

```bash
# Both new domain packs exist
ls /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/domain-packs/
```
Expected: `README.md  auth-identity.md  e-commerce-checkout.md  fintech-payout.md`

```bash
# Changelog exists
ls /Users/luckyjain/Projects/ai-skills/domain-comprehension/reference/workflow-changelog.md
```
Expected: file present

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/reference/domain-packs/e-commerce-checkout.md \
        domain-comprehension/reference/domain-packs/README.md
git commit -m "feat(domain-comprehension): add e-commerce-checkout domain pack"
```
