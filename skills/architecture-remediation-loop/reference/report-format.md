# `architecture_remediation_report` format

Emitted by Converge (see [workflow/converge.md](../workflow/converge.md)) whether or not the loop actually
converged.

```yaml
architecture_remediation_report:
  review_scope: "<as supplied>"
  converged: true | false
  cycles_run: <int>
  gate_a_status: PASS | FAIL
  gate_b_status: PASS | FAIL | UNKNOWN
  stopped_reason: null | AWAITING_MERGE | NO_MATERIAL_PROGRESS | MAX_CYCLES_REACHED
    | MAX_CANDIDATES_REACHED | CONTESTED_DISPOSITION | REPEATED_BATCH_ESCALATION
    | SCOPE_EXCEEDS_AUTHORIZATION
  merge_attempted: false   # invariant — this skill never merges; always false, every report
  candidates:
    total: <int>
    by_disposition:
      ACCEPT: <int>
      ACCEPT_WITH_MODIFICATION: <int>
      ALREADY_SATISFIED: <int>
      DUPLICATE: <int>
      REJECT: <int>
      OUT_OF_SCOPE: <int>
    open: <int>   # disposition still null — only nonzero when stopped_reason is set
    regressions: <int>   # rows with source: regression this run — a merge-confirmed fix rediscovered by
                          # a later Discover pass; visible here even once the regression row itself
                          # closes REJECT/ALREADY_SATISFIED, so it's never silently indistinguishable
                          # from an unrelated first-time candidate at the summary level
  batches:
    - batch_id: "<id>"
      candidate_ids: []
      classification: dedicated | grouped
      pull_request_url: "<url>"
      merged: true | false
      pull_request_merge_sha: "<sha>" | null
      outcome: COMPLETED | BLOCKED
  ledger_ref: "<full candidate ledger, per reference/candidate-ledger.md>"
```

## Safe rendered-output boundary

Candidate scope strings, evidence excerpts, and loop-task-implementer's own escalation-report text are
repository- or child-skill-supplied and render only escaped/fenced per
[safe-output.md](../../../docs/skill-framework/shared/safe-output.md) — never as live links, executable
snippets, or instructions to a downstream tool.

## Rendering rules

- `converged: true` requires `gate_a_status: PASS` **and** `gate_b_status: PASS` **and**
  `candidates.open == 0` in the same reported cycle — never partial credit. `gate_b_status: UNKNOWN` is
  never treated as `PASS`.
- `stopped_reason` is set if and only if `converged: false`.
- Every batch row's `pull_request_url` is present for `outcome: COMPLETED`; `BLOCKED` rows instead carry
  the loop-task-implementer escalation reference in the full ledger. `merged: true` only once Converge's
  merge checkpoint (workflow/converge.md § 1) confirms it directly against the PR's own status — never from
  PR title/description text.
- `merge_attempted` stays `false` in every report this skill ever emits — asserted as a literal invariant,
  not derived per-run, since this skill has no code path that ever sets `autonomous_merge_authorized: true`.
