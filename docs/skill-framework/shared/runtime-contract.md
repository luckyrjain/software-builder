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

Use the portable evidence states from the canonical manifest's
`contracts.platform` section in `skills.yaml`, which is the only place they are declared.

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

Machine-consumable durable artifact results use the canonical manifest-backed envelope:

```yaml
skill_result:
  skill: <registered skill id>
  version: <exact semantic version registered for the skill>
  status: SUCCESS|PARTIAL|BLOCKED|FAILED|ESCALATED
  confidence: HIGH|MEDIUM|LOW|UNKNOWN
  source_revision: <revision, UNKNOWN, or null>
  evidence_status: OBSERVED|INFERRED|UNKNOWN|CONFLICTED|NOT_APPLICABLE
  artifacts: [<known artifact ids>]
  blockers: []
  recommended_next_skill: <registered skill id or null>
  artifact_schema_version: <version declared for the artifact>
  state_semantic: current_state|proposed_state|desired_state|transitional_state
provenance:
  source_revision: <revision, UNKNOWN, or null>
  sources: []
freshness:
  observed_at: <ISO-8601 timestamp, UNKNOWN, or null>
  source_revision: <revision, UNKNOWN, or null>
  source_environment: <environment, UNKNOWN, or null>
definition_of_done:
  required_artifacts: []
  required_checks: []
  completed_checks: []
  blocked_conditions: []
  partial_result_behavior: <bounded fallback behavior>
authority:
  write_authority: <declared composition authority>
  canonical_owner: <declared artifact owner>
payload: <producer-declared artifact-schema fields>
```

### Artifact-v2 machine summaries

An artifact schema that declares the common v2 fields uses this typed payload shape in
addition to its artifact-specific fields:

```yaml
payload:
  assessment_target: {}
  normalized_decision:
    status: PASS|CONDITIONAL|FAIL|UNKNOWN|NOT_APPLICABLE
    raw_verdict: <non-empty string>
  findings:
    - id: <stable non-empty id>
      category: <non-empty category>
      summary: <non-empty summary>
      blocking: true|false
      evidence_status: OBSERVED|INFERRED|UNKNOWN|CONFLICTED|NOT_APPLICABLE
      evidence_refs: [<source ref>]
  conditions:
    - id: <stable non-empty id>
      summary: <non-empty summary>
      required_before: IMPLEMENTATION|MERGE|DEPLOY|FOLLOW_UP
      evidence_refs: [<source ref>]
  required_actions:
    - id: <stable non-empty id>
      summary: <non-empty summary>
      required_before: IMPLEMENTATION|MERGE|DEPLOY|FOLLOW_UP
      verification: <non-empty verification>
      evidence_refs: [<source ref>]
  evidence_refs: [<de-duplicated source ref>]
provenance:
  source_revision: <revision, UNKNOWN, or null>
  sources:
    - ref: <source ref>
      authority: authoritative_host|repository|trusted_runtime|caller|model_knowledge
      kind: scm|repo_content|ci|runtime_metric|service_metadata|build_provenance|artifact|caller_input|model_knowledge
      observed_at: <ISO-8601 timestamp, UNKNOWN, or null>
      source_revision: <revision, UNKNOWN, or null>
      source_environment: <environment, UNKNOWN, or null>
      derived_from: [<source ref>]
```

Each item family has unique IDs and exact item keys. Nested evidence references must
be covered by the root `evidence_refs`; that root is a de-duplicated superset and each
of its values resolves to exactly one typed `provenance.sources` item. A `PASS`,
`CONDITIONAL`, or `FAIL` decision always requires at least one root reference. Derived
sources retain the authorities of their ultimate sources; `derived_from` references
must resolve and must not form cycles.

**The rule the agent applies.** Before emitting or consuming a durable result, check the
envelope itself: every required field present, every item family's IDs unique, the root
`evidence_refs` a de-duplicated superset of every nested reference, each of its values
resolving to exactly one typed `provenance.sources` item, no `derived_from` cycle, and at
least one root reference behind any `PASS`/`CONDITIONAL`/`FAIL` decision. An envelope that
fails any of these is not usable evidence — report the gap rather than proceeding on it.

