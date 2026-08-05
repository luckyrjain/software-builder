# Domain Comprehension — Improvements Design

**Date:** 2026-07-01
**Branch:** feat/incident-rca-deterministic-output
**Skill:** `domain-comprehension`

---

## Problem statement

The `domain-comprehension` skill has a solid 12-phase pipeline and rich reference documentation, but three categories of weakness reduce reliability:

1. **Thin workflow files** — P0.25 (15 lines) and P3b (25 lines) lack investigation recipes and output format guidance. Two agents following these files produce structurally different outputs.
2. **No co-located output enforcement** — `phase-outputs.md` is the central checklist, but individual workflow files don't repeat required outputs inline. An agent can complete all phase steps and never cross-reference the central checklist.
3. **Missing operational capabilities** — No delta/refresh mode, no CODEOWNERS fallback when MCP is unavailable, only one domain pack.

---

## Scope

**In:** workflow file depth, inline required outputs, CODEOWNERS fallback, delta mode, workflow versioning, two new domain packs.

**Out:** automated evidence-counting scripts, deliverable linting (`lint-deliverables.py`), manifest schema changes beyond delta mode. These belong in a follow-on determinism pass.

---

## Section 1 — Workflow file depth

### 1a. `workflow/phase-0-25.md`

**Current state:** 15 lines. Lists contract types and a table header. No investigation guidance.

**Changes:**

- **Grep recipes per contract type** with exact `rg` commands:
  - HTTP/REST: `rg -l 'swagger|openapi|@RestController|@RequestMapping|router\.' --glob '!test*'`
  - gRPC/proto: `rg -l '\.proto' --glob '!vendor'`
  - Events: `rg -l 'topic|exchange|queue|KafkaListener|@EventHandler' --glob '!test*'`
  - Shared DB: `rg -rn 'FROM <table>|INSERT INTO <table>' across repos` — cross-repo grep for table names found in migrations
  - Shared packages: cross-reference `package.json` / `pom.xml` / `go.mod` dependency names against internal repo names
  - Idempotency keys: `rg -l 'idempotency.key|requestId|X-Idempotency' --glob '!test*'`

- **Producer vs. consumer detection heuristics:**
  - Producer = HTTP server handler / event publisher / migration that creates the table
  - Consumer = HTTP client / event listener / DB reader in a separate repo
  - Anti-pattern: do not mark a Feign client or Retrofit interface as the producer; find the handler on the server side

- **Required outputs table** (inline, before Checkpoint)

- **`workflow_version: 1.2`**

### 1b. `workflow/phase-3b.md`

**Current state:** 25 lines. Bullet list of controls. No grep recipes, no output format.

**Changes:**

- **Per-control grep recipes:**
  - Replay/duplicate: `rg -l 'ON CONFLICT|idempoten|dedup|requestId|UNIQUE.*constraint' --glob '!test*'`
  - Webhook spoofing: `rg -l 'signature|hmac|X-Hub-Signature|webhook.*secret' --glob '!test*'`
  - Hardcoded secrets: `rg -rn 'password\s*=\s*["\x27][^$\{]|api_key\s*=|secret\s*=' config/ src/ --glob '!*.md'` — flag file paths only, never print values
  - Audit trail: `rg -l '@Audit|auditLog|audit_trail|immutable.*log' --glob '!test*'`
  - PII in logs: `rg -l 'log\.(info|debug|warn).*\.(pan|aadhaar|phone|email|account)' --glob '!test*'`

- **Output format:** one row per control in `{map_file}` § Fraud & Compliance:

  ```
  | Control | Exists? | Evidence | Gaps | Confidence |
  ```

- **Adversarial mindset instruction:** before writing any row, re-read the corresponding P3 claim and attempt to find a code path that bypasses the control. Only write `Exists? YES` if no bypass is found in code.

- **Required outputs table** (inline, before Checkpoint)

- **`workflow_version: 1.2`**

### 1c. `workflow/session-0b.md`

**Current state:** Mentions "fall back to CODEOWNERS in P1" but no procedure is defined anywhere.

**Changes:**

