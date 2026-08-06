# Gate policy

Every non-happy-path branch this skill can hit, in phase order. "Ask" means stop and wait for a human
turn — a caller is always present for this flow, so ask rather than guess.

## 1. Missing or malformed `target` / `repo_root`

HARD STOP at Inputs. See [workflow/inputs.md](../workflow/inputs.md). Never default `target.mode` to
`backfill` with an inferred scope, and never default `repo_root` to the current directory when it wasn't
actually given.

## 2. Ambiguous framework detection

Two or more candidates at comparable top confidence (e.g. both `jest.config.js` and `.mocharc.json`
present) — ask once, listing the real candidates the scan found. `test_framework_hint` resolves this
without asking only when it names one of the actual candidates; a hint naming a framework the scan found
zero evidence for is itself a reason to ask, not to trust the hint blindly (the repo may have migrated
away from it).

## 3. Zero framework markers found

No config file, no dependency-manifest entry, no existing test files in any recognized ecosystem. Ask
which framework/test command to use before writing anything — never pick "the most common default for
this language," since that may not match what the team actually intends to standardize on.

## 4. Diff source doesn't resolve

`target.source` names an MR, branch, or ref that this session cannot read (not found, no access, merge
conflicts blocking a diff). HARD STOP, ask for a working reference — do not fall back to "diff against
the last commit" or any other silent reinterpretation of `source`.

## 5. Target needs infrastructure this session can't reach

A live third-party API, a real database, or another dependency with no existing mock/stub convention in
the repo. Tag `UNTESTABLE_WITHOUT_FIXTURE` with a one-line reason (see
[generate-tests.md §4](../workflow/generate-tests.md#4-untestable-without-fixture-gate)) rather than
fabricating behavior for a dependency this skill has never actually observed.

## 6. Verification surfaces a probable production bug

The most important gate in this skill. When a generated test fails and the code — not the test — is what
looks wrong: never edit production code to force the test green, never delete or weaken the failing
assertion, and never `.skip`/`xfail`/`@Disabled` it to hide the failure. Tag `WRITTEN_FAILING_PROD_BUG`,
keep the test exactly as written, and surface it in the report per
[report.md §3](../workflow/report.md#3-surface-production-bug-findings-plainly) for a human or
**loop-task-implementer**/**pr-review** to act on. A caller asking "just make the suite green" after this
gate has fired does not change the answer — see
[pressure-tests.md](pressure-tests.md) row 8.

## 7. `max_files_per_run` reached

List every skipped target by name in the report — never a bare count, never silently dropped. Same rule
for a `deadline`/`session_token_budget` cutoff mid-run
([verify-and-iterate.md §5](../workflow/verify-and-iterate.md#5-deadline-token-budget)).

## 8. Genuinely ambiguous test-vs-production failure

After one honest diagnosis pass, if it's still unclear whether the test or the code is wrong, tag
`NEEDS_HUMAN` rather than guessing in either direction — a wrong guess here is worse than asking.
