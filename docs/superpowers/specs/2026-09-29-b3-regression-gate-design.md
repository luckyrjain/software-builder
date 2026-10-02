# System Design Spec — B3: bug-diagnosis → loop-task-implementer fail-before/pass-after regression gate

**Readiness: Ready with open questions**

## Revision history

- **Revision 1**: closed all 5 architecture-review conditions on paper. Round 1 (3 personas) found 9
  blocking issues: command injection, no environment isolation, an unreconciled Blocking-standard
  addition, a factual error, an unnamed historical-secrets risk, a budget/hang-detector conflation, no
  machine cross-check, a wrong-artifact registry question, and a misread isolation rule.
- **Revision 2**: fixed all 9. Round 2 found 6 more: the command regex closed shell-injection but not
  test-runner-extensibility code execution; the new Blocking-standard condition contradicted the
  architecture review's own Condition 4; a "same sandboxing as head" claim was unfounded; the machine
  cross-check had no real data contract (found independently by all 3 reviewers); the doubled budget was
  never reconciled against the per-task ceiling; the registry `fields` edit targeted a generated file.
- **Revision 3**: fixed all 6 with a `source`-tagged finding field, a split Blocking-standard condition,
  base-commit-half caching, and corrected registry file targets. Round 3 found the fixes' *shape* was
  right but their *wiring* broke against real code in every case:
  - **[Security Architect]** `_regression_gate_errors` queried a state path that doesn't exist
    (`review.lens_a.findings.items` — the real `findings` collection is a top-level sibling of `review`,
    not nested under a lens) and checked a `status: ACCEPTED | HUMAN_ACCEPTED` vocabulary that exists
    nowhere in the codebase. Also found a genuinely new vector: the regex's permissive argument charset
    allows pytest's own `--junitxml=`/`--cov-report=`/`--basetemp=` flags to write to arbitrary absolute
    paths outside the disposable worktree — no repo cooperation needed, distinct from the
    extensibility-execution risk. Also found the cache key omitted `root_cause_summary`, which the cached
    judgment actually depends on.
  - **[Software Architect]** Independently confirmed the same broken state path and the same
    nonexistent `status`/`HUMAN_ACCEPTED` vocabulary — the real adjudication field is
    `rebuttal_log[].adjudication: ACCEPTED | REJECTED | NEEDS_EVIDENCE`, a different name, different
    structure, no `HUMAN_ACCEPTED` value anywhere. Also found Fix 6's caching structurally unreachable:
    the Reviewer is deliberately re-isolated on every dispatch, and `orchestrator.md` explicitly instructs
    withholding "Previous Reviewer verdicts" when building each fresh review package — a Reviewer session
    has no way to even see a prior generation's cached result.
  - **[SRE]** Redid the worst-case math with caching applied, using the design's own numbers: even with
    caching, Reviewer-dispatch time alone (120 min generation 1 + 180 min across 3 reruns) already exceeds
    the 180-minute per-task ceiling before adding Builder remediation time — caching reduced but did not
    close the gap the design claimed it closed.
  - Confirmed genuinely fixed this round: the registry file-target correction (Fix 10), the Builder-visibility
    correction (Fix 5), the NEEDS_EVIDENCE-vs-PROPOSED_BLOCKING classification split's *prose* (Fix 3 was
    correctly reasoned; only its *enforcement* mechanism was broken).
  Three consecutive rounds of inventing new cross-check/caching machinery each broke in a new way when
  checked against real code — the same shape of exhaustion this session's B2 ticket hit on a different
  problem, resolved there by routing through what already exists instead of inventing more.