- **Step 7 — CODEOWNERS fallback** (new step, runs only when both MCP ❌):
  1. Look for `.github/CODEOWNERS`, `CODEOWNERS`, or `docs/CODEOWNERS` at each repo root
  2. Extract team handles from patterns covering the service entry directory (e.g., `@org/payments-team`)
  3. Git log top contributors: `git log --since=90.days.ago --pretty='%ae' -- <service-dir> | sort | uniq -c | sort -rn | head -5` — record top 2 email domains as squad hint
  4. Check `package.json` `.maintainers[]`, `pom.xml` `<developers>`, or `go.mod` module path for org prefix
  5. Record in `SQUAD_MAP.md` with source column = `CODEOWNERS` and confidence = LOW
  6. All CODEOWNERS-derived ownership caps at LOW — never MEDIUM without a second signal

- **Required outputs table** (inline, before Checkpoint)

---

## Section 2 — Inline required outputs in every workflow file

**Problem:** `phase-outputs.md` is authoritative but separate. Agents can finish phase steps without checking it.

**Fix:** Add `## Required outputs` table to every workflow file, directly before `## Checkpoint`. The table mirrors the relevant `phase-outputs.md` section concisely — it is not a full duplicate.

**Format:**

```markdown
## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Contract inventory | `{map_file}` § Contracts | Contract, Type, Producer, Consumer(s), Evidence | Phase incomplete |
| API catalog | `API_CATALOG.md` | method, path, producer, consumers, implementation, exercise | Phase incomplete |
| Event catalog | `EVENT_CATALOG.md` | topic, schema, producer, consumers | Phase incomplete — UNKNOWN rows with reason allowed |
```

**Files receiving this section** (13 total):

- `workflow/inputs.md`
- `workflow/session-0.md`
- `workflow/session-0b.md`
- `workflow/phase-0.md`
- `workflow/phase-0-25.md`
- `workflow/phase-0-5.md`
- `workflow/phase-1.md`
- `workflow/phase-2.md`
- `workflow/phase-2b.md`
- `workflow/phase-3.md`
- `workflow/phase-3b.md`
- `workflow/phase-4.md`
- `workflow/phase-5.md`

**Rule:** the "If absent" column distinguishes hard blockers (phase incomplete, cannot advance) from soft gaps (UNKNOWN rows with reason allowed).

---

## Section 3 — Delta / refresh mode

**Problem:** No mode for "re-run only what changed." A full re-run over 44 repos when 3 changed is wasteful.

**Fix:** Add `DELTA` delivery mode to `workflow/inputs.md`.

**Behavior:**

1. Require `manifest.yaml` to exist with ≥ P0 complete; if not, fall back to FULL with a warning
2. For each `repos[]` entry in manifest, run `git -C <repo-path> rev-parse HEAD` and compare to stored `sha`
3. **Changed set** = repos where SHA differs
4. **Affected phases:**
   - P0, P1: always re-run for changed repos
   - P0.25: re-run contract rows for changed repos only; carry forward unchanged repos' rows from existing catalogs
   - P2: re-run if any Tier 0/1 repo changed (flow likely affected)
   - P2b: re-run if P2 re-ran and Datadog ✅
   - P3: re-run if the core-domain repo (as identified in `domain_config.core_section`) changed
   - P3b: re-run if P3 re-ran
   - P4, P5: always re-run after any upstream phase re-ran
5. Phases with no upstream changes keep their `complete` status in manifest
6. At end: run validator; update `engagement.last_updated` and `engagement.next_action`

**Updated delivery mode table in `inputs.md`:**

| Mode | Behavior |
|------|----------|
| `FULL` | All phases, all repos — first-pass default |
| `QUICK` | Session 0 + P0 + draft five questions only |
| `RESUME` | Continue from `PROGRESS.md` next action |
| `DELTA` | Re-run phases for repos whose HEAD SHA changed since last manifest |

---

## Section 4 — Workflow versioning + changelog

**Problem:** Files are inconsistently at `1.0` vs `1.1` with no explanation of what changed.

**Fix:**

1. **Bump all workflow files to `workflow_version: 1.2`** as part of this improvement pass
2. **New file: `reference/workflow-changelog.md`**

