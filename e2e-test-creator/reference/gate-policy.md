# Gate policy

Every non-happy-path branch this skill can hit, in phase order. "Ask" means stop and wait for a human
turn — a caller is always present for this flow, so ask rather than guess. The escalation-on-a-surfaced-
production-bug rule (§6) is shared across all four `*-test-creator` skills — see
[test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug)
for the full text; this file states only the e2e-specific framing.

## 1. Missing or malformed `target` / `repo_root`

HARD STOP at Inputs. See [workflow/inputs.md](../workflow/inputs.md). Never default `target.mode` to
`backfill` with a guessed journey, and never default `repo_root` to the current directory when it wasn't
actually given. This includes `target.mode: backfill` with an absent or empty `journeys` list — a journey
has no 1:1 mapping to a source file, so there is nothing safe to infer in place of it.

## 2. Ambiguous browser tooling detection

Two or more candidates at comparable top confidence (e.g. both `playwright.config.*` and
`cypress.config.*` present) — ask once, listing the real candidates the scan found.
`test_framework_hint` resolves this without asking only when it names one of the actual candidates; a
hint naming a framework the scan found zero evidence for is itself a reason to ask, not to trust the hint
blindly (the repo may have migrated away from it).

## 3. Zero browser tooling markers found

No config file, no dependency-manifest entry, no existing spec files in any recognized ecosystem. Ask
which framework/test command to use before writing anything — never pick "the most common default for
this kind of app," since that may not match what the team actually intends to standardize on.

## 4. Diff source doesn't resolve

`target.source` names an MR, branch, or ref that this session cannot read (not found, no access, merge
conflicts blocking a diff). HARD STOP, ask for a working reference — do not fall back to "diff against
the last commit" or any other silent reinterpretation of `source`.

## 5. No reachable app instance

A journey can only be written and run against a real, currently-reachable instance of the app — locally
started, a staging URL, or a preview deployment. Without one, an assertion on "what the page shows" would
have to be guessed, which is exactly the fabrication the shared
[test-creation-principles.md §1](../../docs/skill-framework/shared/test-creation-principles.md#1-test-first-evidence)
forbids. Tag every affected journey `NEEDS_BROWSER_ENV` (see
[generate-tests.md §1](../workflow/generate-tests.md#1-no-reachable-app-instance-check-before-writing-a-single-assertion))
and name what would resolve it — never fabricate what the UI would have shown.

## 6. Verification surfaces a probable production bug

The most important gate in this skill. When a generated test fails and the app — not the test — is what
looks wrong: never edit production code to force the test green, never delete or weaken the failing
assertion, and never `.skip`/`.only`-around it to hide the failure. Tag `WRITTEN_FAILING_PROD_BUG`, keep
the test exactly as written, and surface it in the report per
[report.md §3](../workflow/report.md#3-surface-production-bug-findings-plainly) for a human or
**loop-task-implementer**/**pr-review** to act on. A caller asking "just make the suite green" after this
gate has fired does not change the answer — see [pressure-tests.md](pressure-tests.md) row 6.

## 7. `max_files_per_run` reached

List every skipped journey by name in the report — never a bare count, never silently dropped. Same rule
for a `deadline`/`session_token_budget` cutoff mid-run
([verify-and-iterate.md §5](../workflow/verify-and-iterate.md#5-deadline-token-budget)).

## 8. Genuinely ambiguous journey-vs-production failure

After one honest diagnosis pass, if it's still unclear whether the test or the app is wrong, tag
`NEEDS_HUMAN` rather than guessing in either direction — a wrong guess here is worse than asking. A
flaky selector or timing issue is **not** this case by default — see
[test-quality-deltas.md](test-quality-deltas.md).