The producer identity in the envelope is **caller context, not an attestation**. A host that
needs authenticated producer identity must inject it from its trusted execution context; a
document that names its own producer does not thereby authenticate it. Producer minor/patch
versions remain readable within the same major version, while the explicit artifact schema
version controls payload compatibility.

*Optional verification, when working from a Software Builder checkout:*

```bash
python3 -m scripts.registry validate-artifact <artifact_type> <result.json> --producer-skill <trusted_skill_id>
```

This CLI ships only with the repository, not inside an installed skill package. It is a
convenience for authors and CI — the obligation above is the agent's own, and applies
identically where the command cannot be run.

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

Default maximum handoff depth is **3** (`recursion_guard.default_max_depth`).

**The rule the agent applies**, before every handoff, from the `execution_context` it was given:

1. If `depth` is already at the maximum, the handoff is **blocked** — do not perform it.
2. If `target_skill` already appears in `visited_skills`, the handoff is **blocked** — a revisit is
   refused by default.
3. Otherwise perform the handoff, passing `depth + 1` and `visited_skills` extended with the current
   skill.

A named orchestrator contract may explicitly permit a cycle; nothing else may. When a handoff is
blocked, say which rule blocked it and return control to the parent rather than continuing with a
degraded substitute.

*Optional verification, when working from a Software Builder checkout:*

```bash
python3 -m scripts.registry.cli check-handoff <target_skill> --depth <execution_context.depth> --visited <comma-separated execution_context.visited_skills>
```

A non-zero exit means the handoff is blocked. This CLI ships only with the repository, not inside an
installed skill package — the rule above is what an agent is obliged to apply, with or without it.

## 9. Artifact ownership and state semantics

The producer declared in the canonical manifest's `contracts.composition` section owns the
canonical artifact. Consumers may read, cite, or derive a new artifact; they must not silently
rewrite another skill's canonical artifact. `scripts/registry/composition_contracts.yaml` is the
generated projection of that ownership data.

Durable artifacts have one default state semantic and may declare a finite allowed set; each individual result still emits exactly one semantic:

- `current_state`
- `proposed_state`
- `desired_state`
- `transitional_state`

Current-state evidence must not be represented as a future-state recommendation, and proposed state must not be described as already deployed.

## 10. Concise completion

User-facing completion answers should make four things clear without exposing internal control flow: what was done, what evidence supports it, what remains or is blocked, and what the next action is.

## 11. Action authorization gates

Every action a skill takes falls into exactly one `action_gates` tier from the canonical
manifest's `contracts.platform` section, which sets the minimum authorization the action
requires (a skill may always require more, never less):

| Tier | Examples | Minimum authorization |
|------|----------|------------------------|
| `read_only` | Reading files, querying metrics, listing PRs | none |
| `local_reversible_write` | Writing a local branch, a scratch file | explicit task authorization |
| `remote_non_destructive_write` | Posting a PR comment, creating an issue | explicit task authorization |
| `destructive_or_high_impact` | Merge, deploy, delete, rollback | explicit action authorization |

Classify each action a skill can take against this table instead of inventing skill-local confirmation language.

## 12. Definition of Done

Every skill declares, for its own output, the `definition_of_done` fields from the canonical
manifest's `contracts.platform` section:

- `required_artifacts` — what must exist for the result to count as complete.
- `required_checks` — what must have been verified (tests, validators, re-reads).
- `completed_checks` — the checks actually completed for this result; `SUCCESS` requires all required checks.
- `blocked_conditions` — the specific states that force a `BLOCKED` status instead of `SUCCESS`/`PARTIAL`.
- `partial_result_behavior` — what a skill reports and preserves when only some of its work could complete.

A skill may define these once, narrowly, in its own words; it must not leave "done" implicit.