```markdown
# Workflow changelog

| Version | Date | Files | Change |
|---------|------|-------|--------|
| 1.0 | initial | all | Base workflow files |
| 1.1 | 2026-06 | phase-2.md, phase-4.md | phase-2: divergence gate, product-line matrix, gate sequence diagram; phase-4: change-risk map |
| 1.2 | 2026-07-01 | all | Inline required outputs in all phases; P0.25 + P3b: investigation recipes and grep recipes; session-0b: CODEOWNERS fallback; inputs.md: DELTA mode |

## Versioning rule

Increment minor version on any behavioral change to a workflow file (new steps, new required outputs, new decision tables). Patch version is not used — workflow files are instructions, not code.
```

---

## Section 5 — New domain packs

**Problem:** Only `fintech-payout` exists. Teams working on auth or e-commerce have to author everything from scratch.

**Fix:** Two new packs following the exact structure of `fintech-payout.md`.

### `reference/domain-packs/auth-identity.md`

**Use when:** authentication, authorization, identity, session management, SSO/federation domains.

- **Five questions:** (1) How are tokens issued and what are their lifetimes? (2) How are permissions/roles enforced at the service boundary? (3) How is session revocation propagated? (4) How does MFA/step-up auth work? (5) How are third-party identity providers federated?
- **Search terms:** `authenticate`, `authorize`, `token`, `session`, `permission`, `role`, `scope`, `jwt`, `oauth`, `saml`, `oidc`, `jwks`, `revoke`, `introspect`
- **Critical path tiers:** token issuance (Tier 0) → token validation middleware (Tier 0) → JWKS/introspection endpoint (Tier 1) → session store (Tier 1) → MFA service (Tier 2)
- **P3b adversarial hints:** token replay after revocation, privilege escalation via role misconfiguration, JWKS rotation window, stale session after password reset, federation bypass via `sub` claim collision

### `reference/domain-packs/e-commerce-checkout.md`

**Use when:** cart, checkout, order, inventory, fulfillment domains.

- **Five questions:** (1) How does a cart become a confirmed order? (2) How is payment captured and when? (3) How is inventory reserved and released? (4) How does fulfillment/shipping get triggered? (5) How are cancellations and refunds handled?
- **Search terms:** `cart`, `order`, `checkout`, `inventory`, `reserve`, `payment`, `fulfil`, `refund`, `coupon`, `promo`, `discount`, `shipment`, `cancel`, `capture`
- **Critical path tiers:** cart service (Tier 1) → order service (Tier 0) → payment service (Tier 0) → inventory service (Tier 0) → fulfillment service (Tier 1)
- **P3b adversarial hints:** double-charge on retry, inventory oversell race, coupon stacking, partial fulfillment without refund, payment capture before inventory confirm

**`reference/domain-packs/README.md`** gains two new rows in the Available packs table and a condensed authoring checklist section.

---

## Files changed

| File | Change type |
|------|-------------|
| `workflow/phase-0-25.md` | Rewrite — grep recipes, producer/consumer heuristics, required outputs |
| `workflow/phase-3b.md` | Rewrite — per-control grep recipes, output format, adversarial guidance |
| `workflow/session-0b.md` | Add Step 7 (CODEOWNERS fallback) + required outputs |
| `workflow/inputs.md` | Add DELTA mode |
| `workflow/session-0.md` | Add required outputs table |
| `workflow/phase-0.md` | Add required outputs table |
| `workflow/phase-0-5.md` | Add required outputs table |
| `workflow/phase-1.md` | Add required outputs table |
| `workflow/phase-2.md` | Add required outputs table |
| `workflow/phase-2b.md` | Add required outputs table |
| `workflow/phase-3.md` | Add required outputs table |
| `workflow/phase-4.md` | Add required outputs table |
| `workflow/phase-5.md` | Add required outputs table |
| `reference/workflow-changelog.md` | New file |
| `reference/domain-packs/auth-identity.md` | New file |
| `reference/domain-packs/e-commerce-checkout.md` | New file |
| `reference/domain-packs/README.md` | Add two rows + authoring checklist section |
| All workflow files | `workflow_version: 1.0/1.1` → `1.2` |

---

## Out of scope (follow-on)

- `lint-deliverables.py` — script to verify required sections exist in artifact files
- Automated evidence block counting to verify `manifest.evidence_summary` counters
- Manifest schema version bump for DELTA mode fields
- Additional domain packs (API gateway, notification/messaging)
