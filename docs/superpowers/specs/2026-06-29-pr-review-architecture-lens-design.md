# PR Review — Architecture Lens Design

**Date:** 2026-06-29  
**Status:** Approved for implementation  
**Scope:** Extend the `pr-review` skill with a trigger-gated Architecture Lens (§16)

## Problem

The current `/pr-review` skill focuses heavily on bugs, security, and correctness via a 15-dimension checklist. Senior reviewers also care about structural quality: coupling, boundary violations, cyclic dependencies, hidden shared state, domain leakage, feature-flag debt, intentional tech debt, and testability. These concerns are partially scattered across existing dimensions (maintainability, concurrency, scope) but lack a dedicated, actionable lens.

## Goals

1. Surface architecture findings on MRs where structural change is likely — without bloating trivial bugfix reviews.
2. Anchor every finding to a changed diff line; cite unchanged files only as supporting context.
3. Tier severity: light signals → Medium/Low; hard violations → High.
4. Discover boundaries from repo docs, CODEOWNERS, heuristics, and an optional per-repo override file.
5. Fit the existing §14 IaC / §15 AI/LLM conditional-dimension pattern.

## Non-goals (v1)

- Automated import-graph tooling or new scripts.
- A separate `/pr-review-architecture` skill.
- Standalone severities on unchanged files (context references only).
- Repo-wide dependency maps or Understand-Anything graph integration.
- Blocking merge on architecture Medium/Low alone.
- A new verdict type (still ✅ / 💬 / 🔴 via the existing rubric).

## Decisions (brainstorming outcomes)

| Question | Decision |
|----------|----------|
| When to run | **Trigger-gated** (like §15); user override via `architecture focus` / `arch lens` |
| Severity | **Tiered by violation strength** — light → Medium/Low; hard → High |
| Evidence | **Diff anchor + context** — finding on changed line; related unchanged paths as support |
| Boundary rules | **Docs + heuristics + optional repo override** at `.cursor/skills/pr-review/architecture-lens.md` |

## Approach

**Recommended:** Add §16 to the checklist with detail in `reference/architecture-lens.md`. No new workflow phase — light context expansion reuses Phase 1 step 7 (local file reads). Do not add Phase 1.5 import-graph building in v1.

Rejected alternatives:

- **Phase 1.5 expanded context pass** — better cycle detection but higher token cost and weaker diff grounding.
- **Separate skill** — fragments the senior review experience.

## Architecture

### Placement

| Artifact | Role |
|----------|------|
| `pr-review/reference/review-checklist.md` | §16 summary: triggers, eight concerns, pointer to detail doc |
| `pr-review/reference/architecture-lens.md` | Full triggers, heuristics, severity examples, override format |
| `pr-review/SKILL.md` | Phase 2 activation rule; chat table `arch ·` tag; reference entry |
| `pr-review/reference/severity-rubric.md` | Calibration examples for architecture High/Medium |
| `pr-review/reference/comment-templates.md` | `arch ·` prefix in inline examples |
| `pr-review/examples.md` | One architecture-finding example |
| `.cursor/skills/pr-review/architecture-lens.md` | Optional per-repo override (documented, not shipped in ai-skills) |

No changes to Phase 0/3/4/5 posting logic, `diff-to-positions.py`, or MCP capabilities.

### Activation (trigger-gated)

§16 runs when **any** signal matches in the diff or in imports on changed lines:

| Signal | Examples |
|--------|----------|
| Cross-boundary import | New import/require across top-level packages or documented layer directories |
| New shared/global state | `global`, module-level mutable, new singleton/DI registration |
| New public surface | Exported type/function, new HTTP/RPC handler, new GraphQL field |
| Feature flag | New flag key, `if (flag)`, LaunchDarkly/Unleash/Flipper usage |
| Structural refactor | >3 files in same package moved/renamed, or new `internal/` / `shared/` path |
| Large MR | >50 non-mechanical files (existing Low finding also **enables** §16) |

**User override:** invocation includes `architecture`, `arch lens`, or `architecture focus` → force §16 even without triggers.

**Skip:** mechanical-only MRs (lockfile, generated, bulk rename) unless user overrides.

### Boundary discovery

Evaluate in order:

