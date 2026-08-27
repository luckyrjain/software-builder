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
| change-impact-analyzer | At least one of: trusted `system_design_spec`, exact `mr_context`, `diff_text`, direct `change_text`, or an explicit `changed_paths` list | `assessment_context` |
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

## Environment-sensitive specialists

`observability-review`, `capacity-planner`, and `deployment-risk-review` are environment-sensitive
dimensions (`ENV_SENSITIVE_DIMENSIONS` in the implementation, alongside the four operational gates
covered in [operational-gates.md](operational-gates.md)): a result scoped to a different declared
environment than the candidate's own must never be recorded as this candidate's evidence, even when
its identity (revision/head SHA) otherwise matches. Assemble and compare each specialist's declared
`environment` the same way its mandatory inputs above are assembled — never assume it matches the
candidate's just because no conflicting field was supplied: if either side (the candidate or the
specialist's own result) doesn't declare an environment at all, that absence is never itself a
match, on any of the seven `ENV_SENSITIVE_DIMENSIONS` (these three specialists and the four
operational gates alike).

### Checking identity and environment on a nested or flat carrier

A candidate's or a specialist result's own identity (`source_revision`/`head_sha`) and `environment`
may be declared either as a flat top-level field on the object, or one level down inside that same
object's own `assessment_target` (or `target`) carrier — both are legitimate shapes, and a caller or
a specialist may use either one. When checking a specialist's result against the candidate:

1. Look for the field (`environment`, `source_revision`, `head_sha`) inside the result's own
   `assessment_target`/`target` mapping first, if it has one and it declares that field.
2. Only if that nested carrier is absent, or is present but doesn't declare the field, fall back to
   the object's own flat top-level field.
3. Once a nested carrier declares the field, it is authoritative outright — a flat field's own
   agreement or disagreement with the candidate becomes irrelevant and is not itself consulted. A
   result whose flat `source_revision` happens to match the candidate but whose own nested
   `assessment_target.source_revision` names a different commit is still rejected
   (`target_mismatch`), because step 1 already resolved the nested value and never falls through
   to step 2. Never resolve identity or environment by picking whichever of the two locations
   happens to match what you were hoping to see — always resolve nested-first per steps 1–2 above,
   independent of what the flat field says.

This nested-vs-flat check applies everywhere a specialist's or child result's identity or
environment is compared against the candidate — not only for the environment-sensitive dimensions
listed above, but for every dispatched child's identity binding (per
[dispatch.md § 3](../workflow/dispatch.md)).
