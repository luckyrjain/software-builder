# Child input map — per-child mandatory inputs (normative)

**This skill never dispatches a child with a knowingly-incomplete mandatory input.** When a mandatory
field below cannot be assembled from the diff, the repository, or an explicit caller-supplied field,
that child is not invoked — the dimension is recorded `UNKNOWN` directly, with the missing-field reason
retained in `dispatch_log` (per [gate-policy.md](gate-policy.md)). This table mirrors each specialist's
own documented HARD STOP fields; if a specialist's own `SKILL.md` changes its required inputs, this
table needs the matching update.

| Child | Mandatory input(s) | Carried as |
|---|---|---|
| pr-review | `merge_request_iid`/PR number, `project`, `expected_head_sha` | Typed `mr_context` fields, always with `review_mode: retrospective`, `audit_type: retrospective`, `posting_policy: forbidden` |
| change-impact-analyzer | At least one of: trusted `system_design_spec`, exact `mr_context`/diff, direct change text | `assessment_context` |
| deployment-risk-review | `change_description` | `assessment_context` |
| security-review | `review_target` (the code/config/design content under review) | `assessment_context` |
| observability-review | `service_name` **and** `observability_material` (metrics/logs/tracing/dashboards/alerts/SLO material) | `assessment_context` |
| resilience-review | `resilience_behavior` (current/proposed failure behavior across the ten resilience dimensions) **and** `dependency_paths` (affected upstream/downstream paths) | `assessment_context` |
| api-design-review | `api_spec` (the API design/contract text — OpenAPI/GraphQL SDL/proto/event-schema) | `assessment_context` |
| database-review | At least one of: `schema` (DDL), `migration_script`, `queries` | `assessment_context` |
| performance-review | `reviewed_content` (the code, query, or service content to review) | `assessment_context` |
| capacity-planner | `demand_data` **and** `forecast_horizon` | `assessment_context` |
| dependency-upgrade-review | `dependency_name`, `current_version`, **and** `target_version` | `assessment_context` |

## Assembly rule

Every mandatory field above must come from evidence already collected in Collect evidence or Dispatch
(the exact diff, repository content, or an explicit caller-supplied field on `assessment_target`) —
never a guess, never a paraphrase of the PR/MR title/description standing in for the real artifact
(e.g. a description that says "adds an endpoint" does not satisfy `api_spec`; the actual contract text
does). `assessment_context`'s own carrier fields (`assessment_target`, `inputs`, `input_provenance`,
`evidence_refs`, `unresolved`) are populated per the invocation-envelope conventions in
[invocation-envelope.md](../../docs/skill-framework/shared/invocation-envelope.md); the mandatory
fields above populate `assessment_context.inputs`.

## Composite mandatory inputs

`resilience-review` and `observability-review` each require **two** fields together — a mandatory
input map entry is satisfied only when every field in its row is assembled; a partial match (e.g.
`service_name` resolved but `observability_material` not) is still a knowingly-incomplete mandatory
input and blocks dispatch the same as a fully-missing field.

## database-review's "at least one of three"

Unlike the composite rows above, `database-review`'s row is satisfied by **any one** of `schema`,
`migration_script`, or `queries` — dispatch proceeds once one of the three is assembled; it is not
required to assemble all three.
