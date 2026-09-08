# Repository review rules (`review-rules.yaml`)

Teams customize review focus without editing the skill. **Prefer `review-rules.yaml` over prose docs**
when defining domain paths and keywords — it is machine-readable and loaded automatically.

## Discovery (first match wins)

Search the **repo under review** in order:

1. `.cursor/skills/pr-review/review-rules.yaml`
2. `review-rules.yaml` (repository root)
3. `.gitlab/review-rules.yaml`

If none exist, fall back to `ARCHITECTURE.md`, `docs/architecture/`, and
`.cursor/skills/pr-review/domain-overrides.md` / `architecture-lens.md` as today.

Load in **Phase 1 step 7** (local context). Pass matched domains to Phase 2.

## Schema

```yaml
# Optional metadata
version: 1

# Optional default review persona (see reference/review-personas.md)
# persona: payments_sme   # principal_engineer | sre | security | architect | performance | payments_sme

# Domain blocks — key = domain name (payments, search, infra, …)
payments:
  critical:
    - ledger
    - money
    - idempotency
  high:
    - webhook
    - refund

search:
  - latency          # shorthand: bare list = critical-tier patterns

infra:
  - terraform

# Optional global knobs (all optional)
stop_search:
  critical: 2
  high: 5
  total: 10

fast_path:
  skip_architecture_below_files: 5
  skip_ci_on_docs: true

# Optional — beat fast-path skips for these dimensions (see reference/precedence.md)
always_review:
  - observability    # §9 — runs even when fast_path.skip_observability
  - performance      # §4
  - security         # §2 rubric (non-negotiable baseline still always runs)

# Optional path context for adaptive severity (see reference/contextual-severity.md)
context:
  production_critical:
    - checkout
    - payment
  internal:
    - admin
    - dashboard

architecture:
  layers:             # optional; complements ARCHITECTURE.md
    - name: api
      paths: ["api/", "handlers/"]
    - name: domain
      paths: ["internal/domain/"]
  forbidden_edges:    # optional §16 hints
    - from: api
      to: domain
      except: ["domain/service"]
```

### Domain block shapes

| Shape | Meaning |
|-------|---------|
| **List** (e.g. `search: [latency]`) | Patterns at **critical** tier |
| **Object with `critical` / `high` / `medium`** | Explicit severity tiers per domain |
| **String** (single pattern) | Shorthand for one critical pattern |

### Pattern matching

- **Case-insensitive substring** on changed file path (`new_path` from the diff).
- Also match against **changed hunk text** when the path alone is ambiguous (e.g. pattern `idempotency`
  in a generic `handler.go`).
- Optional glob: leading/trailing `*` — `**/payments/**`, `*.tf` — treat `*` as glob segment when obvious;
  otherwise substring match is enough for v1.

A file can match **multiple domains** — apply the **highest** tier among matches.

## Phase 2 application

When a changed path or hunk matches a domain pattern, set **path context** for adaptive severity
(`reference/contextual-severity.md`) and apply domain hints:

| Domain tier | Path context | Severity effect |
|-------------|--------------|-----------------|
| **critical** | production-critical | Observability/test/perf gaps → **High** band; §8 + security mandatory |
| **high** | elevated | Same issue types → **Medium** default unless hard floor |
| **medium** | standard | Baseline matrix |
| **`context.internal` match** | internal | Observability/style → **Low** / omit |

Do **not** apply a flat "+1 notch" on top of contextual severity — context tier **is** the primary adjustment.

**Domain hints** (when patterns match, prioritize checklist rows):

| Domain keywords (examples) | Extra scrutiny |
|----------------------------|----------------|
| ledger, money, refund, settlement | Decimal/money types, double-entry, idempotency, audit trail |
| idempotency, webhook | Idempotency keys, replay safety, signature verification |
| latency, search, index | Query plans, N+1, cache, timeout, pagination limits |
| terraform, infra, k8s, helm | State drift, blast radius, secrets in TF, rollback |

Print a one-line header when rules loaded:

> **Repo review rules:** `review-rules.yaml` — domains active: payments (critical), search (critical), infra (critical)

List matched domains and tiers in the Phase 4 summary **Notes** section:
`- Repo rules: payments (critical: ledger, money, idempotency); search (latency)`

### Interaction with other overrides

| Source | Relationship |
|--------|----------------|
| `reference/domain-overrides.md` | Default fintech bar when **no** `review-rules.yaml`; when YAML exists, **YAML wins** for matching paths |
| `ARCHITECTURE.md` | Still read for §16 boundaries; YAML `architecture:` block merges/overrides layer lists when present |
| `.cursor/skills/pr-review/architecture-lens.md` | Prose override; YAML `architecture.forbidden_edges` supplements it |
| `review-feedback-learning.md` | Independent — category ignore rules still apply |
| `reference/fast-path.md` | Classify MR after boundary; optional `fast_path:` overrides in YAML |

### Optional `stop_search` in YAML

When present, override skill defaults for this repo only (same semantics as `workflow/phase-2.md` §Stop searching).

## Authoring tips

- Start with **critical** only — add `high` when the team wants finer control.
- Use path fragments teams already say aloud (`ledger`, `terraform`) not full package paths unless needed.
- Keep **< 10 domains**; merge related areas.
- Commit at repo root or `.cursor/skills/pr-review/` so every MR inherits it.

See `examples/review-rules.yaml` for a copy-paste starter.
