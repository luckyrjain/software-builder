# Operational gates — the four operational dimensions, normative

These four dimensions are evaluated in Aggregate for every assessment, independent of which specialists
Dispatch invoked — they are about the change's operational readiness, not its code correctness.

## The four dimensions

| Dimension | What it evidences |
|---|---|
| **Ownership** | Someone is actually on the hook for this service/change post-deploy — an on-call rotation, a named owner, an escalation path |
| **Rollback / abort** | A concrete, verified way to stop or reverse this change if it goes wrong — a revert path, a feature flag, a migration-down script |
| **Post-deploy verification plan** | A defined way to confirm the change worked after it ships — a health check, a dashboard, a canary/synthetic check |
| **Recovery** | If the change is destructive or hard to reverse (a data migration, a deletion), a proven path back to a good state exists |

In the report and in code these four are the dimension identifiers `operational_ownership`,
`rollback_and_abort`, `post_deploy_verification_plan`, and `recovery`. All four are
environment-sensitive: evidence collected for one environment (e.g. a staging on-call rotation)
must not silently stand in for another (e.g. production) — a declared-environment conflict between
the candidate and the evidence downgrades the dimension to `UNKNOWN`, never `PASS`. This is not
limited to an explicit conflict: if either side (the candidate or the gate's own evidence) doesn't
declare an environment at all, that is never itself grounds to treat the two as matching — never
assume they agree just because no conflicting field was supplied. The same rule applies to every
`ENV_SENSITIVE_DIMENSIONS` member, not just these four; see
[child-input-map.md § Environment-sensitive specialists](child-input-map.md#environment-sensitive-specialists)
for the three dispatched-specialist dimensions it also covers.

Every completeness/affirmative flag these gates read (`complete`, `reversible`, and the
sibling gates' `required`/`scope_covers_changed_manifest`/`bypass_approved`/`codeowners_satisfied`)
is read as a strict boolean: only the literal `true` counts as an affirmative signal. A truthy
non-boolean value (a string like `"false"`, a nonzero count) is never treated as confirming
anything — it degrades the same way an absent field does, never the way a confirmed `true` does.

## Tier-sensitive rules

Apply `criticality` (`tier0`/`tier1`/`tier2`/`tier3`/`unknown`, resolved in Inputs) to every one of the
four dimensions independently:

| Criticality | Caller-only evidence | Authoritative evidence |
|---|---|---|
| `tier0`, `tier1`, `unknown` | `UNKNOWN` — never `PASS`. A caller's own assertion of ownership/rollback/verification/recovery is not sufficient at this stakes level | `PASS` when the evidence affirmatively confirms the dimension; `FAIL` on an affirmative negative finding (below), for ownership/rollback-abort/recovery only — see the note below |
| `tier2`, `tier3` | At most `CONDITIONAL` — never `PASS`. Lower stakes still don't let an unverified caller assertion stand in for evidence, but it also doesn't sink the whole assessment to `UNKNOWN` on its own | `PASS` when the evidence affirmatively confirms the dimension; `FAIL` on an affirmative negative finding (below), for ownership/rollback-abort/recovery only — see the note below |

**Post-deploy verification plan has no `FAIL` path.** Unlike the other three, no
authoritative-negative-finding rule is defined for this dimension (per
[report-format.md](report-format.md)'s fixed report schema) — its ceiling at any tier is `PASS`, its
floor `CONDITIONAL`/`UNKNOWN`. Even an authoritative finding of "this service has no post-deploy
verification of any kind" is `UNKNOWN`/`CONDITIONAL` per the table above, never `FAIL`.

`unknown` criticality is treated as strictly as `tier0`/`tier1`, never as a permissive default — an
unresolved criticality tier is not grounds for relaxing the operational bar.

## Authoritative negative findings are FAIL at any tier

Regardless of criticality tier, an **authoritative** (not caller-only) finding of either of the
following is `FAIL`, not `UNKNOWN` or `CONDITIONAL`:

- **Unowned** — `host.service.metadata.read` (or equivalent authoritative evidence) affirmatively shows
  no on-call owner, no escalation path, or an expired/invalid ownership record for the affected
  service.
- **Proven destructive without recovery** — the change is confirmed (via repository content or an
  authoritative host signal) to perform a destructive or hard-to-reverse operation (e.g. an
  irreversible data deletion, a non-additive schema change with no down-migration), and no recovery
  path is evidenced.
- **Unsafe/irreversible rollback plan** — the rollback/abort plan itself is confirmed unsafe or
  irreversible with no recovery path (e.g. the "rollback" is itself a destructive operation with no
  way back), the same any-tier-FAIL escape hatch as the two findings above, scoped to the
  rollback/abort dimension.

A `FAIL` on any operational dimension is a required dimension `FAIL` for the purposes of the overall
verdict precedence in [gate-policy.md § Verdict precedence](gate-policy.md#verdict-precedence).

## Recovery's `NOT_APPLICABLE` outcome

Recovery is the one operational dimension that can be `NOT_APPLICABLE`, retiring it from the
required set entirely: this is reachable only when authoritative evidence *affirmatively confirms*
the change is non-stateful (an explicit, confirmed `false` — never merely absent or unassessed) and
reversible. A caller-only assertion of either is never enough to reach `NOT_APPLICABLE`; it falls
through to the ordinary completeness/tier ladder above instead, the same as any other caller-only
claim. A change that IS stateful, or whose statefulness was simply never determined, must never take
this shortcut — recovery stays required and is evaluated normally.

## Evidence sourcing

Ownership and recovery-policy evidence come primarily from `host.service.metadata.read`. Rollback/abort
and post-deploy-verification evidence come from the diff/repository (a documented rollback script, a
feature-flag gate, a health-check config) or from `deployment_risk_evidence`'s own Rollback complexity
and Migration risk sections, reused rather than re-derived. Never accept a specialist's or the caller's
prose summary of these as authoritative on its own — trace it back to the underlying source per
[evidence-authority-policy.md](evidence-authority-policy.md).