- **Revision 4**: dropped the invented `_regression_gate_errors`/`source`-field/Reviewer-side-caching
  machinery, routing findings through existing mechanisms and moving the caching decision to the
  Orchestrator. Round 4 found this pivot's *direction* sound but its *execution* had two fresh bugs:
  - **[Security Architect, Software Architect — independently, identical bug]** Fix 1's own validator
    inspected `match.group(1)` (the fixed command verb — `pytest`/`make`/`npm`, which by construction can
    never contain `/` or `..`) instead of `match.group(2)` (the actual arguments, where every dangerous
    path lives) — the entire absolute-path/traversal check was dead code, confirmed by direct execution:
    all of round 3's file-write bypasses (`--junitxml=/etc/cron.d/x`, etc.) still passed through unmodified.
    Security Architect also found a secondary bug (the `=`-split only stripped the first `=`).
  - **[SRE, Software Architect — independently, same root cause]** Fix 6's own isolation claim ("the
    Reviewer is never told a fact to trust, only what work is in scope") was contradicted by Fix 2 step 5,
    left unrevised since revision 2: on a head-only-scoped dispatch, the Orchestrator still handed the
    Reviewer `base_failure_matches_root_cause` — a prior generation's subjective judgment, not a raw fact —
    for the Reviewer to fold into its own `gate_satisfied` conclusion. The "scope, not fact" distinction
    was cosmetic as specified, not real.
  - **[SRE, Software Architect — independently]** The regression gate runs per-lens (Lens A and Lens B
    each dispatch independently), never stated explicitly, so "a full dispatch" budget figures silently
    undercounted the real per-generation cost by 2x.
- **Revision 5**: fixed Fix 1's `group(1)`/`group(2)` bug and the `=`-split bug; dropped the
  Orchestrator-side caching/scoping optimization entirely (three consecutive attempts to make a
  cross-generation shortcut coexist with this skill's deliberate per-dispatch Reviewer isolation each broke
  in a new way — every dispatch now always runs the full procedure, both lenses, matching what earlier
  revisions already said before the optimization was added). Round 5 returned CLEAN from SRE (two minor
  numeric/placement suggestions, applied) but found one more real bug from Security Architect:
  - **[Security Architect]** Fix 1's corrected (`group(2)`, multi-`=`) validator still missed a *fourth*
    distinct delimiter shape: pytest-cov's `TYPE:DEST` colon syntax (`--cov-report=html:/home/user/.ssh/
    authorized_keys`) — confirmed by direct execution, a real, exploitable file-write bypass, the same
    vulnerability class found and "fixed" three times already in this same function.
- **Revision 6** (this version): replaces delimiter-specific splitting with a single delimiter-agnostic
  substring search over the whole command — no tokenizing, so no future delimiter syntax needs to be
  individually enumerated and missed. Applies SRE's two round-5 suggestions (worst-case arithmetic now
  includes the initial Builder dispatch; the budget-ceiling recommendation cites `orchestrator.md` §3, not
  § Inputs). Detailed below.

## Grounding note

The Reviewer's existing "Read-only execution rights" already grant "Use a disposable local worktree" and
"Run tests... locally" (`reviewer.md:39-47`) — a second worktree at a historical commit remains a narrow
extension of an already-granted capability (Condition 1, unchanged across all revisions). Also unchanged
across all revisions and re-confirmed each round: `implementation_task` is external/exempt from the
two-surface registry check; `bug_diagnosis_report` is durable and needs both surfaces, both edits landing
in `skills.yaml` directly, never the generated `composition_contracts.yaml`.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `bug_diagnosis_report` (new: `repro_command`) | Carries a validated, file-write-safe runnable command | `skills/bug-diagnosis`; both `skills.yaml` registration surfaces | Condition 3; Fix 1 |
| `implementation_task` (new: `regression_gate`) | Carries origin signal + command + root-cause summary to both Builder and Reviewer | Built by the Orchestrator/human; `skills.yaml`'s `fields` list only | Conditions 3, 5; Fix 5 |
| `loop-task-implementer`'s Builder (`builder.md`) | Self-verifies against `regression_gate.command` before Reviewer dispatch | Real, specified consuming behavior | Fix 5, 8 |
| `loop-task-implementer`'s Reviewer (`reviewer.md`) | Executes the full dual-commit gate from scratch, every dispatch, every lens; raises an ordinary finding, no new field | New subsection; reuses the *existing* finding schema and Blocking-standard structure; no cross-generation state consulted | Conditions 1, 4; Fixes 2, 3, 4 |
| `loop-task-implementer`'s Orchestrator (`orchestrator.md`) | Charges runtime against an explicit, real, per-generation (both-lens) budget; states a numeric recommended per-task ceiling for gate-carrying tasks | One new conditional rule in §3's response-wait-budget list, mirroring the exact precedent this session's own B1 ticket already set for extending that same sentence | Condition 2; Fix 6 |
| Existing, unmodified `accepted_blocking_findings_open` / non-security-sensitive `NEEDS_EVIDENCE` disclosure rule | Already-working enforcement this design routes through instead of inventing new machinery | `validate_loop_lifecycle.py:219-221`; `orchestrator.md:582-584` | Fix 7 |
| `cross-skill-escalation.md` (rows 138, 199) | Documents the handoff now optionally carries `regression_gate` | Documentation only | |

## APIs

### Fix 1 (revision 6, replaces four consecutive attempts at delimiter-specific parsing) — command validation via a delimiter-agnostic substring search, not token/segment splitting

Rounds 3, 4, and 5 each found a real, distinct bypass in a version of this function that tried to identify
"the path value" by splitting on a specific delimiter and checking that segment: round 3 found the check
inspected the wrong regex capture group entirely (a no-op); round 4's fix inspected the right group but
only split on `=`, missing multi-`=` tokens; round 5 found even that missed pytest-cov's `TYPE:DEST` colon
syntax (`--cov-report=html:/home/user/.ssh/authorized_keys`) — a *fourth* distinct delimiter shape in the
same narrow domain. Three consecutive delimiter-specific patches each closed the exact bypass found and
missed the next one. **The fix: stop trying to identify which delimiter precedes a dangerous value at
all.** Search the whole matched argument text directly for the *shape* of danger — any of the narrow set
of separator characters the allowed charset itself permits (`=`, `:`, `-`, or plain whitespace) immediately
followed by `/` (an absolute path start), or the literal substring `..` anywhere (a traversal marker) — with
no tokenizing, no per-segment splitting, nothing for a fifth delimiter syntax to slip past.

```python
import re

