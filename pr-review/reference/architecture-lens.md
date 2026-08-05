# Architecture Lens (§16)

Trigger-gated structural review for senior reviewers. Load this file when §16 activates (see triggers
below). Also check for a repo-local override at `.cursor/skills/pr-review/architecture-lens.md`.

## Grounding rule

Every architecture finding **must anchor to a changed `+`/`-` line** from the Phase 1 review boundary.
You may cite **unchanged files as supporting context** (e.g. the target of a new import, an existing
facade elsewhere) — label them *Related: `path` (unchanged)*. Do not assign severity to lines outside
the diff. If a pattern spans files but only one edge is new, anchor on the introducing import/call.

Prefix findings with `arch · <concern>` in the Finding column and inline comments (e.g. `arch · coupling`).

## Activation

### Triggers (any one enables §16)

Scan changed lines and imports on those lines:

| Signal | What to look for |
|--------|------------------|
| Cross-boundary import | New `import`/`require`/`use` across top-level packages or documented layer dirs |
| New shared/global state | `global`, module-level mutable, new singleton, DI container registration, `static`/`class` mutable |
| New public API boundary | New HTTP/RPC route or handler, GraphQL root query/mutation/subscription, OpenAPI path, or export consumed across package/module boundaries |
| Feature flag | New flag key, `if (flag)`, LaunchDarkly/Unleash/Flipper/Statsig/`feature_flag` usage |
| Structural refactor | >3 files in same package moved/renamed, or new `internal/` / `shared/` / `_private` path |
| Large MR | >50 non-mechanical changed files (pairs with existing MR-size Low finding) |

**User override:** invocation includes `architecture`, `arch lens`, or `architecture focus` → force §16.

**Skip:** mechanical-only MRs (`*.lock`, `vendor/`, `dist/`, generated fixtures, bulk rename with no
logic change) unless user overrides. Also skip when Phase 1 **`fast_path.skip_architecture`** is set
(≤5 files or docs/lockfile profile — `reference/fast-path.md`).

**Does not trigger §16 alone:** a new `public` class, method, or type within an existing package/module
(e.g. routine Java/C# class additions); internal helpers; private/package-local symbols. Those need a
cross-boundary import or another signal above.

Record which triggers fired for the chat header:

> **Architecture lens** (triggered: cross-boundary import, new feature flag)

### Boundary discovery (evaluate in order)

0. **Monorepo shared-module impact** — when the diff touches `libs/`, `packages/`, `common/`, or
   documented shared kernels, enumerate **downstream services** (import graph, service catalog, or
   CODEOWNERS). Emit Medium **arch · blast-radius** when downstream lacks test coverage in the MR.
1. **Repo docs** under changed paths: `ARCHITECTURE.md`, `docs/architecture/`, `AGENTS.md`,
   `.cursor/rules`, layer READMEs.
   **Also:** `review-rules.yaml` (see `reference/review-rules.md`) — optional `architecture:` block for
   layers and forbidden edges.
2. **CODEOWNERS** — cross-check Phase 1 approval state; required owner not approved → boundary finding.
3. **Heuristics** when docs are silent (see below).
4. **Repo override** — `.cursor/skills/pr-review/architecture-lens.md` with `## Layers`,
   `## Forbidden edges`, `## Package ownership`.

Violations of documented **forbidden edges** → **High** by default.

### Heuristics (when no documented rule)

Common cross-layer smells — use Medium unless the team override says otherwise:

- Presentation/UI (`components/`, `views/`, `pages/`, `handlers/` at edge) → persistence (`db/`,
  `repositories/`, `models/`, `dao/`)
- Public API package → another package's `internal/`, `_private`, or `impl/`
- Domain/service layer → HTTP client, framework router, or ORM details directly
- Cross top-level domain packages without an established integration point (facade, event, shared kernel)

## Eight concerns

### 1. Coupling (`arch · coupling`)

New direct dependencies between modules that should stay independent; bypassing an existing facade,
port, or adapter.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Convenience import skipping an established adapter |
| Hard | High | Core domain depends on infra/UI; payment flow imports billing internals |

### 2. Boundary violations (`arch · boundary`)

Imports or calls crossing documented layer edges or forbidden edges in the repo override.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Heuristic cross-layer import, no documented rule |
| Hard | High | Explicit forbidden edge violated; required CODEOWNER not approved |

### 3. Cyclic dependencies (`arch · cycle`)

New import edge that completes a cycle. When a new import is added, read the target file's imports
(Phase 1 local context) to detect A→B→…→A.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Cycle within one feature package |
| Hard | High | Cycle across top-level domains |

### 4. Hidden shared state (`arch · shared-state`)

Module-level mutable state, singleton registries, process-wide caches, static/class variables holding
request-scoped data.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low/Medium | Module cache without TTL/eviction notes |
| Hard | High | Request/user data on global/singleton; mutable static across workers |

Overlaps §7 concurrency — §16 frames *design* harm; §7 frames runtime correctness. Prefer one finding
on the changed line; mention both angles if warranted.

### 5. Domain leakage (`arch · domain-leakage`)

Persistence models, ORM entities, or internal DTOs at API/UI boundaries; business rules in
presentation; cross-domain entity refs without anti-corruption layer.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Medium | Internal struct returned where a view-model exists |
| Hard | High | DB model serialized directly to public API response |

### 6. Feature flag debt (`arch · flag-debt`)

New flags without removal plan; permanent behavior behind flags; nested flag spaghetti; unsafe defaults.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low | New flag, no cleanup note or ticket |
| Medium | Medium | Flag wraps core logic on prod path, no sunset |
| Hard | High | Flag default enables unsafe prod behavior |

### 7. Tech debt introduced (`arch · tech-debt`)

Architectural shortcuts that compound — duplicated abstraction, divergent pattern across 3+ files,
workaround instead of fixing root cause. Does **not** duplicate §12 hygiene TODOs; frame compounding
design cost.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low | Small duplication with tracked TODO |
| Hard | Medium | New divergent pattern across 3+ files without justification |
| Regulated path | High | Debt in payments/auth — bump per `domain-overrides.md` |

### 8. Testability reduced (`arch · testability`)

Hard dependencies without injection seam; logic in untestable locations; critical branch requiring
full stack to test.

| Tier | Severity | Example |
|------|----------|---------|
| Light | Low | New static call where an interface exists nearby |
| Hard | Medium | Core logic moved into route closure with no extraction |
| Hard | High | Critical untestable branch + no tests in diff (escalate with §8) |

## Severity summary

- **Hard violation** → High (Critical only if combined with security/data-loss per existing rubric).
- **Light / heuristic** → Medium or Low.
- Architecture **High** participates in the existing blocking gate. Medium/Low do not block alone.

## Comment template

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

When a finding cites a forbidden edge, quote the rule from the override in the comment body.

Phase 5 **Architectural summary** (`reference/architectural-summary.md`) rates Overall design,
Maintainability, Complexity, Readability, and Future cost — informed by §16 findings and holistic judgment.
