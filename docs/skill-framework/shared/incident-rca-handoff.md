# Incident RCA → executor handoff (shared)

**Normative.** Reference doc for the `incident-rca → loop-task-implementer` escalation declared in
[cross-skill-escalation.md](cross-skill-escalation.md) (forward table, "A Preventive action is a concrete,
code-level fix with no existing task/branch" row; reverse table's matching entry). That table has no room
for this content — the real forward table is exactly 4 columns, the real reverse table exactly 3 — so this
doc holds the selection bar, the classification function's documented contract, the target-validation
contract, the envelope-population mapping, the target-discovery rule, the Reviewer's condition 9 contract,
and the disclosed residuals, linked from the escalation row itself.

**Distinct from the existing task-branch-regression row.** The reverse table already has a row,
"incident-rca confirms a regression tied to a task branch → loop-task-implementer dispatches Builder
remediation". That row fires when a regression traces back to a task `loop-task-implementer` **already
dispatched** (an existing `task_id`/branch). This handoff fires only when there is **no** such prior task.
The distinction is stated in both rows' Trigger text and is also a real, fail-closed parameter of
`classify_incident_preventive_action` (`has_existing_task_branch`), not prose alone.

## Selection bar

Not every row of an `incident_rca_report`'s `Preventive actions` table becomes a `loop-task-implementer`
task. A row qualifies only when `classify_incident_preventive_action` (see below) returns `QUALIFYING`,
i.e. **all six** of the following hold:

1. `action_source == "preventive"` — derived **structurally** from which real H2 heading
   (`## Corrective actions` vs `## Preventive actions`) the row appears under, never from a judgment about
   the row's "nature".
2. `priority` is exactly `P1` or `P2` (an allowlist, trimmed of surrounding whitespace only). `P0` is
   [report-template.md](../../../skills/incident-rca/report-template.md)'s documented Corrective signature;
   `p0`, `P0/P1`, `Sev0`, an empty string and `None` all fail closed, so a Corrective item misfiled under
   the Preventive heading is still caught.
3. `confidence`, taken from the **raw** Incident-scope `Confidence` cell: its first whitespace-delimited
   token must be exactly `HIGH` or `MEDIUM` (case-sensitive). The real gold shape is
   `HIGH — deploy + error spike + diff on failing path`, so the whole cell never equals a bare enum value;
   the appendix metadata's lowercase `confidence: high` is not accepted.
4. `incident_class` is exactly `Software defect` or `Deploy` — against the real **10-value** `Incident class`
   vocabulary (9 named classes — `Deploy`/`Dependency`/`Capacity`/`Configuration`/`Software defect`/
   `Data quality`/`Security`/`Network`/`Third-party` — plus the `Unknown` fallback), documented in
   `report-template.md`.
5. `has_existing_task_branch is False` — only the literal boolean `False`; `True`, `None` and everything
   else fail closed.
6. `action_text` passes the whole-cell keyword presence/absence check (below).

A row that fails any one of these stays in the report for a human to read; it is never silently dropped,
and it never becomes an autonomous task by default. Each qualifying row is its own single, independent task
— no merge group, no stepwise chain, no ordering dependency between rows of one RCA.

## `classify_incident_preventive_action`

Implemented at
[`skills/loop-task-implementer/scripts/classify_incident_preventive_action.py`](../../../skills/loop-task-implementer/scripts/classify_incident_preventive_action.py)
and tested at
[`skills/loop-task-implementer/tests/test_classify_incident_preventive_action.py`](../../../skills/loop-task-implementer/tests/test_classify_incident_preventive_action.py).
This doc cites the contract; read the module docstring and tests for the authoritative behavior.

- **Signature:**
  `classify_incident_preventive_action(action_source, priority, confidence, incident_class, action_text, has_existing_task_branch) -> Literal["QUALIFYING", "NOT_QUALIFYING"]`
- **Pure function** — no I/O, no network, no state, deterministic.
- **Fail-closed on every one of six independent axes**, toward `NOT_QUALIFYING`, including a non-`str`
  value on any str-typed argument. It never raises on malformed input and never fails open.
- **Axis 6 mechanics.** Preconditions: `action_text` is a `str`, `isascii()` (a Turkish dotted `İ` or a
  Cyrillic `а` would otherwise evade the exclusion side after lowercasing), at most 200 characters, and
  contains no character with code point below 32 or equal to 127. Then, on the lowercased text: tokens are
  `[a-z0-9]+`, so hyphen, underscore and apostrophe **split** tokens (`waf-rule` → `waf`, `rule`) while
  digits stay inside a token (`k8s`, `s3`, `ec2`). **Qualifying side — strict whole-token equality**
  against `{fix, fixes, fixing, patch, patches, patching, validate, validates, validating, validation,
  handle, handles, handling, correct, corrects, correcting, test, tests, testing}`; at least one must be
  present. **Exclusion side — stem-prefix, deliberately over-matching**: any token that starts with one of
  `{alert, dashboard, runbook, rollback, scal, autoscal, capacit, monitor, architect, refactor, redesign, decoupl,
  migrat, terraform, cloudformation, waf, firewall, iam, kube, k8s, helm, ingress, gateway, nginx, envoy,
  istio, ansible, pulumi, cdk, vpc, subnet, acl, dns, polic, s3, ec2, credential, secret, password, token}`
  excludes, plus the phrases `{network policy, security group, load balancer, roll back}` matched as
  substrings of the lowercased text with every non-alphanumeric run removed, so camelCase and concatenated
  spellings (`LoadBalancer`, `SecurityGroup`, `NetworkPolicy`, `loadbalancer`) are caught along with spaced,
  hyphenated and underscored ones. Substring matching already over-matched mid-word before squashing
  (`scroll back` contains `roll back`); squashing additionally ignores any separator, so `load.balancer` and
  `network/policy` match too. Known over-matches, accepted as the safe direction: `tokenizer`,
  `retry policy`, `helmet`, `scalar`, `gateway`.
- **No proximity window.** Unlike `classify_security_finding`'s multi-sentence `Recommendation` column, a
  Preventive `Action` cell is a short phrase, so a word-distance window is nearly vacuous.

## `validate_task_target`

Implemented at
[`skills/loop-task-implementer/scripts/validate_task_target.py`](../../../skills/loop-task-implementer/scripts/validate_task_target.py)
and tested at
[`skills/loop-task-implementer/tests/test_validate_task_target.py`](../../../skills/loop-task-implementer/tests/test_validate_task_target.py).

- **Signature:** `validate_task_target(repo_root: str | Path, target: str | None) -> str | None` — returns
  the original validated `target`, or `None` (drop it; the envelope falls back to service-name-only). A
  rejected string is **never** passed on.
- **Why:** Rule 5 redacts token shapes and PII only; it does nothing about paths or injected prose, and no
  repository code validates a handoff's `target`. (The only containment helper in
  `skills/loop-task-implementer/scripts` is `app_run.resolve_screenshot_path`, for screenshot output.)
