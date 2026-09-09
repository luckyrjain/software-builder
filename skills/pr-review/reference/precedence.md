# Precedence rules (conflict resolution)

When modules disagree (fast path vs repo rules, persona vs non-negotiable, feedback learning vs
security), apply **the highest-precedence source that applies**. Load when Phase 1 or Phase 2 sets
conflicting flags.

## Stack (highest wins)

| Rank | Source | Examples |
|------|--------|----------|
| **1** | **Explicit user request** | *full review*, *exhaustive*, *no fast path*, *refresh context*, *as Security*, *architecture focus* |
| **2** | **Repository `review-rules.yaml`** | `persona:`, domain tiers, `stop_search`, `always_review: [performance]` |
| **3** | **Active workflow phase + `fast_path` flags** | Phase 1 classification; step contracts in `workflow/*.md` |
| **4** | **Reference defaults** | `SKILL.md` §Review principle, `finding-gates.md` §Non-negotiable, pipeline order |

Lower ranks **never override** higher ranks. When rank 2 and 3 conflict, **rank 2 wins**.

## Common conflicts

| Conflict | Resolution |
|----------|------------|
| Fast path `skip_observability` vs repo rule `always_review: observability` | **Repo rules win** — run §9 on production paths unless user said *no fast path* / *full review* |
| Fast path `skip_security_checklist` vs non-negotiable secret scan | **Non-negotiable wins** — always scan changed lines for secrets (rank 4 baseline) |
| Persona *Architect* skip §2 vs Security-critical path in diff | **Non-negotiable + §2 on that hunk** — persona narrows emphasis, not baseline |
| Feedback learning `ignored_categories: observability` vs new prod payment path | **Emit** — materially worse or non-negotiable path beats ignore signal |
| `stop_search` threshold vs secret on current hunk | **Finish current hunk** including non-negotiable; then stop |
| User *migrations only* vs repo `persona: sre` | **User focus wins** (rank 1) for scope; non-negotiable still applies on reviewed hunks |

## Fast path vs repo rules (explicit)

```text
User "full review"     → disable all fast_path skips (rank 1)
Repo always_review     → run that dimension even if fast_path would skip (rank 2 > 3)
Default fast_path      → skip expensive dimensions when profile matches (rank 3)
Non-negotiable list    → always run regardless of fast_path (rank 4, cannot be skipped)
```

## Workflow contracts

Each `workflow/*.md` file declares `produces` / `consumes`. A phase **must not** assume artifacts a
prior phase did not produce at its declared `workflow_version`. See front matter on workflow files.

## When uncertain

Prefer **stricter review** (run the check) for security, auth, and money paths. Prefer **omit** over
speculative emit for Medium/Low when precedence is ambiguous and no non-negotiable match.
