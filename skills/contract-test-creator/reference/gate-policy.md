# Gate policy

Every non-happy-path branch this skill can hit, in phase order. "Ask" means stop and wait for a human
turn — a caller is always present for this flow, so ask rather than guess.

## 1. Missing or malformed target, repo_root, or role

HARD STOP at Inputs. See [workflow/inputs.md](../workflow/inputs.md). Never default `target.mode` to
`backfill` with an inferred scope, never default `repo_root` to the current directory when it wasn't
actually given, and — the delta specific to this skill — **never infer `target.role`** (`consumer` or
`provider`) from a file's location, its filename, or which side of the interaction it "looks like." The
consumer/provider generation logic is completely different; a wrong guess produces an actively misleading
test. Ask which role before proceeding.

## 2. Ambiguous Pact tooling detection

Two or more Pact libraries at comparable top confidence within the same target's scope (e.g. a monorepo
edge case with two ecosystems both showing a `pacts/`-corroborated dependency). Ask once, listing the real
candidates the scan found. `test_framework_hint` resolves this without asking only when it names one of
the actual candidates.

## 3. Zero Pact tooling detected

No manifest entry for any of pact-js, pact-python, pact-jvm, pact-go, or pact-ruby in the target's scope.
Ask which Pact library/broker setup to use before writing anything — never default silently to whichever
Pact binding this session would pick for a greenfield project.

## 4. Diff source doesn't resolve

`target.source` names an MR, branch, or ref this session cannot read. HARD STOP, ask for a working
reference — do not fall back to "diff against the last commit."

## 5. Target has no real observed interaction to derive its shape from

This skill's instance of the shared test-first-evidence principle
([test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence)).
When neither an actual request-building call site, an existing API client method's real usage, nor an
OpenAPI/GraphQL schema file exists for a target, do not invent a plausible-looking request/response shape.
Tag `NEEDS_OBSERVED_INTERACTION` with a one-line reason instead
(see [generate-tests.md §3](../workflow/generate-tests.md#3-derive-the-interaction-shape-from-real-observed-usage-only)).
A caller asking to "just invent a reasonable response shape" does not change the answer — see
[pressure-tests.md](pressure-tests.md) row 3.

## 6. Verification surfaces a probable production bug

The most important gate in this skill, with a contract-testing-specific shape: a **provider verification
failure against a real, existing pact file usually means the provider broke a real consumer's
expectation** — it is a finding about production behavior, not a test bug. Never edit production code to
force the verification green, and never loosen the pact file (widening a matcher, deleting an
interaction) to make a failing verification pass — that just hides the break from every consumer that
relies on it. Tag `WRITTEN_FAILING_PROD_BUG`, keep the pact file and the verification test exactly as
they are, and surface it in the report per
[report.md §3](../workflow/report.md#3-surface-production-bug-findings-plainly) for a human or
**loop-task-implementer**/**pr-review** to act on. Full non-negotiable:
[test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug).

## 7. `max_files_per_run` reached

List every skipped target by name in the report — never a bare count, never silently dropped. Same rule
for a `deadline`/`session_token_budget` cutoff mid-run
([verify-and-iterate.md §5](../workflow/verify-and-iterate.md#5-deadline-token-budget)).

## 8. Genuinely ambiguous test-vs-production failure

After one honest diagnosis pass, if it's still unclear whether the test/pact expectation or the code is
wrong, tag `NEEDS_HUMAN` rather than guessing in either direction — a wrong guess here is worse than
asking.
