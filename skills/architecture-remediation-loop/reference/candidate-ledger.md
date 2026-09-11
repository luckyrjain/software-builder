# Candidate ledger (normative)

Session-level state this skill owns. It extends, never modifies, the artifacts each composed skill already
produces (`codebase_architecture_report` candidates, `engineering_decision_record` resolutions,
`module_design_spec`, loop-task-implementer's own per-task state) — this file is the schema that stitches
them into one traceable row per candidate across cycles.

## Schema

```yaml
candidate_ledger:
  - candidate_id: "<from codebase_architecture_report, stable across cycles>"
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
    pull_request_url: null
    outcome: PENDING | COMPLETED | BLOCKED
    source: architecture | holistic   # holistic = opened from a Gate B finding, not a Discover cycle
    duplicate_of: null   # candidate_id, when disposition == DUPLICATE
```

## Disposition contract

Every candidate receives exactly one terminal disposition before it leaves Disposition:

| Disposition | Meaning | Continues to Remediate? |
|--------------|---------|---------------------------|
| `ACCEPT` | Candidate and proposed remedy are both correct as evidenced | Yes |
| `ACCEPT_WITH_MODIFICATION` | Underlying issue is valid; the stronger root-cause remedy is recorded in `modification` | Yes — implement the modification, not the original text |
| `ALREADY_SATISFIED` | Current repository state already resolves it — evidence required | No |
| `DUPLICATE` | Same root cause as an existing non-terminal-rejected row — `duplicate_of` set | No |
| `REJECT` | Incorrect, harmful, obsolete, or unjustified — evidence required | No |
| `OUT_OF_SCOPE` | Real issue requiring genuinely external work — used sparingly | No |

No candidate may silently disappear from the ledger: every row keeps its disposition and evidence even
after the cycle that produced it ends.

## Anti-gaming

A `Speculative` candidate is never downgraded to `REJECT`/`ALREADY_SATISFIED` solely to reach a zero count
— [reference/convergence-gates.md § Anti-gaming](convergence-gates.md#anti-gaming) is the binding rule; this
ledger only records the outcome, it never supplies the justification.
