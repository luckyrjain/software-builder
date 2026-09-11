# Candidate ledger (normative)

Session-level state this skill owns. It extends, never modifies, the artifacts each composed skill already
produces (`codebase_architecture_report` candidates, `engineering_decision_record` resolutions,
`module_design_spec`, loop-task-implementer's own per-task state) — this file is the schema that stitches
them into one traceable row per candidate across cycles.

## Schema

```yaml
candidate_ledger:
  - candidate_id: "<this ledger's own ID, assigned on first open — never assumed stable
      against codebase-architecture-review's own local identifier across separate
      invocations; dedup matches on scope + root cause instead, see workflow/discover.md § 4>"
    cycle_discovered: <int>
    scope: "<bounded paths/subsystem>"
    strength: Strong | Worth exploring | Speculative
    evidence_refs: []
    falsification_result: "<from codebase-architecture-review>"
    disposition: null | ACCEPT | ACCEPT_WITH_MODIFICATION | ALREADY_SATISFIED | DUPLICATE | REJECT | OUT_OF_SCOPE
    disposition_evidence: "<required once disposition is set>"
    modification: null | "<what changed vs. the original candidate, when ACCEPT_WITH_MODIFICATION>"
    needs_design: false
    module_design_spec_ref: null
    batch_id: null
    batch_attempt_count: 0   # incremented each loop-task-implementer dispatch for this batch; see
                             # reference/pr-batching-policy.md and SKILL.md § Circuit breakers
    pull_request_url: null
    merge_confirmed: false   # set true only once Converge's merge checkpoint confirms the PR
                             # landed on the effective base branch — see workflow/converge.md § 1
    pull_request_merge_sha: null
    outcome: PENDING | COMPLETED | BLOCKED
    source: architecture | holistic | regression   # holistic = opened from a Gate B finding;
                                                     # regression = rediscovered after an earlier,
                                                     # merge-confirmed row for the same root cause
    duplicate_of: null      # candidate_id, when disposition == DUPLICATE
    regressed_from: null    # candidate_id, when source == regression
```

Disposition values above are the literal field values (underscore form). Prose elsewhere in this skill
(SKILL.md, README.md, workflow/*.md) spells them with spaces for readability — e.g. "ACCEPT WITH
MODIFICATION" in prose is always `ACCEPT_WITH_MODIFICATION` in the field; never write the spaced form to
the `disposition` field itself.

## Disposition contract

Every candidate receives exactly one terminal disposition before it leaves Disposition:

| Disposition | Meaning | Continues to Remediate? |
|--------------|---------|---------------------------|
| `ACCEPT` | Candidate and proposed remedy are both correct as evidenced | Yes |
| `ACCEPT_WITH_MODIFICATION` | Underlying issue is valid; the stronger root-cause remedy is recorded in `modification` | Yes — implement the modification, not the original text |
| `ALREADY_SATISFIED` | Current repository state already resolves it — evidence required | No |
| `DUPLICATE` | Same root cause as an existing, **not-yet-merge-confirmed** row — `duplicate_of` set; a match against an already merge-confirmed row is `source: regression` instead, never `DUPLICATE` (see workflow/discover.md § 4) | No |
| `REJECT` | Incorrect, harmful, obsolete, or unjustified — evidence required | No |
| `OUT_OF_SCOPE` | Real issue requiring genuinely external work — used sparingly | No |

No candidate may silently disappear from the ledger: every row keeps its disposition and evidence even
after the cycle that produced it ends.

## Anti-gaming

A `Speculative` candidate is never downgraded to `REJECT`/`ALREADY_SATISFIED` solely to reach a zero count
— [reference/convergence-gates.md § Anti-gaming](convergence-gates.md#anti-gaming) is the binding rule; this
ledger only records the outcome, it never supplies the justification.