1. Repo docs under changed paths (`ARCHITECTURE.md`, `AGENTS.md`, `.cursor/rules`, `docs/architecture/`).
2. CODEOWNERS ownership boundaries (cross-check with Phase 1 approval state).
3. Heuristics when docs are silent (e.g. `ui/` → `db/`, handler → another package's `internal/`).
4. Repo override file with explicit allowed/forbidden dependency edges.

Violations of documented **forbidden edges** in the override → **High** by default.

### Phase 2 workflow

```
Phase 2: Review each hunk
  → §16 triggers or user override?
      No  → standard §1–§15 only
      Yes → load architecture-lens.md + repo override
          → evaluate 8 concerns on changed lines
          → emit findings (anchor changed line + related paths as context)
  → merge into severity table
```

**Phase 1 step 7:** when reading local context, also look for `ARCHITECTURE.md`, `docs/architecture/`, and `.cursor/skills/pr-review/architecture-lens.md`.

**Chat output:** when §16 ran, prefix arch rows and add a one-line header:

> **Architecture lens** (triggered: cross-boundary import, new feature flag)

## Eight concerns + severity tiers

Each finding anchors to a **changed line**. Unchanged paths are supporting context only.

### 1. Coupling

**Look for:** new direct dependencies between modules that should stay independent; bypassing facades/ports.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Convenience import skipping an established adapter |
| Hard | High | Core domain depends on infra/UI; payment flow imports billing internals |

### 2. Boundary violations

**Look for:** cross-layer imports per docs or override; CODEOWNERS mismatch without required reviewer.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Heuristic cross-layer import with no documented rule |
| Hard | High | Explicit forbidden edge violated; required CODEOWNER not approved |

### 3. Cyclic dependencies

**Look for:** new import edge completing a cycle; read target file imports when needed (Phase 1 local context).

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Cycle within one feature package |
| Hard | High | Cycle across top-level domains |

### 4. Hidden shared state

**Look for:** module-level mutable state, singletons, process-wide caches, static request-scoped data.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low/Medium | Module cache without TTL/eviction notes |
| Hard | High | Request/user data on global/singleton; mutable static across workers |

Overlaps §7 concurrency — §16 frames design harm; §7 frames runtime correctness.

### 5. Domain leakage

**Look for:** persistence models at API/UI boundaries; business rules in presentation; cross-domain refs without anti-corruption layer.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Internal struct returned where a view-model exists |
| Hard | High | DB model serialized to public API |

### 6. Feature flag debt

**Look for:** new flags without removal plan; permanent behavior behind flags; nested flag spaghetti; unsafe defaults.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low | New flag, no cleanup note |
| Medium | Medium | Flag wraps core logic, no sunset on prod path |
| Hard | High | Flag default enables unsafe prod behavior |

### 7. Tech debt introduced

**Look for:** shortcuts that compound — duplicated abstraction, TODO without ticket, pattern divergence across 3+ files.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low | Small duplication with tracked TODO |
| Hard | Medium | New divergent pattern without justification |
| Hard (regulated) | High | Debt in payments/auth per `domain-overrides.md` |

Does not duplicate §12 hygiene — §16 frames architectural debt.

### 8. Testability reduced

**Look for:** hard dependencies without injection; logic in untestable locations; critical branch requiring full stack.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low | Static call where interface exists nearby |
| Hard | Medium | Core logic in route closure, no extraction |
| Hard | High | Critical untestable branch + no tests in diff → escalate with §8 |

### Severity summary

- **Hard violation** → High (Critical only if combined with security/data-loss per existing rubric).
- **Light / heuristic** → Medium or Low.
- Architecture **High** participates in the existing blocking gate. Medium/Low do not block alone.

## Comment format

```
🟡 **[Medium]** arch · coupling — `checkout/handler.go:14` imports `billing/internal/ledger` directly.

Bypasses the `billing.Client` facade used elsewhere; couples checkout deploys to billing internals.
Related: `billing/internal/ledger/post.go` (unchanged).

Suggested fix: extend `billing.Client` with the needed operation instead of importing `internal/`.
```

## Repo override format

Teams may add `.cursor/skills/pr-review/architecture-lens.md`:

```markdown
## Layers
- `api/` — HTTP handlers; may import `service/`, must not import `db/` or `models/`
- `service/` — business logic; may import `ports/`, `models/`
- `db/` — persistence only

## Forbidden edges
- `api/` → `db/`
- `checkout/` → `billing/internal/`

## Package ownership
- `billing/` — team-billing (required reviewer per CODEOWNERS)
```

## Success criteria

1. Trivial bugfix MR (no triggers) — §16 does not run; review time unchanged.
2. MR adding `checkout → billing/internal` import — anchored High/Medium finding with facade suggestion.
3. MR with new feature flag, no sunset — Low/Medium flag-debt finding.
4. Team with repo override — findings cite the violated rule.
5. All findings pass the existing hallucination guardrail (changed-line anchor).

## Implementation checklist

- [x] Add §16 to `review-checklist.md`
- [x] Create `reference/architecture-lens.md`
- [x] Update `SKILL.md` Phase 2 and Reference section
- [x] Add calibration examples to `severity-rubric.md`
- [x] Update `comment-templates.md` with `arch ·` example
- [x] Add example to `examples.md`
- [x] Run smoke test per `reference/smoke-test.md` (no script changes expected)
