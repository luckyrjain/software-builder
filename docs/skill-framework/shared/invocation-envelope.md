# Invocation envelope / result envelope

Tracked from issue #52 (originally #20's roadmap). A composed wrapper skill (release-readiness-checker,
incident-triage-agent, backlog-runner, weekly-squad-digest, cost-optimization-sprint-planner) needs a
consistent shape for **what it hands to a child skill** and **what it gets back** — so every wrapper
doesn't invent its own ad hoc field names for the same concepts.

This doc names that shape and points at where it's already enforced — it does not introduce a new
validation mechanism. The registry's composition-contract machinery
([composition_contracts.py](../../../scripts/registry/composition_contracts.py)) already validates that
a consumer's declared fields are a subset of the producer's schema (`_validate_declared_fields`) and
that an invoked producer actually exposes what its consumer requires
(`_validate_invoke_schema_matching`) — the envelope is data in
the canonical `skills.yaml` manifest's `contracts.composition` section. The generated
[composition_contracts.yaml](../../../scripts/registry/composition_contracts.yaml) is retained as a
projection for compatibility and inspection.

## InvocationEnvelope — what a wrapper hands to a child skill

| Field category | Purpose | Reference implementation |
|---|---|---|
| **Exact scope** | What, precisely, is being invoked on — never inferred from a bare conversational phrase | `mr_context.project` + `mr_context.merge_request_iid` |
| **Interaction policy** | Which mode/path the child skill should take, when it has more than one | `mr_context.review_mode` / `mr_context.audit_type` (pr-review's `pre_merge`\|`incremental`\|`retrospective`, see [review-metadata-schema.md §2.1](review-metadata-schema.md)) |
| **Allowed actions** | What the child is permitted to do externally — this is the invocation-time input; whether it happened is a **result**-side concern (Final repository action, [five-concept-separation-audit.md](five-concept-separation-audit.md)) | `mr_context.posting_policy` |
| **Expected SHA** (where applicable) | The exact revision the child should be evaluating — never left to the child to (re-)resolve when the caller already pinned one | `mr_context.expected_head_sha` |
| **Source revisions** | Provenance the caller resolved before invoking (e.g. release-readiness-checker's own MR-range resolution) | `mr_context.head_sha`; `digest_report.source_revisions` on the result side |
| **Caller/child skill versions** | The canonical manifest entry in `skills.yaml` owns the normalized semantic version. Record the relevant manifest version at invocation time when the interaction must be reproduced later. `SKILL.md` frontmatter no longer owns platform or version metadata. |

`mr_context` (in the canonical manifest's composition contract) is the reference implementation — the fields above
were extended onto it directly rather than inventing a parallel schema, since it was already
consumed by ten skills and needed exactly this field set (see this PR's diff: `review_mode`,
`audit_type`, and `expected_head_sha` were already real fields
[release-readiness-checker/workflow/run-check.md](../../../release-readiness-checker/workflow/run-check.md)
passes to pr-review — the schema just hadn't caught up to what was already true in practice).

## ResultEnvelope — what comes back

Durable cross-skill results use the canonical runtime envelope in
[runtime-contract.md](runtime-contract.md). `review_metadata` and
`assessment_metadata` are producer payload fields, not alternative envelope schemas; their
artifact-specific fields are declared in the canonical manifest's
`contracts.composition.artifact_schemas` and `contracts.platform.artifact_runtime` sections.
The relevant mapping onto the five separated concepts
([five-concept-separation-audit.md](five-concept-separation-audit.md)) is:

| Concept | Field |
|---|---|
| Evidence completeness | `review_complete`, or the skill's own `evidence_summary`/completeness counters |
| Review verdict / typed outcome | `recommendation`, or the skill's own conclusion field (`root_cause`, recommendations list, `Verdict:` line) |
| Final repository action | `posted` (pr-review), or the composition contract's own producer field for a write-shaped artifact (`implementation_pr.pr_url`) |

## Extending this pattern to another wrapper

Do not invent a second envelope schema. When a wrapper skill's invocation is genuinely typed
(explicit fields, not a conversational phrase — same bar `run-check.md` already applies), extend
the existing artifact type it already consumes/produces in the canonical `skills.yaml` manifest,
under `contracts.composition`. The generated `scripts/registry/composition_contracts.yaml` and
`composition_runtime.yaml` files are projections and must not be edited as independent sources.
Add a new `artifact_types` entry only when the interaction genuinely isn't a variant of one of
the existing artifact types.