_REPRO_COMMAND_BASE = re.compile(
    r"^(pytest|python3 -m pytest|make [\w-]+|npm test|npm run [\w:-]+)((?: [\w./:=-]+)*)$"
)
_DANGEROUS_PATH_MARKER = re.compile(r"[\s=:-]/|\.\.")

def validate_repro_command(command: str | None) -> str | None:
    """Return the command if it matches a known, safe test-runner invocation shape with no
    absolute-path or traversal content anywhere; else None.

    Closes: shell metacharacters/chaining/substitution/redirection (round 1); absolute-path
    arguments and ".." traversal, closed via a single delimiter-agnostic substring search rather
    than delimiter-specific splitting (rounds 3-5 each found a distinct delimiter shape -- bare,
    "=", multi-"=", pytest-cov's "TYPE:DEST" colon syntax -- slip past a splitting-based check;
    this version doesn't split at all, so no delimiter syntax needs to be individually enumerated).

    "..": rejected as a literal substring anywhere in the command, not just as an isolated path
    segment -- deliberately broader than strictly necessary (a value like "1..2" would also be
    rejected) because the allowed character class is narrow enough (test-runner invocations only)
    that this is not expected to reject any legitimate repro command, and over-rejection fails
    safe into Condition 3's existing "not automatable" fallback, never into executing something
    dangerous.

    Does NOT and cannot close: a syntactically clean, dangerous-substring-free, relative-path-only
    command still executes whatever the test runner's own extensibility points define at the
    checked-out commit (conftest.py collection, a Makefile recipe body, npm lifecycle hooks). No
    command-shape validator can constrain what a test runner itself chooses to execute; only
    execution-environment sandboxing could, and this design does not add that (accepted residual
    risk, Open questions).
    """
    if command is None:
        return None
    if not _REPRO_COMMAND_BASE.fullmatch(command):
        return None
    if _DANGEROUS_PATH_MARKER.search(command):
        return None
    return command
```

Re-verified by direct execution against every bypass found across rounds 3-5:
`--junitxml=/etc/cron.d/x`, `--cov-report=html:/home/user/.ssh/authorized_keys`,
`--cov-report=xml:/etc/cron.d/evil`, `--basetemp=/some/dir`, bare `pytest /etc/passwd`,
`pytest tests/../../etc/passwd`, `--cov-report=html:../etc/passwd`, `--x=y=/etc/passwd` — all correctly
rejected (`None`). Legitimate commands still validate: `pytest tests/test_foo.py`,
`pytest tests/test_foo.py::test_bar` (the `::`-separated test-id syntax doesn't trip the check — no `/`
immediately follows either colon), `make test`, `npm run test:unit`.

Populated only when `repro_status: confirmed` and a single command exists; `null` otherwise (Condition 3's
fallback, `repro_evidence` continues to explain why). Re-validated again immediately before Reviewer
execution — a copy-forward step must never be trusted to have preserved validity.

### Fix 2 (unchanged since revision 2, re-confirmed rounds 2 and 3) — Reviewer's regression-gate procedure, with environment isolation

```
## Regression gate (bug-diagnosis-originated tasks)

