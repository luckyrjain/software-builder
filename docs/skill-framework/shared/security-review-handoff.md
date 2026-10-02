# Security review → executor handoff (shared)

**Normative.** Reference doc for the `security-review → loop-task-implementer` escalation declared in
[cross-skill-escalation.md](cross-skill-escalation.md) (forward table, "A vulnerability finding has a
concrete, fixable code-level remediation and is not rotation-requiring" row; reverse table's matching
entry). That table has no room for this content — the real forward table is exactly 4 columns, the real
reverse table exactly 3 — so this doc holds the selection bar, the classification function's documented
contract, the envelope-population mapping, and the gitleaks-reuse disclosure, linked from the escalation
row itself.

## Selection bar

Not every `security_review_report` finding becomes a `loop-task-implementer` task. A finding qualifies for
this handoff only when **all** of the following hold:

1. **Severity** is `Critical`, `High`, or `Medium` (the exact verdict vocabulary
   [security-review's report format](../../../skills/security-review/reference/report-format.md) uses in
   its per-category `Severity` column — case-sensitive match). `Low` and `—` never qualify.
2. The finding's `Recommendation` cell names a **concrete, code-level action** (a fix the Builder could
   actually make in the current source), not a vague "investigate further" or a non-code action (e.g. "add
   a WAF rule", "update the on-call runbook").
3. `classify_security_finding` (see below) returns `QUALIFYING` for the finding's `Recommendation` text and
   severity — **not** `ROTATION_REQUIRED` and not `NOT_QUALIFYING`.

A finding that fails any one of these stays in the report for a human to read; it is never silently
dropped, and it never becomes an autonomous task by default.

## `classify_security_finding`

The real, single, consistently-applied classification mechanism for this handoff. Implemented at
[`skills/loop-task-implementer/scripts/classify_security_finding.py`](../../../skills/loop-task-implementer/scripts/classify_security_finding.py)
and tested at
[`skills/loop-task-implementer/tests/test_classify_security_finding.py`](../../../skills/loop-task-implementer/tests/test_classify_security_finding.py).
This doc cites that function's contract; it does not re-derive its logic in prose — read the module
docstring and tests for the authoritative behavior.

- **Signature:** `classify_security_finding(recommendation_text: str, severity: str) -> Literal["QUALIFYING", "ROTATION_REQUIRED", "NOT_QUALIFYING"]`
- **Pure function** — no I/O, no network, no file access, deterministic.
- **Fail-closed, always toward `ROTATION_REQUIRED`** on any ambiguous, malformed, `None`, or empty input —
  this is the single most important safety property of this function. It never fails open toward
  `QUALIFYING`.
- This function is a **strong, fail-closed first gate**, not the structural backstop itself. Its own
  keyword/severity heuristic is deliberately simple and conservative, and is known to be evadable by
  ordinary paraphrase (e.g. "Request a new value from the identity provider and update the config"
  describes rotation with no keyword overlap and classifies `QUALIFYING`) — this is a disclosed,
  documented limitation, not a silently-accepted gap. **Blocking-standard condition 7** in
  [`workflow/reviewer.md`](../../../skills/loop-task-implementer/workflow/reviewer.md) is the independent
  downstream backstop for exactly this case: it fires on the resulting task's own `scope`/
  `acceptance_criteria` content, regardless of whether this function was ever called, called correctly, or
  evaded.
- The **real** structural backstop against autonomous rotation is independent of this function entirely:
  the Builder has no code path to any live external credential-management system (a cloud provider's IAM,
  a secrets vault, a CI/CD secret store) anywhere in this framework, today. That is a true capability
  absence, not a convention this function enforces. `classify_security_finding` is a strong gate layered on
  top of that real absence, not a substitute for it.

## Envelope-population mapping

A qualifying finding (or merged group of qualifying findings — see Composition algorithm below) is
authored into the real, existing legacy `implementation_task` envelope (the 15-field schema a human or the
Orchestrator populates directly, per B6's own confirmed "legacy bypass, cite the real fields" precedent —
no new typed artifact, no `composition_contracts.yaml`/`skills.yaml` registration needed). Each field is
populated as follows:

| Field | Population rule |
|-------|-------------------|
| `task_id` | Generated per this skill's existing task-id convention — no finding-specific rule. |
| `scope` | The finding's category plus its file/symbol citation, **merged across the finding's own collision group**. A collision group is formed when EITHER (a) two findings share the same file AND have overlapping or adjacent line ranges, OR (b) two findings name the same symbol across different files — never on bare file co-membership alone (two findings merely sharing a large file, at unrelated lines, with no shared symbol, stay separate tasks). |
| `acceptance_criteria` | The finding's `Recommendation` text, **re-redacted per [safe-output.md Rule 5](safe-output.md#rule-5-pii-secret-redaction-in-rendered-output) at copy time** — Rule 5's redaction obligation in `report-format.md` is scoped to the `Evidence` column only, so `Recommendation` text is not assumed already clean and must be redacted again here. For a finding whose category is Injection, SSRF, or AuthZ-bypass, `acceptance_criteria` additionally states an explicit requirement that the fix include a negative test proving the specific vulnerability is closed — not merely "existing suite green." |
| `request` | A synthesized trigger phrase: `"Fix the {category} finding in {file/symbol} per security-review's own recommendation"` (the same template as the escalation row in `cross-skill-escalation.md`). |
| `repo_root` / `target` | The file/symbol path taken from the finding's own `Evidence` column. |
| `level_hint` | Same default as any legacy-envelope task — no finding-specific rule. |
| `specialist_inputs` | Carries an explicit `security_origin: true` marker, so a human or the Orchestrator reading the task later knows it originated from this handoff. |
| `test_framework_hint` / `run_tests` | `run_tests: true` by default, same as any code-change task. The security-specific negative-test requirement lives in `acceptance_criteria` above, not as a separate field. |
| `max_files_per_run` | A concrete absolute value: **3** for a Secrets finding whose evidence suggests a pattern recurring across files; **2** otherwise. (Not a "+1 from the ordinary default" — the legacy-envelope-bypass path skips `implementation_plan.py`'s own planning-derived `estimated_scope` computation entirely, so there is no baseline to offset from.) |
| `deadline` / `session_token_budget` / `output_dir` | Same defaults as any legacy-envelope task — no finding-specific rule. |
| `regression_gate` | `null`. `regression_gate` is for a bug-diagnosis-originated task whose confirmed repro command fails at the base commit for the diagnosed root cause (see [`skills/loop-task-implementer/workflow/reviewer.md`](../../../skills/loop-task-implementer/workflow/reviewer.md) §Regression gate): the Reviewer only treats the gate as satisfied when the command fails at the review-time merge-base (the package's `Base commit`), that failure matches `regression_gate.root_cause_summary`, and the command then passes at head. A security finding is not a bug-diagnosis repro and carries no `root_cause_summary`. The required negative test does not exist at the base commit (the Builder writes it as part of the fix) and its path is not known at dispatch, so a command naming it would fail at base for the wrong reason (`base_failure_matches_root_cause: false`, e.g. file or test not found) and raise a `NEEDS_EVIDENCE` finding (evidence prefix `"regression_gate: "`) on every review dispatch, plus the doubled Reviewer wait budget and the `≥ 630`-minute task ceiling recommendation in `orchestrator.md` §3. The negative-test requirement is carried by `acceptance_criteria` above and enforced by the Reviewer's ordinary Blocking-standard condition 1 (an explicit acceptance criterion is violated), not by this field. Never populate it with a raw `curl`/HTTP-client line either: `validate_repro_command` ([`skills/bug-diagnosis/workflow/repro.md`](../../../skills/bug-diagnosis/workflow/repro.md)) would reject it and the gate would silently downgrade to `null`. |

`app_run` is the envelope's 16th field (added after this handoff was designed); this handoff does not
populate it and leaves it at its ordinary default — a security-finding-derived task has no app-run/UI
verification requirement of its own.

None of these fields ever carry the raw, un-redacted `review_target` excerpt the underlying finding's
`Evidence` cell quoted.

## Composition algorithm for a merged (multi-finding) task

When two or more qualifying findings fall into the same collision group (see `scope` above), they are
merged into **one** task, not dispatched as separate, potentially racing tasks against overlapping code.
The merge itself is a **human/Orchestrator-applied convention, not code-enforced** — whoever authors the
handoff applies the collision-group trigger and the composition rule below by hand; there is no validator
that rejects an incorrectly-merged or incorrectly-split group. State this honestly; do not describe it as
"structural" or "by construction."

- `scope` and `acceptance_criteria` each become a **bulleted list**, one entry per sub-finding.
- Each entry is tagged by its own `finding_id`.
- Each entry is independently re-redacted per Rule 5 at copy time (the group is not redacted once as a
  whole — each sub-finding's text is redacted on its own).
- The negative-test requirement (Injection/SSRF/AuthZ-bypass) is **unioned** across the group: present in
  the merged task if **any** sub-finding's category requires it, even if others in the group don't.

## Rotation-requiring and non-qualifying findings

`classify_security_finding` never returns a value that maps to an envelope-population path for
`ROTATION_REQUIRED` or `NOT_QUALIFYING`. A rotation-requiring finding only ever reaches a human via the
report's own existing rendering — it is never authored into an `implementation_task`, autonomous or
otherwise, under any `allowed_actions`/`autonomous_merge_authorized` grant. No skill in this framework has
visibility into or a safe rollback path for live external credential systems, and this handoff does not
change that.

## Gitleaks-reuse disclosure

A code-level fix that removes a hardcoded secret from current `HEAD` does not remove that secret from the
repository's git history — every prior commit that already contains it in plaintext stays exposed for as
long as that history exists, independent of how clean the resulting PR's diff looks. This handoff does not
attempt history-scrubbing (e.g. a `git filter-repo`/BFG-style rewrite); that is an explicit, named,
human-only residual outside this handoff's scope.

The existing, already-active `gitleaks` CI gate (the `gitleaks` job in
[`.github/workflows/secret-scan.yml`](../../../.github/workflows/secret-scan.yml)) is the ongoing,
reused protection against this: it scans commit-by-commit history, not just the final tree, so a secret
introduced in any historical commit within its scan range continues to be flagged on every subsequent PR
touching that range. A human must still separately decide whether full history-scrubbing is warranted for
a given exposed secret — a clean current-`HEAD` diff must never be read as "the exposure is fully
resolved."