- **Preconditions:** `target` is a non-empty ASCII `str`.
- **Symbol form:** `re.fullmatch(r"[A-Za-z_][\w.:$#-]{0,127}", target, re.ASCII)`.
- **Path form** (anything else containing `/`): reject absolute paths, backslashes, NUL bytes, any `..`
  segment and any input over 200 characters; resolve `(Path(repo_root) / target).resolve()`; require
  `is_relative_to(Path(repo_root).resolve())`, **not** equal to the repository root itself, and existing.
- **Neither form** (a bare `.env`, `.`) returns `None`.
- **Deny list**, casefolded, applied to both forms and to the **resolved** path relative to the root (so a
  symlink into `.git` is caught): `.git`/`.ssh`/`.aws`/`.kube`/`.docker`/`.gnupg` components; names `.env*`,
  `.netrc`, `.npmrc`, `.htpasswd`, `.pgpass`, `.pypirc`, `.git-credentials`, `kubeconfig*`, `credentials*`,
  `terraform.tfstate*`, `id_rsa*`, `id_dsa*`, `id_ecdsa*`, `id_ed25519*`; suffixes `.pem`, `.key`, `.p12`,
  `.pfx`, `.p8`, `.jks`, `.keystore`, `.tfvars`, `.tfstate`. A generic `id_*` prefix is not used (it
  would reject ordinary names such as `id_generator`). Each component is also checked with any `:line` or
  `#fragment` tail removed (the symbol regex admits both), so `server.pem:12` and `server.pem#L10` are denied. The same tail means a path-form hint on a real file
  (`src/handler.py:12`) fails the literal-existence check and is dropped: callers pass the bare path.
