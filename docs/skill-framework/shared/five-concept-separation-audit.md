# Five-concept separation audit

Tracked from issue #53 (originally #20's roadmap). A repo-wide pass confirming five concepts are
not conflated in any skill — a skill answering "what's my recommendation" should never be the same
code path as "am I allowed to act on it" or "did I actually act."

## The five concepts

| Code | Concept | Question it answers | Anti-pattern if conflated |
|------|---------|----------------------|----------------------------|
| **EC** | Evidence completeness | Have I gathered enough evidence to speak with confidence? | Treating "I looked" as "I know" |
| **RV** | Review verdict | What is my judgment/recommendation, given the evidence? | Verdict silently changes when authorization or action state changes |
| **RR** | Repository readiness | Is the *target* (repo, release, service) itself in a ready state? | Confusing "my review is done" with "the thing I reviewed is ready" |
| **EA** | External-action authorization | Am I *permitted* to post/write/merge externally right now? | Treating "verdict is positive" as implicit permission to act |
| **FA** | Final repository action | Did the write/post/merge *actually happen*? | A report claims an action that didn't happen, or omits one that did |

`EA` and `FA` collapse to **N/A** for any skill with `risk_class: [read-only]` in `skills.yaml` —
it never has external write authority to confuse with anything, by construction. `RR` is N/A for
skills that don't evaluate a target's own readiness (pure lookups, generators, aggregators).

## Matrix — all 23 skills

Each cell is either a pointer to where that concept is a *distinct, separately-named* artifact/field
(so it can't silently collapse into another concept), or `N/A` with why.

| Skill | EC | RV | RR | EA | FA |
|-------|----|----|----|----|----|
| **pr-review** | `review_metadata.review_complete` | `review_metadata.recommendation` | N/A (reviews the diff, not repo-wide readiness) | `posting_mode` / draft-MR checks (phase-3) | `posted` field ([composition_contracts.yaml](../../../scripts/registry/composition_contracts.yaml)) |
| **pr-gatekeeper** | delegates to pr-review | delegates to pr-review | N/A | `auto_post_authorized` ([auto-post-policy.md](../../../pr-gatekeeper/reference/auto-post-policy.md)) | "Posted?" column, same doc |
| **k8s-overprovisioning-datadog** | `assessment_metadata` §8.2 evidence fields | recommendation per-workload | N/A (rightsizing, not merge readiness) | N/A (read-only) | N/A |
| **incident-rca** | `assessment_metadata` §8.1; confidence capped when partial ([log-redaction.md](../../../incident-rca/reference/log-redaction.md)) | `root_cause` / conclusion | N/A | N/A (read-only) | N/A |
| **incident-triage-agent** | delegates to incident-rca | delegates to incident-rca | N/A | N/A (drafts only, never posts — delegates any write to incident-rca/squad-map) | N/A |
| **domain-comprehension** | `evidence_summary` counters + `overall_confidence` (manifest schema) | five-questions answers, per-section confidence | `engagement.status: FIRST_PASS_COMPLETE` (distinct from confidence) | N/A (read-only) | N/A |
| **squad-map** | `assessment_metadata` §8.4 | squad assignment + confidence | N/A | N/A (read-only) | N/A |
| **who-owns-x-bot** | delegates to squad-map | delegates to squad-map | N/A | single-shot-reply constraint ([slack-format.md](../../../who-owns-x-bot/reference/slack-format.md)) | implicit in single-shot reply (one message = one action) |
| **new-hire-guide** | delegates to domain-comprehension/squad-map | curated tour, no verdict of its own | N/A | N/A — explicit "none of its own" in Post-actions | N/A |
| **release-readiness-checker** | aggregates pr-review/k8s/incident-rca evidence | explicit `Verdict: READY \| CONDITIONAL \| NOT_READY \| UNKNOWN` field ([report-format.md](../../../release-readiness-checker/reference/report-format.md)) | *is* the readiness verdict (RV and RR are the same field by design here — the skill's whole job is repo readiness) | N/A (read-only) | N/A |
| **migration-program-manager** | `evidence_summary`-equivalent rollup counters | aggregated status per service | N/A (aggregator, no verdict of its own — explicit "nothing to answer: no posting" in SKILL.md) | N/A | N/A |
| **cost-optimization-sprint-planner** | delegates to k8s-overprovisioning-datadog | sprint plan ranking | N/A | N/A — explicit "none of its own" in Post-actions | N/A |
| **mysql-to-postgres-sql** | `assessment_metadata` §8.5 | scan-gate pass/fail | N/A (per-service, not repo-wide) | none granted — PR opening deferred to human/pr-review, never this skill | N/A (never opens a PR itself) |
| **loop-task-implementer** | "verify authoritative checks" pipeline step | Lens A/B adjudication | N/A | explicit `→ complete repository action **when authorized**` pipeline step (SKILL.md) — a distinct, separately-gated step from adjudication | "verify result" step confirms the action after the fact |
| **backlog-runner** | delegates to loop-task-implementer | delegates to loop-task-implementer | N/A | explicit `autonomous_merge_authorized` is never passed as `true` ([queue-policy.md](../../../backlog-runner/reference/queue-policy.md)) | never authorized, so never happens by construction |
| **weekly-squad-digest** | source-revision fingerprints (provenance) | digest content itself | N/A | N/A — explicit "does not post anywhere itself" in SKILL.md | N/A |
| **test-writer** | delegates to dispatch target | delegates to dispatch target | N/A | N/A — router only, no scripts/tests of its own | N/A |
| **unit/integration/contract/e2e/api-test-creator** | `## Targets` table, per-target status | test-quality gate ([gate-policy.md](../../../unit-test-creator/reference/gate-policy.md) per skill) | N/A | **gap found, fixed in this PR** — "write test files only" scope existed but no explicit never-commit/push/PR statement | report says "Ready to open as an MR" (a suggestion, not an action) |
| **prd-architect** | evidence gathered per section | explicit build/no-build verdict (SKILL.md §Validation) | N/A (evaluates a proposal, not a repo) | N/A — "none of its own" in Post-actions | N/A |

## Gap found and fixed

The five `*-test-creator` skills (`risk_class: [repository-write]`) each state "write or modify
test files only" as their scope, but nothing in either their own `skill-contract.md` or the shared
[test-creation-principles.md](test-creation-principles.md) explicitly said they never commit, push,
or open a PR/MR themselves — unlike `backlog-runner` and `pr-gatekeeper`, which state their
authorization boundary explicitly. Added one sentence to `test-creation-principles.md` (shared by
all five, so this fixes it once, not five times) — see that file's diff in this PR.

No other conflation was found: every skill with `risk_class` other than `read-only` already has a
verdict/authorization/action split that's a distinct, separately-named artifact — not something
this audit needed to invent, just confirm.

## See also

[terminology-glossary.md](terminology-glossary.md) defines these five terms alongside the rest of
the platform vocabulary.
