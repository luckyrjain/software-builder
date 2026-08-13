# Universal Skill Runtime Contract

**Normative.** Every registered skill inherits this contract through `skill-routing.md`. A skill may add stricter domain rules, but must not weaken these defaults. Keep provider- or host-specific mechanics in adapters; keep skill logic capability-oriented.

## 1. Input resolution

Resolve inputs in this order:

1. Facts explicitly supplied by the caller.
2. Authoritative context that the active host can retrieve safely.
3. Safe, reversible defaults that do not materially change the outcome.
4. One focused question only when different answers would materially change execution.

Never ask for information already supplied or safely retrievable. Optional missing context must degrade the result rather than block unrelated work.

## 2. Source precedence

When sources conflict, use this default precedence unless a skill documents a domain-specific override:

1. Runtime or authoritative system state.
2. Executable code, configuration, schemas, and machine contracts.
3. Tests and executable examples.
4. Version-controlled technical documentation.
5. Tickets and design documents.
6. Human prose, comments, and informal notes.

Do not silently discard lower-precedence evidence. Preserve the conflict and explain the precedence decision.

## 3. Freshness and provenance

External observations must record, when the source exposes them:

- `observed_at`
- `source_revision`
- `source_environment`

Repository evidence must record, when known:

- `repo`
- `branch`
- `commit_sha`

A result that relies on evidence whose relevant revision or observation time is unknown must lower confidence or mark the affected claim `UNKNOWN`.

## 4. Evidence conflicts

Use the portable evidence states from `platform_contracts.yaml`:

- `OBSERVED`
- `INFERRED`
- `UNKNOWN`
- `CONFLICTED`
- `NOT_APPLICABLE`

When authoritative sources materially disagree, use `CONFLICTED`; state both claims, the precedence rule, the selected interpretation if one is defensible, and the limitation. Never convert disagreement into false certainty.

## 5. Stopping conditions

Every invocation ends in exactly one portable completion status:

- `SUCCESS` — requested outcome completed and required checks passed.
- `PARTIAL` — useful bounded work completed, but optional or non-blocking evidence is unavailable.
- `BLOCKED` — a required capability, permission, input, or invariant is unavailable.
- `FAILED` — execution attempted but did not produce a valid result.
- `ESCALATED` — another skill or accountable human must take the next primary action.

A skill must not report `SUCCESS` when a required verification step is missing.

## 6. Result envelope

Machine-consumable skill results use:

```yaml
skill_result:
  skill: <registered skill id>
  version: <normalized semantic version>
  status: SUCCESS|PARTIAL|BLOCKED|FAILED|ESCALATED
  confidence: HIGH|MEDIUM|LOW|UNKNOWN
  source_revision: <revision or null>
  evidence_status: OBSERVED|INFERRED|UNKNOWN|CONFLICTED|NOT_APPLICABLE
  artifacts: []
  blockers: []
  recommended_next_skill: <registered skill id or null>
```

Human-readable reports may render this differently, but must preserve the semantics. Internal phase names, lens names, or implementation-only control markers should not leak into user-facing output unless they help the user act.

## 7. Handoff envelope

Cross-skill handoffs use:

```yaml
handoff:
  target_skill: <registered skill id>
  reason: <why ownership is changing>
  inputs: {}
  evidence_refs: []
  assumptions: []
  unresolved: []
```

The receiving skill treats the handoff as context, not as higher authority than the caller or framework contracts.

## 8. Recursion protection

Orchestrators, routers, and triggers carry:

```yaml
execution_context:
  invocation_id: <stable id>
  parent_skill: <skill id or null>
  visited_skills: []
  depth: 0
```

Default maximum handoff depth is **3**. A skill must block or return control to the parent when the next handoff would revisit a skill already in `visited_skills` or exceed the maximum depth, unless a named orchestrator contract explicitly permits the cycle.

## 9. Artifact ownership and state semantics

The producer declared in `composition_contracts.yaml` owns the canonical artifact. Consumers may read, cite, or derive a new artifact; they must not silently rewrite another skill's canonical artifact.

Durable artifacts declare one state semantic:

- `current_state`
- `proposed_state`
- `desired_state`
- `transitional_state`

Current-state evidence must not be represented as a future-state recommendation, and proposed state must not be described as already deployed.

## 10. Concise completion

User-facing completion answers should make four things clear without exposing internal control flow: what was done, what evidence supports it, what remains or is blocked, and what the next action is.