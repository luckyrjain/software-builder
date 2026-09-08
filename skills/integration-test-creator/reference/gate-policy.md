# Gate policy

Every non-happy-path branch this skill can hit, in phase order. "Ask" means stop and wait for a human
turn — a caller is always present for this flow, so ask rather than guess. Escalation on a surfaced
production bug is the shared rule in
[test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug)
— this file cites it rather than restating it.

## 1. Missing or malformed `target` / `repo_root`

HARD STOP at Inputs. See [workflow/inputs.md](../workflow/inputs.md). Never default `target.mode` to
`backfill` with an inferred scope, and never default `repo_root` to the current directory when it wasn't
actually given.

## 2. Ambiguous base-runner detection

Two or more base-runner candidates at comparable top confidence (e.g. both `jest.config.js` and
`.mocharc.json` present) — ask once, listing the real candidates the scan found. `test_framework_hint`
resolves this without asking only when it names one of the actual candidates; a hint naming a framework
the scan found zero evidence for is itself a reason to ask, not to trust the hint blindly (the repo may
have migrated away from it).

## 3. Zero base-runner markers found

No config file, no dependency-manifest entry, no existing test files in any recognized ecosystem. Ask
which test command to use before writing anything — never pick "the most common default for this
language," since that may not match what the team actually intends to standardize on.

## 4. Diff source doesn't resolve

`target.source` names an MR, branch, or ref that this session cannot read (not found, no access, merge
conflicts blocking a diff). HARD STOP, ask for a working reference — do not fall back to "diff against
the last commit" or any other silent reinterpretation of `source`.

## 5. Zero orchestration mechanism detected

`ORCHESTRATION: none` — no testcontainers, docker-compose, or embedded-DB convention found — and this
session has no other way to stand up the real dependency (no reachable Docker daemon, nothing already
running). This is **not** a HARD STOP the way §§1–3 are, and it is never a license to mock the dependency
instead: tag the affected target `NEEDS_INTEGRATION_ENV` at Verify & iterate
([workflow/verify-and-iterate.md §2](../workflow/verify-and-iterate.md#2-needsintegrationenv-no-way-to-stand-up-the-real-dependency)),
write the test correctly against the real dependency's real interface, and surface exactly what's missing
in the report ([report.md §4](../workflow/report.md#4-surface-needsintegrationenv-plainly-not-as-a-soft-failure)).
A caller asking "just mock it so the suite runs" after this gate has fired does not change the answer —
see [pressure-tests.md](pressure-tests.md) row 2.

## 6. Verification surfaces a probable production bug

The most important gate in this skill. When a generated test fails and the code — not the test — is what
looks wrong: never edit production code to force the test green, never delete or weaken the failing
assertion, and never `.skip`/`xfail`/`@Disabled` it to hide the failure. Tag `WRITTEN_FAILING_PROD_BUG`,
keep the test exactly as written, and surface it in the report per
[report.md §3](../workflow/report.md#3-surface-production-bug-findings-plainly) for a human or
**loop-task-implementer**/**pr-review** to act on. Full rule:
[test-creation-principles.md §5](../../docs/skill-framework/shared/test-creation-principles.md#5-escalation-on-a-surfaced-production-bug).
A caller asking "just make the suite green" after this gate has fired does not change the answer — see
[pressure-tests.md](pressure-tests.md) row 6.

## 7. `max_files_per_run` reached

List every skipped target by name in the report — never a bare count, never silently dropped. Same rule
for a `deadline`/`session_token_budget` cutoff mid-run
([verify-and-iterate.md §6](../workflow/verify-and-iterate.md#6-deadline-token-budget)).

## 8. Genuinely ambiguous test-vs-production failure

After one honest diagnosis pass, if it's still unclear whether the test or the code is wrong, tag
`NEEDS_HUMAN` rather than guessing in either direction — a wrong guess here is worse than asking.
