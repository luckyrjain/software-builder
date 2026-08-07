# Gate policy

Every non-happy-path branch this skill can hit, in phase order. "Ask" means stop and wait for a human
turn — a caller is always present for this flow, so ask rather than guess.

## 1. Missing or malformed target or repo_root

HARD STOP at Inputs. See [workflow/inputs.md](../workflow/inputs.md). Never default `target.mode` to
`backfill` with an inferred scope, and never default `repo_root` to the current directory when it wasn't
actually given.

## 2. Ambiguous canonical collection

Two or more `*.postman_collection.json` files at comparable confidence within the same target's scope,
with no naming convention (`main`/`primary`) or CI reference pointing at exactly one. Ask once, listing the
real candidates the scan found. `test_framework_hint` resolves this without asking only when it names one
of the actual candidates (by path or basename).

## 3. Zero Postman/Newman tooling detected

No `*.postman_collection.json` file and no `newman` dependency anywhere in the target's scope. Ask which
collection to create (and where) before writing anything — never default silently to whichever layout this
session would pick for a greenfield project.

## 4. Diff source doesn't resolve

`target.source` names an MR, branch, or ref this session cannot read. HARD STOP, ask for a working
reference — do not fall back to "diff against the last commit."

## 5. Target has no real observed endpoint to derive its shape from

This skill's instance of the shared test-first-evidence principle
([test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence)).
When neither the actual route-handler source, an OpenAPI/Swagger spec, nor `API_CATALOG.md` (corroborating
only) gives a real request/response shape for a target, do not invent a plausible-looking payload. Tag
`NEEDS_OBSERVED_ENDPOINT` with a one-line reason instead (see
[generate-tests.md §1](../workflow/generate-tests.md#1-derive-the-requestresponse-shape-from-real-observed-usage-only)).
A caller asking to "just invent a reasonable response shape" does not change the answer — see
[pressure-tests.md](pressure-tests.md) row 4.

## 6. No reachable API instance

Running the collection requires a real, reachable running API instance — locally started, staging, or a
preview deployment. Without one, an assertion on "what the response would look like" would have to be
guessed, which is exactly the fabrication
[test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence)
forbids. Tag every affected target `NEEDS_API_ENV` (see
[verify-and-iterate.md §1](../workflow/verify-and-iterate.md#1-no-reachable-api-instance-check-before-running-anything))
and name what would resolve it — never fabricate what a response would have been.

## 7. Verification surfaces a probable production bug

The most important gate in this skill: a run that fails because the API itself — not the test — returns
the wrong status code, an incorrect/incomplete response schema, or a missing header is a finding about
production behavior, not a test bug. Never edit production code to force the run green, and never loosen
the `pm.test()` assertion (widen a schema check, drop a status-code check) to make a failing run pass —
that just hides the break from every real caller of the endpoint. Tag `WRITTEN_FAILING_PROD_BUG`, keep the
request and assertion exactly as they are, and surface it in the report per
[report.md §3](../workflow/report.md#3-surface-production-bug-findings-plainly) for a human or
**loop-task-implementer**/**pr-review** to act on. Full non-negotiable:
[test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug).

## 8. `max_files_per_run` reached

List every skipped target by name in the report — never a bare count, never silently dropped. Same rule
for a `deadline`/`session_token_budget` cutoff mid-run
([verify-and-iterate.md §6](../workflow/verify-and-iterate.md#6-deadline-token-budget)).

## 9. Genuinely ambiguous test-vs-production failure

After one honest diagnosis pass, if it's still unclear whether the request/assertion or the API is wrong,
tag `NEEDS_HUMAN` rather than guessing in either direction — a wrong guess here is worse than asking.