- **No subprocess, no git** — "exists in the worktree" is the only existence check.
- `repo_root` is **caller-supplied** (the repository the Orchestrator is already operating in), never
  derived from RCA text. A mismatch between the RCA's `service` and that repository is a human check at
  dispatch, disclosed rather than automated.

## Envelope-population mapping

A qualifying row is authored into the real, existing legacy `implementation_task` envelope (the 16-field
schema a human or the Orchestrator populates directly — the same "legacy bypass, cite the real fields"
precedent as C1 and C2; no new typed artifact, no `composition_contracts.yaml`/`skills.yaml` registration).
All 16 fields are addressed individually:

| Field | Population rule |
|-------|-------------------|
| `task_id` | Generated per existing convention, with the deterministic `preventive_action_id` (see axis-5 population below) as its suffix, so a re-dispatch of the same action derives the same `task_id`. |
| `scope` | `"{service}: {action_text}"`, where `action_text` has already passed axis 6's preconditions (a `str`, at most 200 characters, ASCII, no control character). The Preventive `Action` cell is untrusted data (per `incident-rca`'s own P0 guardrail); it is length-capped and control-character-free by those preconditions, and Rule 5 alone is the wrong control for an injected instruction phrase. |
| `acceptance_criteria` | (a) A mandatory, **synthesized** (not copied) clause: `"Include a passing regression test demonstrating the fix for: {action_text}"` — the gold example's Preventive table has only 3 columns (Action, Owner, Priority) and no `Notes` column, so the criteria cannot rely on a `Notes` cell. (b) The `Notes` cell **only if present**, [Rule-5](safe-output.md#rule-5-pii-secret-redaction-in-rendered-output) redacted and capped at 200 characters. (c) **No prose from the Executive summary** — it contains `symptom`, the same untrusted class as the flagged tables. Citation is by reference only (report identifier and `incident_window`, carried in `specialist_inputs`). |
| `request` | Synthesized trigger phrase `"Fix: {action_text} — preventive action from RCA for {service} {window}"` (the same template as the escalation row), built from the same validated `action_text`. |
| `repo_root` | **Caller-supplied** — the repository the Orchestrator is already operating in, never derived from RCA text. |
| `target` | Discovered best-effort (see §Target-discovery rule), passed through `validate_task_target`; on `None`, service-name-only. |
| `level_hint` | Same default as any legacy-envelope task. |
| `specialist_inputs` | Carries `incident_rca_origin: true` (the origin marker, and the key Reviewer condition 9 gates on); `incident_window` (the RCA's own `from`/`to`); `incident_report_ref` (a path, link or ID for the RCA report — the by-reference citation); and `preventive_action_id` (see below). |
| `test_framework_hint` | Left to whoever authors the handoff to discover per the repo's own build tooling: the `Makefile`'s `test` target, `package.json`'s `scripts.test`, `pytest.ini`/`pyproject.toml`'s test configuration, `tox.ini`, then CI config for an explicit test-invocation line. A hint for the Builder only; it is **not** copied into `regression_gate`. |
| `run_tests` | `true` — "each PR keeps tests green" is enforced by this skill's own existing, unmodified completion-gate discipline. |
| `deadline` | Same default as any legacy-envelope task, unchanged (one of the 3 genuinely generic fields). |
| `session_token_budget` | Same default, unchanged (generic). |
| `output_dir` | Same default, unchanged (generic). |
| `app_run` | Same default as any legacy-envelope task, unchanged — an RCA-derived task has no app-run/UI verification requirement of its own. |
| `max_files_per_run` | **2**, with a conditional bump to **3** when `action_text`'s tokens include a test-family token (`test`/`tests`/`testing`) **and** any non-test qualifying token (`fix`/`patch`/`validate`/`handle`/`correct` families) — the combined test-plus-fix shape. The bump fires on the gold example's own row ("Add regression test for transfer-money validation"), so 3 is the ordinary case for test-bearing rows, not a rare escape valve. |
| `regression_gate` | `null`. `regression_gate` is for a bug-diagnosis-originated task whose confirmed repro command fails at the base commit for the diagnosed root cause (see [`skills/loop-task-implementer/workflow/reviewer.md`](../../../skills/loop-task-implementer/workflow/reviewer.md) §Regression gate): the Reviewer only treats the gate as satisfied when the command fails at the review-time merge-base (the package's `Base commit`), that failure matches `regression_gate.root_cause_summary`, and the command then passes at head. An RCA preventive action is not a bug-diagnosis repro and carries no `root_cause_summary`, and the repo's general test command already passes at the base commit, so populating it would yield `base_test_result: UNEXPECTED_PASS` and a `NEEDS_EVIDENCE` finding (evidence prefix `"regression_gate: "`) on every review dispatch, plus the doubled Reviewer wait budget and the `≥ 630`-minute task ceiling recommendation in `orchestrator.md` §3. The regression-test requirement lives in `acceptance_criteria` (a) above, and "each PR keeps tests green" is already enforced by `run_tests: true` plus the completion gate. |

None of these fields ever carry raw, un-redacted log or evidence excerpts.

## Axis-5 population: a caller-applied convention, not code-enforced

`has_existing_task_branch` is an **explicit, fail-closed parameter** of the classifier; **its population is a
caller-applied lookup convention, not code-enforced.** Nothing in `workflow/orchestrator.md` or
`workflow/builder.md` invokes these lookups (this ticket does not change either file), so a caller can still
pass `False` without running anything. The parameter makes the distinction explicit and fail-closed at the
function boundary; it does not make the lookup enforced. This is the same family-level convention as C1's
and C2's own lookups.

The caller computes it **Orchestrator-side** (the run log and shared state are deliberately kept from the
Builder), passing `False` only when **both** lookups below affirmatively ran and returned nothing. Any lookup
error, or no SCM/run-log access, passes `None`.

- **(a) Provenance.** Extract the PR/MR references and SHAs the RCA already cites (Evidence matrix, Unified
  timeline, Recovery's `Mitigation` row, the Post-RCA `PR review` target row). RCA text may use GitLab-style
  `MR !482` or GitHub `#482`/PR-URL forms; extract both and resolve against the repository's own SCM. Check
  whether each maps to a `loop-task-implementer` task via the shared-state `workspace.working_branch` / `workspace.pull_request_id` / `workspace.pull_request_url` fields.
  A `Deploy` or `Software defect` RCA that cites **no** causative PR/MR is "provenance unknown" and is
  **not** `False`.
- **(b) Duplication.** Derive a deterministic
  `preventive_action_id = canonical_payload_digest({"incident_window": ..., "service": ..., "action_text": <whitespace-normalized>})[:12]`
  (the existing `scripts/registry/assessment_target.py` helper, the same reuse as C2's `dependency_chain_id`),
  use it as the deterministic `task_id` suffix, then look that `task_id` up in shared state. **Any existing
  state for it — including `COMPLETE` or `ESCALATED` — is `True`**, so a previously completed or escalated
  attempt is never silently re-run.

**No branch/PR marker convention exists.** Nothing in `builder.md` or `orchestrator.md` writes a task-ID
branch name, PR-body marker or commit trailer (the only trailers are `Checkpoint: implementation-complete` /
`Checkpoint: tests-passing`). Duplication detection therefore rests on the deterministic `task_id` plus the
shared-state lookup; any branch/PR search for the id is **best-effort only**. Duplicates remain possible when
no shared state exists — disclosed, not claimed closed. Reusing `orchestrator.md` §2's existing-branch check
alone would be vacuous: it matches a task's own freshly generated ID and names no marker location.

## Target-discovery rule

`incident-rca`'s report has no structured file/symbol field. Best-effort heuristic: scan the RCA's own
Executive summary, Conclusion and Causal chain sections for a backtick-quoted symbol or handler (after the
same Rule-5 redaction those sections require), then pass the result through `validate_task_target`. A
backtick-quoted symbol appears exactly once across the gold example's six section instances, so this usually
falls through to service-name-only. A discovered value is a **symbol**, not a path; nothing here resolves a
symbol to a file, which stays Builder-side judgment.

## Reviewer Blocking-standard condition 9

Declared in [`workflow/reviewer.md`](../../../skills/loop-task-implementer/workflow/reviewer.md) (the real
current max on `origin/main` before this ticket was 8, C2's; condition 9 is this ticket's). For any task whose
`specialist_inputs.incident_rca_origin` is `true`, a PR whose **actual changed-path list** — computed by the
Reviewer as `git diff --name-only --no-renames` against the base, never from task text — contains any path
matching `*.tf`, `*.tfvars`, `*.hcl`, `*.rego`, `terraform/**`, `cloudformation/**`, `helm/**`, `charts/**`,
`k8s/**`, `kubernetes/**`, `manifests/**`, `iam/**`, `policies/**`, `.github/workflows/**`, `.gitlab-ci.yml`,
`Jenkinsfile`, `.circleci/**`, `kustomization.yaml`, `cdk.json`, `Pulumi.*.yaml`, `Dockerfile*` or
`docker-compose*.yml` is itself Blocking-standard condition 9, regardless of passing tests or keyword
classification, and regardless of which lens(es) the dispatch runs.

- Patterns match at **any directory depth** (`infra/terraform/**`, `deploy/helm/**`). **False-block cost:**
  fixtures (`tests/fixtures/manifests/`) and application code in a directory merely named `iam/` or
  `policies/` escalate to a human — a safe-direction error.
- `--no-renames` ensures a rename out of `terraform/` is still seen.
- A finding under this condition is an ordinary `PROPOSED_BLOCKING` finding using the existing finding schema
  unmodified; its `evidence` must begin with the literal prefix `"incident_rca_infra: "` (mirroring condition
  6's `"regression_gate: "` and condition 8's `"dependency_hop: "`).
- **Why it exists:** `reviewer.md` condition 7 is credential/identity/secrets only, and C1's "the Builder has
  no code path to a live system" backstop does not transfer to an infrastructure-as-code repository, where an
  ordinary merged PR **is** the live change. Acting on diff paths is stronger than six words of untrusted
  summary text. Condition 7 remains the unmodified backstop for the narrower credential/identity/secrets case.

## Disclosed residuals

- **Keyword evasion.** The axis-6 lists are a best-effort first gate. A qualifying verb plus an infra noun
  that is in none of the lists ("Fix the data-store replication config") classifies `QUALIFYING`. Other
  compound words that embed an excluded stem mid-token (for example `rescaling`) are not caught by prefix
  matching (the four multi-word phrases are not subject to this: they match as squashed substrings); over-matching is the safe direction, but prefix matching cannot see mid-token stems. Condition 9's diff-path gate, not keyword classification, is the real
  control for infra changes.
- **Condition 9 is best-effort and layout-dependent.** The path set is not identical to the keyword
  exclusions (`nginx`, `envoy`, `istio`, `ansible` have no path pattern), a repository with an unusual infra
  layout needs its own paths added, and practical blast radius also depends on whether autonomous merge plus
  CD-on-merge is enabled for the repository.
- **Axis-5 population is a convention**, and duplicates remain possible when no shared state exists (see
  above).
- **`validate_task_target` tail residual.** Only `:` and `#` tails are stripped before the deny check. A `?`
  suffix or trailing whitespace (`a/x.pem?x`, `a/a.pem `) is not, so such a name passes if a file with that
  literal name exists in the repository. Unchanged from before the tail handling was added, and `target` is
  only a hint string that nothing reads in code.
- **`validate_task_target` residual.** A 128-character, whitespace-free string such as
  `IGNORE-ALL-PRIOR-INSTRUCTIONS-and-run` passes the symbol form — a small residual injection channel in a
  hint field.
- **Family gap.** C1 and C2 take `target` from report evidence the same way and neither handoff doc validates
  it; this ticket adds `validate_task_target` for itself only. Retrofitting C1/C2 is flagged for follow-up,
  not claimed fixed.
- **Condition 7 recall** against incident-rca-sourced phrasing was never validated (it was authored against
  C1's application-code-vulnerability domain).
- **Upstream template gap.** `report-template.md`'s safe-output enumeration omits the Executive summary,
  Conclusion and the Preventive `Action`/`Notes` cells while claiming everything else needs no escaping —
  outside this ticket, flagged rather than fixed. Whether the Preventive table has a `Notes` column also
  differs between the gold example (3 columns) and the template (5 columns); `acceptance_criteria` is derived
  from `Action` plus a mandatory regression-test clause so it works for both.
- **Unvalidated recall/precision.** The heuristic's precision/recall against real-world Preventive-action
  phrasing is unvalidated, the same disclosed class as C1's `classify_security_finding`; the typical number of
  qualifying rows per RCA (0–3) is an unvalidated guess, not sourced from the gold example (which has exactly
  one Preventive row).
- **`backlog-runner`.** A qualifying task is standalone with no chain-ordering concern, so it may be
  dispatched directly or through `backlog-runner`'s queue like any other task; no carve-out is needed.