When implementation_task.regression_gate.command is present (non-null) AND independently re-validates
against validate_repro_command (Fix 1) — if it fails re-validation, treat exactly as command: null.

Run the FULL procedure below on every dispatch, for both Lens A and Lens B, every review generation --
including reruns. (Round 3/4: an earlier version of this design tried to let the Orchestrator skip the
base-commit half on a rerun by scoping a dispatch to "head-only" and supplying the prior generation's
base-commit judgment as a fact for the Reviewer to use. Two independent round-4 reviewers found this
still handed a fresh Reviewer session a prior generation's subjective conclusion to trust -- exactly
what this skill's own isolation architecture (orchestrator.md:451, withholding "Previous Reviewer
verdicts" from every fresh review package) exists to prevent. Three consecutive attempts at a
cross-generation shortcut each broke against that isolation boundary in a new way. This design now
runs the full, self-contained procedure every time, with no cross-generation state consulted by the
Reviewer at all -- the cost is real and is disclosed honestly in Capacity/Failure strategy below,
not hidden behind an optimization that doesn't actually work.)

1. Provision a SECOND disposable local worktree via `git worktree add`, separate from the primary
   worktree at head. Check out exactly state.repository.base_commit_at_start -- never any other commit.
   (Revision note, 2026-10-02: nothing populates that field. The gate now checks out the review package's
   `Base commit`, the Orchestrator-computed merge-base of the dispatch's head, preserving this
   condition's intent that the Reviewer never picks the commit. See the CHANGELOG entry.)
2. Install this worktree's OWN dependencies from scratch -- never share the primary worktree's
   dependencies, test cache, scratch directories, or database/service fixture state.
3. Run regression_gate.command in the base-commit worktree.
   - Checkout/install errors before a pass/fail result: base_commit_checkout: SETUP_ERROR.
   - Command unexpectedly PASSES: base_test_result: UNEXPECTED_PASS.
   - Command FAILS: compare the failure's actual output against regression_gate.root_cause_summary.
     Plausible match -> base_test_result: FAILED_AS_EXPECTED, base_failure_matches_root_cause: true.
     Unrelated -> base_failure_matches_root_cause: false.
4. Run the same command at head (primary worktree). Record head_test_result: PASSED or FAILED.
5. gate_satisfied: true only when all three, ALL freshly computed in this same dispatch: FAILED_AS_EXPECTED,
   base_failure_matches_root_cause: true, head_test_result: PASSED. No prior-generation fact is ever
   consulted or supplied.

Discard the second worktree after use (reviewer.md:48).
```

### Fix 3 (unchanged since revision 3's prose, re-confirmed round 3) — Blocking-standard condition 6 covers only a demonstrated defect

```
## Blocking standard (reviewer.md:88-94, amended)

[... existing 5 conditions, unchanged ...]
6. The task carries a mandatory regression_gate (regression_gate.command is non-null and re-validates)
   and regression_gate_result.head_test_result is FAILED -- a demonstrated defect.
```

A finding raised under condition 6 is an **ordinary `PROPOSED_BLOCKING` finding, using the existing finding
schema unmodified** — no new field, no new tag. It flows through this skill's normal, already-working
adjudication path exactly like any other finding. Its `evidence` field must begin with the same fixed
literal prefix Fix 4 requires for the inconclusive path, `"regression_gate: "` (round 5, Software
Architect: the two classes need the same convention, or the Observability section's claim that both are
prefix-greppable is only true for one of them).

### Fix 4 (revision 4, replaces round-3's broken machine-cross-check) — the inconclusive sub-cases are ordinary `NEEDS_EVIDENCE`, and the existing disclosure rule already satisfies the architecture review's actual requirement

Round 3 found `_regression_gate_errors` unimplementable three separate ways (wrong state path, nonexistent
`status` vocabulary, and — independently — that `orchestrator.md`'s real forced-resolution rule for
`NEEDS_EVIDENCE` is a **closed class** (`orchestrator.md:578-581`: "authentication, authorization,
secrets/credential handling, or a trust boundary" only) that this design never extended, so Fix 3's "always
a lifecycle blocker" claim had no real backing even before the broken Python).

**The actual fix: don't force this into the closed security-sensitive class at all.** Re-read the
architecture review's Condition 4 literally: *"Name both failure modes... explicitly as `NEEDS_EVIDENCE`-
class outcomes, never a silently-satisfied gate."* "Never silent" means never silent — visible, disclosed,
not misrepresented as passing. It does not require a forced hard block. And this skill's own **existing,
unmodified** rule for a non-security-sensitive `NEEDS_EVIDENCE` already guarantees exactly that:

> *"If evidence cannot be gathered and the finding is outside that class, it may remain `NEEDS_EVIDENCE` at
> completion — but must be listed by `finding_id` and rationale in the completion report (§19), **never
> silently dropped** because it was never promoted to `ACCEPTED`."* — `orchestrator.md:582-584`

So: `base_commit_checkout: SETUP_ERROR`, `base_test_result: UNEXPECTED_PASS`, or
`base_failure_matches_root_cause: false` is raised as an **ordinary `NEEDS_EVIDENCE` finding, existing
schema unmodified**. This design adds zero new enforcement code. What it does add is a one-line, fixed
convention (round 4, Software Architect suggestion — tightened from "must name the gate" to an exact,
greppable literal): the finding's `evidence` field must begin with the exact literal prefix
`"regression_gate: "` (e.g. `"regression_gate: base-commit test unexpectedly passed — cannot confirm the
diagnosed bug reproduces at the merge-base"`). This is still not machine-validated — no field
in `reviewer.md`'s existing finding schema is — but a fixed literal prefix is unambiguously greppable by a
human or a future tool, unlike free-form "mention the gate somewhere" phrasing.

This is deliberately less than revision 3 claimed ("always a lifecycle blocker requiring explicit human
resolution") — that claim is now retracted as unbacked. What Condition 4 actually asked for — visibility,
never silent satisfaction — is fully delivered by existing, unmodified machinery. Whether a human reading
the completion report chooses to treat an unresolved gate-related `NEEDS_EVIDENCE` as blocking is the same
judgment call this skill's doctrine already leaves to non-security-sensitive `NEEDS_EVIDENCE` findings today
— not a new gap this design introduces, and not a guarantee it overclaims.

### Fix 5 (unchanged since revision 2, re-confirmed rounds 2 and 3) — `regression_gate.command` is a Builder input

`SKILL.md:149`'s isolation rule is one-directional. `regression_gate.command`/`root_cause_summary` are
passed to the Builder as a required validation command alongside acceptance criteria.

### Fix 6 (revision 5 dropped caching; revision 6 makes the budget a real rule, not undisclosed prose) — no cross-generation shortcut; every dispatch runs the full procedure; the doubled budget is an explicit orchestrator.md edit

Round 3 found Reviewer-side caching unreachable given this skill's isolation architecture. Round 4's fix
(Orchestrator-side scoping) was found, independently by two reviewers, to still relay a prior generation's
subjective judgment (`base_failure_matches_root_cause`) into a "fresh" Reviewer session's own output via
the dispatch instructions — the "scope, not fact" distinction didn't survive contact with Fix 2's own
unrevised text. Three attempts at a cross-generation shortcut, three different ways it broke against the
same isolation boundary.

**The fix: stop trying to shortcut it.** Every Reviewer dispatch — both lenses, every generation, including
every dirty-review rerun — runs Fix 2's full procedure (both worktrees, both commits, both dependency
installs) from scratch, with zero cross-generation state consulted by the Reviewer. This is not a new
constraint this design invents; it is exactly what this document's own earlier revisions already said
before the caching optimization was added ("a reviewer rerun re-executes the whole gate from scratch,
consistent with how every other check already behaves on rerun"). Reverting to it removes the
Fix 2/Fix 6 contradiction at the root, not by patching it a fourth time.

**Budget — a real, stated rule, not undisclosed prose (round 5, Software Architect: the first version of
this fix disclaimed "no new dispatch logic," which meant literally nothing enforced the doubled figure —
`orchestrator.md`'s real response-wait budget is a flat, unconditional 30-minute default with no
caller-override mechanism, so every legitimate gate-carrying dispatch, needing ~60 minutes, would trip the
existing non-responding-session circuit breaker as the modal outcome, not an edge case). This needs one
real, explicitly-new sentence in `orchestrator.md` §3's response-wait-budget list — the exact same editing
pattern this session's own B1 ticket already used to extend that identical sentence for its own clarify
sub-step (`orchestrator.md`'s response-wait budget already reads "...or the optional clarify sub-step's
dispatch (§2, gap-backlog B1), to return a result: default 30 minutes"):**

```
# orchestrator.md §3, response-wait-budget sentence, extended a second time:
Maximum wait for a dispatched Builder or Reviewer session, or the optional clarify sub-step's dispatch
(§2, gap-backlog B1), to return a result: default 30 minutes -- except a Reviewer dispatch whose task
carries a non-null implementation_task.regression_gate.command (gap-backlog B3), which gets 60 minutes,
reflecting the real ~2x test-execution cost (base + head, each with its own from-scratch dependency
install) -- treat a non-responding session as a failure, escalate, do not silently retry indefinitely.
```

Disclosed as an estimate, not a measured baseline for this repository (Open questions) — but now a real,
enforced number, not prose with nothing behind it.
- **This cost applies to BOTH Lens A and Lens B independently** — round 4 (SRE, Software Architect,
  independently) found earlier revisions never stated this, silently undercounting real per-generation
  cost by 2x. Stated explicitly here: **per-generation Reviewer-dispatch cost for a gate-carrying task is
  2 lenses × 60 min = 120 minutes**, before any Builder remediation time.
- Worst case across `max_dirty_reviews: 3` (1 initial generation + up to 3 remediation reruns, all of
  which re-run the full gate per this fix): **4 generations × 120 min = up to 480 minutes** of
  Reviewer-dispatch time alone, plus up to 3 Builder remediation dispatches (30 min default each = 90
  min) — **up to ~570 minutes of Reviewer-plus-remediation time**, plus the initial Builder
implementation dispatch (default 30 min, before the first Reviewer generation) — **~600 minutes
total worst case**, against the 180-minute `max_task_elapsed_minutes` default.

**Per-task ceiling — an explicit, numeric recommendation, not a vague "raise it if needed":** a caller
dispatching a task with `regression_gate.command` present should set `max_task_elapsed_minutes` to at
least 630 (comfortably above the ~600-minute disclosed worst case, itself Reviewer + remediation +
the initial Builder dispatch), using this budget system's own
existing, documented flexibility (*"the caller may raise or lower it"*). This recommendation belongs in
`orchestrator.md` §3 "Budget and size guards" (where the real numeric defaults and the "caller may
raise or lower it" language actually live, cross-referenced from § Inputs) — not `reviewer.md`,
which a dispatched Reviewer sub-agent reads mid-task, after the budget is already fixed (round 4, SRE).

This is deliberately expensive and deliberately disclosed as such, rather than optimized via a mechanism
that doesn't actually work within this skill's isolation architecture.

### Fix 7 — see Fix 3 and Fix 4 above (routes through existing, already-enforced mechanisms). Cross-reference only.

### Fix 8 (unchanged since revision 3, re-confirmed round 3) — `bug_diagnosis_report`, not `implementation_task`, needs the two-surface registration; both edits target `skills.yaml` directly

```yaml
# skills.yaml, contracts.composition.artifact_schemas.bug_diagnosis_report.fields gains:
- repro_command
# skills.yaml, contracts.platform.artifact_runtime.payload_types.bug_diagnosis_report gains:
repro_command: string
# skills.yaml, contracts.composition.artifact_schemas.implementation_task.fields gains:
- regression_gate
```

`composition_contracts.yaml` is regenerated via `make generate` from these edits — never an edit target
itself (round 2 found revision 2's `fields`-half edit targeted the generated file; corrected in revision 3
and re-confirmed clean in round 3).

### Fix 9 (unchanged since revision 3, re-confirmed round 3) — Builder-side consuming behavior for `regression_gate.command`

```
## Builder: regression_gate.command handling

If present, run it locally after implementing the fix, before marking the task ready for Reviewer
dispatch:
- PASSES: proceed normally.
- Still FAILS: expected mid-implementation signal, keep iterating.
- Errors (not a test failure, a setup/invocation error): report explicitly in completion notes.
Advisory only for the Builder's own iteration -- never replaces or is replaced by the Reviewer's
independent dual-worktree execution of the same command (Fix 2).
```

## Events

None — no new `run_log.py` event or reason code needed.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `bug_diagnosis_report.repro_command` | `str \| null`, validated (Fix 1, now blocks absolute paths/traversal too) | Copied into `implementation_task.regression_gate.command`; re-validated on arrival | `skills/bug-diagnosis` |
| `implementation_task.regression_gate` | `source_skill`, `command`, `root_cause_summary` | Read by both Builder (Fix 5, 9) and Reviewer (Fix 2) | `implementation_task` envelope |
| `regression_gate_result` (Fix 6, per-dispatch only) | `base_commit_checkout`, `base_test_result`, `base_failure_matches_root_cause`, `head_test_result`, `gate_satisfied` | A Reviewer's own report for that one dispatch — not persisted or reused across generations; freshly computed every time (Fix 6) | `reviewer.md`'s output, per dispatch |
| Findings raised under condition 6 or the inconclusive path | **Existing, unmodified finding schema** — no new field | Flow through existing adjudication (`accepted_blocking_findings_open`) or existing non-security-sensitive `NEEDS_EVIDENCE` disclosure (`orchestrator.md:582-584`) | `reviewer.md`'s existing output schema |

## State machines

`regression_gate_result`'s progression, freshly re-run every dispatch: `checkout → dependency-install →
base_test → (root_cause_match) → head_test → gate_satisfied`. No cross-generation state; no field tracks
"already established" anywhere (Fix 6, revision 5).

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| `bug_diagnosis_report.repro_command` vs. `implementation_task.regression_gate.command` | Copy-once, re-validated on arrival | Stale/corrupted copies can never silently bypass the command-shape check |
| Findings raised by the gate vs. lifecycle completion | Strong, via existing mechanisms | `accepted_blocking_findings_open` (demonstrated defect) and the existing non-security-sensitive `NEEDS_EVIDENCE` disclosure rule (inconclusive) — no new cross-check code, no new failure surface for that code to have |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| Base-commit checkout-and-run | Yes — deterministic given the same inputs | Re-executed in full on every dispatch (Fix 6, revision 5) — no caching, by design, after three failed attempts to make caching coexist with Reviewer isolation |
| Head-commit run | Yes, content-dependent | Re-executed on every reviewer rerun, since head content is what changes |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Additional code/schema surface | 2 new optional `skills.yaml` fields, ~90-110 lines of new prose in `reviewer.md`, ~10 lines in `orchestrator.md` (the real-cost budget note + ceiling recommendation), ~10 lines in `builder.md`, 2 `bug-diagnosis` doc edits, 2 escalation-matrix row updates | Smaller than revision 3 and 4 — no new validator function, no new finding field, no new state-schema field, since caching is dropped entirely (Fix 6) and findings route through existing mechanisms (Fix 3/4) |
| Reviewer runtime, per dispatch, per lens | ~2x a single command's runtime + one dependency install, doubled budget (60 min) | Every dispatch, every lens, every generation — no caching (Fix 6) |
| Reviewer runtime, per generation (both lenses) | 2 × 60 min = 120 min | Explicitly stated this revision — round 4 found this was previously undercounted by 2x |
| Worst case, full task lifecycle | ~600 min (30 min initial Builder dispatch + 4 generations × 120 min Reviewer time + 3 × 30 min Builder remediation) | Explicit, disclosed real number, not a claim that a mechanism closes the gap |
| Per-task ceiling | **Explicit numeric recommendation: set `max_task_elapsed_minutes` ≥ 630** for a `regression_gate`-carrying task | Grounded in the worst-case arithmetic above, stated in `orchestrator.md` §3, not left as vague guidance |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| `repro_command` contains shell metacharacters/chaining, an absolute-path argument, or `..` traversal | Never stored as non-null (Fix 1) |
| A regex-valid, relative-path-only command still executes arbitrary code via test-runner extensibility | **Accepted, disclosed residual risk** — no command-shape validator can close this |
| Shared environment/cache state between the two worktree runs | Each gets its own from-scratch dependency install (Fix 2); external-service/DB/queue isolation still has no concrete mechanism (**disclosed, not solved**) |
| Regression genuinely still fails at head | Ordinary `PROPOSED_BLOCKING` finding (Fix 3), existing adjudication, existing `accepted_blocking_findings_open` enforcement — zero new code |
| Base-commit checkout fails / unexpectedly passes / doesn't match root cause | Ordinary `NEEDS_EVIDENCE` finding (Fix 4), existing non-security-sensitive disclosure rule already guarantees it's never silently dropped from the completion report — zero new code |
| A busy multi-task plan has several bug-diagnosis-originated tasks, each rerun multiple times | Real, disclosed cost (~600 min worst case per task) — mitigated only by an explicit caller recommendation to raise `max_task_elapsed_minutes` to ≥630, not by any caching mechanism (three attempts at one each broke against this skill's isolation architecture) |
| Executing code at a historical commit exercises a since-rotated secret or since-removed dangerous code path | **Accepted, disclosed residual risk** — no documented sandboxing exists for Reviewer execution at base or head; this design increases blast radius (more historical states executed), named honestly |
| Builder narrowly makes only the known command pass without a genuine fix ("teaching to the test") | **Disclosed, not solved** |
| The Reviewer's second worktree isn't cleaned up (crash, interrupt) | Same residual risk every disposable local worktree already carries |

## Observability

| Signal | What's measured |
|--------|-------------------|
| `regression_gate_result` (per dispatch) | Whether the gate ran and its outcome for that specific dispatch |
| Findings raised under condition 6 / the inconclusive path | Visible in the completion report via existing, unmodified mechanisms — greppable via the fixed `"regression_gate: "` evidence prefix (Fix 4) |

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 0 | `skills.yaml` only (never `composition_contracts.yaml` directly): `repro_command` on `bug_diagnosis_report`'s `fields` AND `payload_types`; `regression_gate` on `implementation_task`'s `fields` only; regenerate via `make generate`; update pinned contract-field tests | None — optional/additive |
| 1 | `skills/loop-task-implementer/workflow/reviewer.md`: new "Regression gate" subsection (Fix 2, corrected regex in Fix 1), Blocking-standard condition 6 (Fix 3), the inconclusive-`NEEDS_EVIDENCE` convention with the fixed `"regression_gate: "` evidence prefix (Fix 4) — **no schema changes to the finding output, no new state-schema.yaml field**, only prose | None — documentation |
| 2 | `skills/loop-task-implementer/workflow/orchestrator.md`: the explicit doubled per-dispatch budget, the per-generation (both-lens) cost statement, and the numeric `max_task_elapsed_minutes ≥ 630` recommendation in §3 (Fix 6) | None — additive |
| 3 | `skills/loop-task-implementer/workflow/builder.md`: Fix 9's consuming behavior | None — additive |
| 4 | `skills/bug-diagnosis/`: when/how to populate `repro_command`, including validation | None — additive |
| 5 | `docs/skill-framework/shared/cross-skill-escalation.md`: rows 138 and 199 | None — documentation only |

No feature flag: every piece is optional/additive by construction.

## Open questions

- **Accepted residual risk — test-runner extensibility as a code-execution vector** (`conftest.py`,
  Makefile recipe bodies, npm lifecycle hooks). No command-shape validator can close this.
- **Accepted residual risk — no documented sandboxing/credential scope for Reviewer execution**, at base
  or head; this design increases blast radius by executing more historical states.
- **Accepted, disclosed limitation — external-service (DB/queue) isolation** has no concrete mechanism.
- **Accepted, disclosed limitation — "teaching to the test"** from Builder visibility into the exact gate
  command.
- **Unvalidated assumption — the 60-minute doubled per-dispatch budget figure** is not grounded in a
  measured baseline for this repository's actual dependency-install/test-suite runtime.
- **Real, disclosed cost, not a claim of closure — the per-task ceiling.** Worst case is ~600 minutes
  (30 min initial Builder dispatch + 4 generations × 120 min Reviewer time, both lenses, no caching +
  3 × 30 min Builder remediation); callers are told to set `max_task_elapsed_minutes ≥ 630` explicitly.
  This is honest arithmetic against
  a real, expensive mechanism — not a smaller number made to work via an optimization, after three
  attempts at exactly that each broke against this skill's isolation architecture.

Retracted from revision 3: the claim that an unresolved inconclusive gate outcome is "always a lifecycle
blocker requiring explicit human resolution." That claim had no real enforcement behind it. What Condition
4 actually required — visibility, never silent satisfaction — is delivered by existing, unmodified
mechanisms (Fix 4), which is a real but narrower guarantee than revision 3 claimed.

Retracted from revision 4: the claim that Orchestrator-side dispatch scoping lets the Reviewer skip the
base-commit half on a rerun without violating isolation. Two independent round-4 reviewers found this
still relayed a prior generation's judgment into a "fresh" Reviewer session. Revision 5 drops the shortcut
entirely rather than attempting a fourth fix to the same mechanism.
