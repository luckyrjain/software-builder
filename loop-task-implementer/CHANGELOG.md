# loop-task-implementer changelog

For earlier history, see the `## loop-task-implementer` section in the repository root `CHANGELOG.md`.

## v1.2 — post-merge Batch 5.2C lifecycle hardening (2026-08-21)

- Made `scripts/validate_loop_lifecycle.py` an actual fail-closed CLI. The documented `python ... --state <state.json>` lifecycle gate now reads official JSON state and exits `0` only on a valid state, `1` on lifecycle errors, and `2` when input/runtime validation cannot be performed; the previous function-only script could be executed directly and silently exit `0` without validating anything.
- Bound third-party branch-change evidence to the exact current head with `workspace.third_party_change_checked_head`, and changed the default detection state from `false` to `null` so unrefreshed state cannot masquerade as a clean branch check.
- Bound degraded-isolation human exceptions to the exact `reviewed_change_identity`; stale authorization from an earlier review identity no longer carries forward after evidence is invalidated or rerun.
- Aligned `reference/phase-index.md` with the canonical `SKILL.md` review/remediation order and made the mandatory lifecycle overlay explicitly authoritative wherever legacy readiness/completion text conflicts with it.
- Corrected the completion-report template so human-entered isolation-exception provenance is rendered as escaped/redacted free text rather than inline code, matching the shared safe-output contract.
- Added regression coverage for the CLI exit contract, stale/missing third-party check heads, isolation-exception identity binding, canonical review ordering, and safe provenance rendering. `reference/state-schema.yaml` workflow version is now `1.4`; skill version is `1.2`.
