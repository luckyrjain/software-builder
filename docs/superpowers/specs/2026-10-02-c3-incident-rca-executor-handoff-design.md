# System Design Spec — C3: incident-rca → executor handoff

**Readiness: Ready with open questions**

## Revision history

**Revision 1** (initial): reused C1/C2's converged pattern, resolved the Corrective-vs-Preventive
scoping decision, and claimed the existing `reviewer.md` condition 7 plus a prose-level Trigger-column
distinction were sufficient to keep this ticket's new row separate from the existing task-branch-regression
row.

Round 1 adversarial review (Security Architect, SRE, Software Architect — all three, fresh, in parallel)
found one central defect from two independent angles, a second real blast-radius gap, and several factual
corrections. Fixed in **revision 2**:

- **The "no existing task/branch" distinction — the one thing this ticket exists to get right — had no
  code behind it, only prose** (Software Architect — the central finding, the identical "claimed
  structural, actually convention" pattern C1 round 1 and C2 round 1 each independently hit). Every other
  axis of `classify_incident_preventive_action` was explicit-input and fail-closed; this one wasn't even a
  parameter. **Fixed**: added `has_existing_task_branch: bool` as a required 5th-now-6th axis, fail-closed
  to `NOT_QUALIFYING` on `True` or any non-`False` value.
- **`action_source`'s own population step had no stated mechanism, and even a correctly-populated
  `action_source` can't catch an upstream report that misfiles a genuinely corrective item under the
  `Preventive actions` heading** (Security Architect, two-part finding). **Fixed**: `action_source` must
  be derived by structural lookup of which H2 heading the row appears under, never by independent human
  judgment about the row's "nature" — and a new `priority` axis fails closed to `NOT_QUALIFYING` whenever
  the row's own `Priority` cell is `P0` (report-template.md's own documented Corrective signature),
  regardless of which table it structurally came from.
- **The Executive-summary citation was treated as exempt from redaction, but it isn't** (Security
  Architect) — `report-template.md`'s own documented `symptom` field lands inside the Executive summary,
  and `symptom` is explicitly named elsewhere in that same template as the same untrusted-content class as
  the flagged tables. **Fixed**: the Executive-summary citation now gets the identical Rule-5 re-redaction
  the Notes-cell citation already had, no exemption.
- **The keyword-heuristic's "proximity window" framing was hand-wavy, and a structural mismatch from the
  precedent it claimed to mirror** (Security Architect) — `classify_security_finding`'s free-text
  `Recommendation` column is multi-sentence; this design's own `action_text` is a short table cell, where a
  word-distance window is nearly vacuous. **Fixed**: dropped the window framing entirely; axis 6 is now a
  concrete, whole-cell keyword-presence/absence check with named keyword lists, no window.
- **`reviewer.md` condition 7's real scope (credential/identity/secrets) doesn't cover the architecture
  review's own motivating example (a WAF rule, an IAM policy), and C1's "Builder has no path to a live
  system" backstop doesn't transfer to an infra-as-code repository, where an ordinary PR IS a live
  production change** (Security Architect — the second real gap, larger blast radius than anything C1 or
  C2 had to consider). **Fixed**: axis 6's exclusion list now explicitly excludes infra-as-code/
  network-control-plane keywords (`terraform`, `cloudformation`, `waf`, `firewall`, `iam`, `network
  policy`, `security group`) and the broad `architecture` category itself — narrowing qualification to
  the genuinely code-level subset (tests, validation, targeted fixes, documentation) rather than leaning on
  condition 7 alone for a risk class it was never scoped to cover. The residual (a keyword exclusion is
  itself evadable) is disclosed honestly, not claimed solved.
- **`max_files_per_run: 2`'s justification didn't hold for the "architecture"-class actions the
  architecture review itself put in scope** (Software Architect, SRE, independently convergent) — now
  moot for the excluded `architecture` category, but SRE's own concrete counterexample (a combined
  test-addition-plus-fix action spanning 3 files) still stood for the narrowed, legitimately-qualifying
  subset. **Fixed**: added a conditional bump to 3 when `action_text` names both a test keyword and a
  fix/validation keyword together, mirroring C1's own conditional-bump structure for its Secrets
  sub-case, rather than asserting one flat number covers every qualifying shape.
- **The Capacity section's "typically 0-3, per the gold example's own 2-3 rows" claim was false** (SRE,
  verified by direct read of `gold-rca-excerpt.md`) — the real gold example has exactly **1** Preventive
  row. **Fixed**: corrected the citation and reframed the 0-3 estimate as this design's own unvalidated
  guess, not sourced from the gold example.
- **Three citation/count corrections** (Software Architect, SRE): the existing task-branch-regression row
  is at line ~181, not 183; the real `Incident class` vocabulary is 10 enumerated values (9 named classes
  plus the `Unknown` fallback), not 9, and it's documented in `report-template.md`, not
  `cross-skill-escalation.md` as revision 1 mistakenly cited.
- **The `target` field's Open Question was thinner than it needed to be** (SRE) — **fixed** with a
  concrete, cheap discovery rule: scan the RCA's own Executive summary/Conclusion/Causal chain sections for
  a backtick-quoted symbol/handler (best-effort heuristic — see round-3 correction in Data model) before falling back to
  service-name-only, applying the same Rule-5 redaction now required for those sections.
- **One honesty-consistency gap** (Security Architect): added one sentence disclosing that condition 7's
  recall against incident-rca-sourced phrasing is unvalidated, matching the disclosure standard applied
  everywhere else in this design.
- **The Epic-C precedent note speculated about C4's own upstream-report shape**, a claim this design has
  no basis to make (Software Architect) — **fixed**, trimmed to generic guidance.
- **One clarifying sentence on `backlog-runner`** added (SRE) — this ticket's tasks are standalone, no
  chain-ordering concern, so no carve-out is needed, stated explicitly rather than left silent.

Round 2 adversarial review (SRE and Software Architect completed; Security Architect's round-2 agent
was killed by an API rate limit and is re-run against revision 3) confirmed the central defect
(`has_existing_task_branch` as a real, fail-closed axis) genuinely closed, all 16 envelope fields still
individually addressed, and the C4 speculation trimmed. Fixed in **revision 3**:

- **`refactor` was a qualifying keyword, which defeated the architecture exclusion** (SRE) — a concrete,
  natural phrasing ("Refactor the payment service to decouple it from the notification service") matched a
  qualifying keyword and no excluded one. **Fixed**: `refactor` moved from the qualifying list to the
  exclusion set, with `redesign`/`decouple`/`migrate` added; residual evasion via a still-qualifying keyword
  disclosed.
- **The `target`-discovery rule's "gold example convention" framing was empirically unsupported** (SRE) —
  a backtick-quoted symbol appears once across the gold example's six section-instances. **Fixed**: reframed
  as a best-effort heuristic that usually falls through to service-name-only.
- **Multi-word exclusion phrases (`network policy`, `security group`) had no stated matching mechanism**
  (Software Architect) — "whole-word" has no defined meaning for a two-word phrase. **Fixed**: single words
  match as whole tokens via the same word regex as `classify_security_finding.py`; the two phrases match as
  whitespace-collapsed case-insensitive substrings; no qualifying keyword present means `NOT_QUALIFYING`.
- **The claim that condition 7 clearly does not cover an IAM policy was debatable** (Software Architect) —
  IAM is arguably inside condition 7's "identity-management system" wording. **Fixed**: softened; axis 6
  excludes `iam` conservatively either way.

Round 2's Security Architect review (re-run after a rate-limit failure) found three real defects and
several smaller ones against revision 3. Fixed in **revision 4**:

- **`has_existing_task_branch` had no population mechanism** (High) — a bare boolean relocates the
  unenforced judgment the doc itself named as round 1's central defect, and the obvious reuse of
  `orchestrator.md` §2's existing-branch check is vacuous because it matches a task's own freshly generated
  ID. **Fixed**: Orchestrator-side provenance lookup plus a deterministic `preventive_action_id`
  duplication lookup, `None` on any failure, only literal `False` passes.
- **The axis-6 matcher was fail-open on the exclusion side** — hyphen and apostrophe inside the token class
  (`waf-rule`, `IAM-policy`, `WAF's`), underscore/hyphen phrase variants, and inflections (`alerting`,
  `autoscaling`, `Refactoring`) all evaded it. **Fixed**: `[a-z]+` tokenization, stem-prefix exclusion
  matching, `[\s_-]+` phrase normalization, a larger exclusion term list, strict qualifying side.
- **"The Reviewer's ordinary review is the backstop" overclaimed** — `reviewer.md` has no condition that
  fires on a live-infra PR, and condition 7 is credential/identity/secrets only. **Fixed**: a deterministic
  diff-path gate, Blocking-standard **condition 9**, reversing revision 3's "no condition 9 needed".
- **`target` was never validated** (Medium) — Rule 5 redacts token shapes and PII, not paths or injected
  prose, and no repository code validates `target`. **Fixed**: `validate_task_target`; family gap with
  C1/C2 disclosed.
- **Smaller**: `priority != "P0"` was a fail-open denylist (now allowlist `{P1, P2}`); the `confidence`
  extraction rule was missing and the gold shape (`HIGH — ...`) would never match (now first token of the
  Incident-scope cell); the Preventive `Action` cell had no stated untrusted-data treatment (length cap,
  control-character rejection); the gold Preventive table has no `Notes` column (`acceptance_criteria` now
  derived from `Action` plus a mandatory regression-test clause); the "Executive summary headline" was
  undefined and is replaced by a by-reference citation; the `max_files_per_run` bump lists were misaligned.

A narrow confirmation pass on revision 4 (one agent, all three lenses, with the matcher run in a
scratch script) closed the condition-7/8 numbering check (real max confirmed 8), the `canonical_payload_digest`
reuse and the 16-field count, and found two blocking punch-list items plus smaller ones. Fixed in
**revision 5** (this revision):

- **The branch/PR marker claim was false** (blocking) — nothing in `builder.md` or `orchestrator.md` writes a
  task-ID branch name, PR-body marker or commit trailer, and `orchestrator.md` §2 names no marker location.
  **Fixed**: claim dropped; duplication detection rests on a deterministic `task_id` plus shared-state lookup
  (any existing state, including `COMPLETE`/`ESCALATED`, is `True`), branch/PR search best-effort; "real,
  code-enforced axis" reworded to "explicit, fail-closed parameter with a caller-applied population
  convention"; SCM mapping stated (GitLab `MR !N` and GitHub `#N`/URL forms).
- **`validate_task_target` had bypasses** (blocking) — the deny list ran on path form only (bare `server.pem`,
  `terraform.tfvars` passed as symbols), not on the resolved path (a symlink into `.git` passed), not
  casefolded (macOS), accepted the repo root itself, left a bare `.env` in an unspecified branch, used `^...$`
  (trailing newline) and Unicode `\w`. **Fixed**: deny list on both forms and the resolved path, casefolded,
  `is_relative_to` and not-equal-to-root, neither-form returns `None`, `fullmatch` with `re.ASCII`, wider deny
  list (`.p12`, `.pfx`, `.netrc`, `.npmrc`, `.ssh`, `.aws`, `*.tfvars`), path-form length cap.
- **Dead `k8s` stem and Unicode evasion** — `[a-z]+` split `k8s`; `İAM`/Cyrillic `а` evaded the exclusion
  side. **Fixed**: `[a-z0-9]+` tokenization, `isascii()` precondition, defined control-character check,
  `s3`/`ec2`/`kube` stems added.
- **Qualifying side had no inflections** — "Add unit tests for X" and "Fixing null check" were
  `NOT_QUALIFYING`, the largest recall loss. **Fixed**: inflected forms added as exact tokens.
- **Condition 9 under-specified** — path anchoring, rename evasion, lens sentence, and path/keyword
  mismatch. **Fixed**: any-depth matching with the false-block cost stated, `--no-renames`, the lens
  sentence, more CI/IaC paths.
- **Post-Builder correction (implementation found a design error)** — the design claimed the exclusion stems caught `autoscaling`, but prefix matching on `scal` does not match a token starting with `auto`; the Builder followed the spec literally, flagged it, and the test list had named `autoscaling` as a covered case. **Fixed**: `autoscal` added to the exclusion stem list. Residual of the same class: other compound words that embed an excluded stem mid-token (for example `rescaling`) are not caught by prefix matching; over-matching is the safe direction but prefix matching cannot see mid-token stems, disclosed.
- **Cleanups**: stale `P0` wording now says the `{P1, P2}` allowlist; "(this revision)" labels reduced to the
  latest; the `max_files_per_run` bump list aligned with the qualifying families.

The third of eight Epic-C "analysis skill → executor" tickets — reuses C1/C2's own converged pattern
(legacy-envelope bypass, a real tested classification function, an independent downstream Reviewer
backstop) wherever it applies unmodified, and now backs its central "no existing task/branch" distinction
with an explicit, fail-closed classification parameter (its population is a caller-applied lookup
convention, the same family-level convention as C1/C2, not code-enforced), a narrowed qualification bar, and
a deterministic diff-path Blocking-standard condition for the infra subset.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| New `cross-skill-escalation.md` row pair (forward 4-column, reverse 3-column) | Declares the handoff: a qualifying, freestanding `Preventive actions` row (no existing task branch) → `loop-task-implementer` | Documentation only | Distinguished explicitly from the existing line-~181 row (see APIs) |
| New reference doc: `docs/skill-framework/shared/incident-rca-handoff.md` | Holds the selection rule, `classify_incident_preventive_action`'s contract, the envelope-population mapping | Linked from the new escalation row, mirroring C1's `security-review-handoff.md`/C2's `dependency-upgrade-handoff.md` convention exactly | Same file-naming/location convention, now three times established |
| `classify_incident_preventive_action(action_source, priority, confidence, incident_class, action_text, has_existing_task_branch) -> Literal["QUALIFYING", "NOT_QUALIFYING"]` (new, real, tested function; round 4: `has_existing_task_branch` is `bool | None`, only literal `False` passes) | Whole-cell keyword presence/absence check (round-2 fix: no proximity window — see APIs), mirroring `classify_security_finding`'s own free-text-input shape but adapted to a short table cell rather than multi-sentence prose | Lives at `skills/loop-task-implementer/scripts/classify_incident_preventive_action.py` | Fail-closed on every one of **6** independent axes (round-2: was 4) — see APIs |
| `validate_task_target(repo_root, target) -> str | None` (new, real, tested function, round 4) | Rejects any non-symbol, non-contained, non-existent or sensitive `target` before it reaches the envelope | Lives at `skills/loop-task-implementer/scripts/validate_task_target.py` | Closes Security Architect's Medium `target`-validation finding; family gap with C1/C2 disclosed |
| New Blocking-standard **condition 9** in `workflow/reviewer.md` (round 4) | Deterministic diff-path gate on `incident_rca_origin: true` tasks (see APIs) | `skills/loop-task-implementer/workflow/reviewer.md`, same additive shape as C1's condition 7 and C2's condition 8 | Replaces revision 3's overclaimed "the Reviewer is the backstop" |
| The envelope population rule (documented in the new reference doc) | Maps a qualifying Preventive action into the real, existing legacy `implementation_task` envelope, all 16 fields individually addressed | Reuses C1/C2's "legacy bypass, cite the real 16 fields, no blanket-clause regression" precedent | See Data model |

**Confirmed untouched**: `workflow/orchestrator.md`, `workflow/builder.md`, `workflow/lifecycle-gate.md`,
`scripts/validate_loop_lifecycle.py`, `reference/state-schema.yaml`,
`scripts/registry/composition_contracts.yaml`, `skills.yaml`, and `skills/backlog-runner/*`.
**`workflow/reviewer.md` is touched (round 4)**: it gains one additive Blocking-standard condition 9, the same
shape as C1's condition 7 and C2's condition 8. Revision 1 claimed it needed no change because condition 7
covers the case; round 2 corrected that condition 7's real scope is credential/identity/secrets only (it does
not cover a WAF rule or infra-as-code), and round 4 found that keyword exclusion at axis 6 is not a real
control for infra changes either, because the Reviewer's ordinary review has no condition that fires on
"this PR is a live infra change". Condition 9 acts on the PR's actual changed paths instead. Condition 7
remains the unmodified backstop for the narrower credential/identity/secrets case. The condensed
Blocking-standard prose in `SKILL.md` is already stale for conditions 6 to 8 (pre-existing, disclosed by C1
and C2); this ticket does not change that.

## APIs

| Field / function | Contract | Consumer(s) | Notes |
|--------------------------|----------|-------------|-------|
| New forward row | `"A Preventive action is a concrete, code-level fix with no existing task/branch (per classify_incident_preventive_action — see [incident-rca-handoff.md](incident-rca-handoff.md))"` \| `incident-rca → loop-task-implementer` \| `incident_rca_report` (incident class, confidence, the qualifying Preventive-action row's own Action/Owner/Priority/Notes cells) \| `"Fix: {action_text} — preventive action from RCA for {service} {window}"` | Whoever authors the handoff | **Distinguished explicitly from the existing row** (`cross-skill-escalation.md` line ~181, round-2 citation fix — was miscited as ~183, "incident-rca confirms a regression tied to a task branch"): that row fires when a regression traces back to a task `loop-task-implementer` already dispatched (an existing `task_id`/branch); this new row fires only when there is no such prior task. The two rows' own Trigger-column text states this distinction, AND (round-2 fix) the classification function itself now takes `has_existing_task_branch` as a required, fail-closed input — the distinction is no longer prose-only |
| New reverse row | `"incident-rca's own Preventive actions table contains a qualifying, freestanding code-level fix"` \| `loop-task-implementer receives the incident class, confidence, and the one qualifying action's own citation` \| `"Fix: {action_text} — preventive action from RCA for {service} {window}"` | Whoever authors the handoff | Mirrors C1/C2's reverse-row, skill-as-subject phrasing |
| `classify_incident_preventive_action(action_source: Literal["corrective", "preventive"], priority: str, confidence: str, incident_class: str, action_text: str, has_existing_task_branch: bool | None) -> Literal["QUALIFYING", "NOT_QUALIFYING"]` | Pure function, no I/O. Fail-closed to `NOT_QUALIFYING` unless **all six** hold: (1) `action_source == "preventive"` — exact string, **structurally derived from which real H2 heading (`## Corrective actions` vs `## Preventive actions`) the row appears under**, never a judgment call about the row's "nature"; any other/malformed value is `NOT_QUALIFYING`. (2) `priority in {"P1", "P2"}` — an exact-match **allowlist** read from the row's own `Priority` cell, trimmed of surrounding whitespace only (round-4 fix, Security Architect: revision 3's `priority != "P0"` denylist was fail-open — `p0`, `P0/P1`, `Sev0`, `Critical`, an empty string and `None` all passed, contradicting this doc's own "malformed fails closed" claim, and it is the very cross-check meant to catch a misfiled Corrective item). `P0` is `report-template.md`'s documented Corrective signature, so it, and everything else outside the allowlist, fails closed even if `action_source` was somehow wrong. (3) `confidence` — **source and extraction rule stated (round-4 fix, Security Architect)**: the Incident-scope table's `Confidence` cell; take its first whitespace-delimited token (the real gold shape is `HIGH — deploy + error spike + diff on failing path`, so the whole cell never equals a bare enum value); that token must equal `"HIGH"` or `"MEDIUM"` exactly, case-sensitive; the appendix metadata's lowercase `confidence: high` form is not accepted; anything else is `NOT_QUALIFYING`. (4) `incident_class in {"Software defect", "Deploy"}` — exact match against the real **10-value** `Incident class` vocabulary (9 named classes — `Deploy`/`Dependency`/`Capacity`/`Configuration`/`Software defect`/`Data quality`/`Security`/`Network`/`Third-party` — plus the `Unknown` fallback; documented in `skills/incident-rca/report-template.md`). (5) `has_existing_task_branch is False` — only the literal boolean `False` passes; `True`, `None` and every other value fail closed. **Population mechanism (rounds 4-5, Security Architect's High finding, narrowed in round 5 after the confirmation pass)**: the caller computes it **Orchestrator-side** (the run log and shared state are deliberately kept from the Builder) and passes `False` only when **both** lookups affirmatively ran and returned nothing; any lookup error, or no SCM/run-log access, passes `None`. **Honest scope (round 5)**: nothing in `orchestrator.md` invokes these lookups and this design does not change `orchestrator.md` or `builder.md`, so population is a caller-applied convention, the same family-level convention as C1's and C2's own lookups — a caller can still pass `False` without running anything. The parameter makes the distinction **explicit and fail-closed at the function boundary**; it does not make the lookup code-enforced. Revision 4 also claimed a `preventive_action_id` "embedded in the branch/PR marker"; confirmation-pass grep showed nothing in `builder.md` or `orchestrator.md` writes any task-ID branch name, PR-body marker or commit trailer (the only trailers are `Checkpoint: implementation-complete` / `Checkpoint: tests-passing`), so that claim is **dropped**. The axis answers two questions, so there are two lookups: **(a) provenance** — extract the PR/MR references and SHAs the RCA already cites (Evidence matrix, Unified timeline, Recovery's `Mitigation` row, the Post-RCA `PR review` target row; RCA text may use GitLab-style `MR !482` or GitHub `#482`/PR URLs, so extract both forms and resolve against the repository's own SCM) and check whether each maps to a `loop-task-implementer` task via the shared-state `working_branch`/`pr_url` fields; a `Deploy` or `Software defect` RCA that cites **no** causative PR/MR is "provenance unknown" and is **not** `False`. **(b) duplication** — derive a deterministic `preventive_action_id = canonical_payload_digest({"incident_window": ..., "service": ..., "action_text": <whitespace-normalized>})[:12]` (the existing `scripts/registry/assessment_target.py` helper, same reuse as C2's `dependency_chain_id`; confirmed `canonical_payload_digest(payload) -> str` takes a JSON-serializable dict) and use it as the deterministic `task_id` suffix, then look the `task_id` up in shared state. **Any existing state for that `task_id` — including `COMPLETE` or `ESCALATED` — is `True`** (a previously completed or escalated attempt must not be silently re-run). Branch/PR search for the id is best-effort only, since no marker convention exists; duplicates remain possible when no shared state exists, disclosed rather than claimed closed. Revision 3's suggested reuse of `orchestrator.md` §2's existing-branch check alone would have been vacuous: §2 says only "an existing branch/PR matching its ID" with no marker location. (6) `action_text` passes a **whole-cell keyword presence/absence check, no proximity window** (`action_text` is a short table cell, not multi-sentence prose like `classify_security_finding`'s `Recommendation` column, so a word-distance window is nearly vacuous here). **Preconditions, fail-closed (rounds 4-5)**: `action_text` that is not a `str`, is not ASCII (`action_text.isascii()`; round-5 fix — Turkish dotted `İ` and a Cyrillic `а` otherwise evade the exclusion side after lowercasing), is longer than 200 characters, or contains any character with code point below 32 or equal to 127 (newlines and other control characters) is `NOT_QUALIFYING` — a Preventive `Action` cell is a short phrase, and anything else is anomalous untrusted input. **Matching mechanics (rounds 4-5)**: lowercase `action_text`; for single-word checks tokenize with `[a-z0-9]+`, so hyphen, underscore and apostrophe **split** tokens (`waf-rule` → `waf`,`rule`; `WAF's` → `waf`,`s`) while digits stay inside a token (round-5 fix: revision 4's `[a-z]+` split `k8s` into `k`,`s`, so its stem could never match, and `s3`/`ec2` could not be listed). Revision 3 reused `classify_security_finding`'s `[A-Za-z][A-Za-z'-]*`, which keeps hyphen and apostrophe inside the token, so `waf-rule`, `IAM-policy`, `Terraform-managed` all evaded the exclusion set. **Qualifying side stays strict whole-token equality** against `{fix, fixes, fixing, patch, patches, patching, validate, validates, validating, validation, handle, handles, handling, correct, corrects, correcting, test, tests, testing}` (round-5 fix: inflections added, since "Add unit tests for X" and "Fixing null check" were all `NOT_QUALIFYING` — the largest recall loss found; `attestation`/`protest` still never match `test`); an `action_text` with no qualifying token is `NOT_QUALIFYING`. **Exclusion side is stem-prefix and deliberately over-matching** (over-matching only yields a false `NOT_QUALIFYING`, the safe direction): any token that **starts with** one of `{alert, dashboard, runbook, rollback, scal, autoscal, capacit, monitor, architect, refactor, redesign, decoupl, migrat, terraform, cloudformation, waf, firewall, iam, kube, k8s, helm, ingress, gateway, nginx, envoy, istio, ansible, pulumi, cdk, vpc, subnet, acl, dns, polic, s3, ec2, credential, secret, password, token}` excludes. Known over-matches, accepted as the safe direction: `tokenizer`, `retry policy`, `helmet`, `scalar`, `gateway`. Multi-word phrases are matched after normalizing `[\s_-]+` to a single space: `{network policy, security group, load balancer, roll back}`. **Residual, disclosed honestly**: the converse still qualifies — a qualifying verb plus an infra noun in none of these lists ("Fix the data-store replication config") classifies `QUALIFYING`. The keyword lists are a best-effort first gate on six words of untrusted text, **not** the control for infra changes; the real control is the diff-path check in Blocking-standard condition 9 below, which acts on what the PR actually changed. | Whoever authors the handoff | **Disclosed limitation, stated honestly**: this keyword heuristic is evadable by paraphrase, the same disclosed class as C1's `classify_security_finding`. Revision 3 called "the Reviewer's own ordinary review of the resulting PR" the backstop; that **overclaimed** (Security Architect): `reviewer.md`'s "Do not mark as blocking" list covers architectural improvements, and no existing condition fires on "this PR is a live production network/infra change"; condition 7 is credential/identity/secrets only. Round 4 replaces that claim with a real control, condition 9. `reviewer.md` condition 7 remains the backstop for the narrower credential/identity/secrets case; its recall against incident-rca-sourced phrasing is unvalidated (disclosed) |
| `validate_task_target(repo_root: str | Path, target: str | None) -> str | None` (new, real, tested function — round-4 addition, Security Architect, Medium) | Returns the validated `target` or `None` (drop it; the envelope then falls back to service-name-only — a rejected string is **never** passed on). Rule 5 redacts token shapes and PII only; it does nothing about paths or injection text, and no repository code validates `target` (confirmed: the only containment helper in `skills/loop-task-implementer/scripts` is `app_run.resolve_screenshot_path`, for screenshot output; `orchestrator.md` §2's "within the authorized repository and scope" is agent judgment, not code). **Common preconditions (round 5)**: `target` must be a non-empty ASCII `str`; the deny check below applies to **both** forms and, for the path form, to the **resolved** path as well as the input string, with every component casefolded first (macOS filesystems are case-insensitive: `.GIT/config`, `.ENV`, `KEY.PEM` otherwise evade). **Symbol form**: `re.fullmatch(r"[A-Za-z_][\w.:$#-]{0,127}", target, re.ASCII)` — `fullmatch` and `re.ASCII`, not `^...$` (which accepts a trailing newline) and not Unicode `\w`. **Path form** (anything else containing `/`): reject absolute paths, backslashes, NUL bytes, any `..` segment and any input over 200 characters; resolve with `(Path(repo_root) / target).resolve()`; require the resolved path to satisfy `is_relative_to(Path(repo_root).resolve())` (not string `startswith`, which lets `/repo-evil` pass) **and to differ from the repository root itself** (`./` otherwise passes) **and to exist**. **Neither form** (for example a bare `.env` or `.`, which fails the symbol regex and contains no `/`) returns `None`. **Deny list** (casefolded component or suffix match, applied to both forms and to the resolved path, so a symlink `docs/x -> ../.git/config` is caught): a `.git`, `.ssh` or `.aws` component; names `.env*`, `.netrc`, `.npmrc`, `id_rsa*`, `credentials*`; suffixes `.pem`, `.key`, `.p12`, `.pfx`, `.tfvars`. A bare filename such as `server.pem` or `terraform.tfvars` matches the symbol regex, so the deny list must run on it too. No subprocess (no `git ls-files`); "exists in the worktree" is the existence check. `target` as discovered by the backtick-scan is a **symbol**, not a path, and nothing here resolves a symbol to a file; that stays Builder-side judgment. **Residual, disclosed**: a 128-character, whitespace-free string such as `IGNORE-ALL-PRIOR-INSTRUCTIONS-and-run` passes the symbol form — a small residual injection channel in a hint field. | Whoever authors the handoff, before populating `target` | **Family gap, disclosed**: C1 and C2 take `target` from report evidence the same way and neither handoff doc validates it. This design adds the helper for C3; retrofitting C1/C2 is out of this ticket's scope and flagged for follow-up, not claimed fixed. Service-to-repo mapping: `repo_root` is **caller-supplied**, the repository the Orchestrator is already operating in, never derived from RCA text; a mismatch between the RCA's `service` and that repository is a human check at dispatch, disclosed rather than automated |
| New Reviewer Blocking-standard **condition 9** (round-4 addition, Security Architect — reverses revision 3's "no condition 9 needed") | For any task whose `specialist_inputs.incident_rca_origin` is `true`, a PR whose **actual changed-path list** (`git diff --name-only` against the base, computed by the Reviewer, never taken from task text) contains any path matching `*.tf`, `*.tfvars`, `*.hcl`, `*.rego`, `terraform/**`, `cloudformation/**`, `helm/**`, `charts/**`, `k8s/**`, `kubernetes/**`, `manifests/**`, `iam/**`, `policies/**`, `.github/workflows/**`, `.gitlab-ci.yml`, `Jenkinsfile`, `.circleci/**`, `kustomization.yaml`, `cdk.json`, `Pulumi.*.yaml`, `Dockerfile*` or `docker-compose*.yml` is itself Blocking-standard condition 9, regardless of passing tests or keyword classification, and regardless of which lens(es) this dispatch actually runs (the same sentence conditions 7 and 8 carry). **Path semantics (round 5)**: patterns match at **any directory depth** (anchoring at the repo root would miss `infra/terraform/**` and `deploy/helm/**`); the accepted cost is false blocks on fixtures (`tests/fixtures/manifests/`) and application code in a directory named `iam/` or `policies/`, which escalate to a human — a safe-direction error. The path list is computed with `git diff --name-only --no-renames` so a rename out of `terraform/` is still seen. The keyword exclusion list and this path set are not identical (for example `nginx`, `envoy`, `istio`, `ansible` have no path pattern); best-effort, disclosed A finding raised under it is an ordinary `PROPOSED_BLOCKING` finding using the existing finding schema unmodified, and its `evidence` must begin with the literal prefix `"incident_rca_infra: "` (mirrors condition 6's `"regression_gate: "` and C2 condition 8's `"dependency_hop: "`) | Added to `skills/loop-task-implementer/workflow/reviewer.md`'s shared Blocking standard | Revision 3 rejected a condition 9 on the reasoning that condition 7 already covers the credential case; that reasoning does not extend to infra: condition 7 is credential/identity/secrets only, and C1's "the Builder has no code path to a live system" backstop does not transfer to an infra-as-code repository, where an ordinary merged PR **is** the live change. Acting on diff paths is stronger than six words of untrusted summary text. **Residual**: practical blast radius also depends on whether autonomous merge plus CD-on-merge is enabled for the repository; the path set is best-effort and a repository with unusual infra layout needs its own paths added. **Numbering**: the real current max on `origin/main` is 8 (C2's); an implementer must re-check the real max at implementation time and renumber if another ticket landed first |

## Events

None — same reasoning as C1/C2: no new run-log event, no network, no state. The classification function
is pure and local.

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| Legacy `implementation_task` envelope (reused, all 16 real fields addressed individually, matching C1/C2's final-revision rigor — no blanket clause beyond the 3 genuinely generic fields) | See field-by-field mapping below | None of these fields ever carry raw, un-redacted log/evidence excerpts | Whoever authors the handoff |

**Field-by-field mapping** (no field left to a blanket "unchanged" clause beyond the 3 genuinely
domain-agnostic ones, per C2's own round-2/round-3 corrected rigor):

- `task_id` — generated per existing convention, with the deterministic `preventive_action_id` (see APIs,
  axis 5) embedded so `orchestrator.md` §2's existing-branch/PR check matches on a re-dispatch of the same
  action (round-4 fix).
- `scope` — `"{service}: {action_text}"`, where `action_text` has already passed axis 6's preconditions
  (a `str`, at most 200 characters, no newline or control character). **Round-4 correction (Security
  Architect)**: the Preventive `Action` cell is the single highest-value copy in this design — it becomes
  `scope`, `request` and the classified string — and revision 3 specified no treatment for it. It is
  untrusted data (per `incident-rca`'s own P0 guardrail), length-capped and control-character-free by the
  axis-6 preconditions; Rule 5 alone is the wrong control for an injected instruction phrase.
- `acceptance_criteria` — **round-4 rewrite (Security Architect)**: (a) a mandatory, synthesized (not
  copied) clause, `"Include a passing regression test demonstrating the fix for: {action_text}"`, because
  the real gold example's Preventive table has only 3 columns (Action, Owner, Priority) and no `Notes`
  column, so revision 3's "the action's own `Notes` cell" would be empty for gold-shaped reports and
  untestable (2 to 3 words such as "Root cause fix") for template-shaped ones, failing `orchestrator.md` §2's
  "acceptance criteria sufficiently concrete" check; (b) the `Notes` cell **only if present**, Rule-5
  redacted and capped at 200 characters; (c) **no prose from the Executive summary** — revision 3 cited an
  undefined "Executive summary headline" (it is a paragraph) after round 2 showed it contains `symptom`,
  the same untrusted class as the flagged tables, and `report-template.md`'s own safe-output enumeration
  omits the Executive summary, Conclusion and the Preventive `Action`/`Notes` cells while claiming
  "everything else ... no escaping needed" (an upstream gap in that template, flagged for follow-up, not
  something this design can rely on). Citation is by reference only: the RCA report identifier and
  `incident_window`, carried in `specialist_inputs`.
- `request` — synthesized trigger phrase (built from the same validated `action_text`).
- `repo_root`/`target` — `repo_root` is **caller-supplied** (the repository the Orchestrator is already
  operating in), never derived from RCA text. `target` is discovered best-effort (round 3 honesty
  correction, SRE: a backtick-quoted symbol appears exactly once across the gold example's six section
  instances, so this usually falls through to service-name-only): scan the Executive summary, Conclusion
  and Causal chain for a backtick-quoted symbol, then pass the result through `validate_task_target`
  (round 4); on `None`, fall back to service-name-only. A discovered value is a symbol, not a path, and no
  mechanism here resolves a symbol to a file. See Open questions.
- `level_hint` — same default as any legacy-envelope task.
- `specialist_inputs` — carries `incident_rca_origin: true` (mirrors C1's `security_origin`/C2's
  `dependency_upgrade_origin` marker convention, and is the key condition 9 gates on), `incident_window`
  (the RCA's own `from`/`to` window), `incident_report_ref` (a path, link or ID for the RCA report — the
  by-reference citation that replaces the Executive-summary prose, round 4) and `preventive_action_id`
  (see APIs, axis 5).
- `test_framework_hint`/`run_tests` — `run_tests: true` (each PR keeps tests green, enforced by this
  skill's own existing, unmodified completion-gate discipline); `test_framework_hint` left to whoever
  authors the handoff to discover per the repo's own build tooling (same discovery-order convention C2
  established for `regression_gate`, reused here rather than re-derived).
- `deadline`/`session_token_budget`/`output_dir` — same defaults as any legacy-envelope task, unchanged
  (the 3 genuinely generic fields).
- `app_run` — same default as any legacy-envelope task, unchanged (confirmed real, 16th field, via B7).
- `max_files_per_run` — a concrete absolute value of **2**, with a conditional bump to **3** (round-2
  fix, mirrors C1's own conditional bump for its Secrets sub-case, closes SRE's concrete counterexample:
  revision 1's flat "2" didn't account for a combined test-addition-plus-fix action — e.g. "Add perf
  regression test" plausibly spanning a new test file, a fixture, and a one-line fix — easily 3 files)
  when `action_text`'s tokens include a test-family token (`test`/`tests`/`testing`) **and** any non-test
  qualifying token (round-5 alignment: `patch` and `handle` families now count too, since a test plus any
  code-change verb is the combined test-and-fix shape). Note the bump fires on the gold example's own row ("Add regression test for transfer-money
  validation" contains `test` and `validation`), so 3 is the ordinary case for test-bearing rows, not a rare
  escape valve. **Round-2 correction**: revision 1's justification ("narrower by construction") did
  not hold for the `architecture` category the architecture review itself put in scope — now moot, since
  axis 6 excludes `architecture`-labeled actions from qualifying at all (see APIs); the remaining,
  genuinely code-level subset (tests, validation, targeted fixes, documentation) is narrow enough for 2,
  with the stated 3-file escape valve for the one concrete wider-footprint sub-case identified.
- `regression_gate` — populated via the same discovery-order convention C2 established (Makefile → 
  package.json → pytest.ini/pyproject.toml → tox.ini → CI config), falling back to `null` with the gap
  disclosed when the discovered command doesn't match `validate_repro_command`'s real accepted shapes —
  reused verbatim, not re-derived.

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| One Preventive action | `NOT_QUALIFYING` (wrong source table, `priority` outside `{P1, P2}`, confidence not `HIGH`/`MEDIUM`, wrong incident class, an existing task/branch already exists, or action text fails the keyword check — round-2: 6 independent ways to land here, was 4) → terminal, stays in the RCA report for a human to read; `QUALIFYING` → an `implementation_task` is authored, then proceeds through the completely unmodified Builder/Reviewer/lifecycle-gate pipeline | Classification happens once per qualifying action row, from that RCA's own report | No merge-group concept, no stepwise/multi-hop concept — each qualifying action is always its own, single, independent task, simpler than both C1 (merge groups) and C2 (stepwise chains) |

## Consistency

| Boundary | Model (strong / eventual) | Why |
|----------|-----------------------------|-----|
| Action-table source (`corrective` vs `preventive`) | Strong — an explicit, caller-supplied field, **structurally derived from the real H2 heading (round-2 fix), never a judgment call** | Prevents the exact confusion architecture-review Condition 2 named as Blocking |
| Existing task/branch status | Strong — an explicit, fail-closed boolean input (round-2 addition) | Closes the central gap Software Architect found: this was the one axis the ticket exists to get right, and revision 1 left it entirely to prose |
| Row's own stated urgency (`priority`) vs. its table placement | Strong, as a cross-check — anything outside the allowlist `{P1, P2}` (so `P0`, `p0`, `P0/P1`, empty) fails closed regardless of `action_source` (rounds 2 and 4) | Catches an upstream report that misfiles a genuinely corrective item under the Preventive heading — a risk `action_source` alone cannot catch even when correctly populated |
| One RCA's own multiple qualifying Preventive rows | Independent — each becomes its own task, no shared state, no ordering dependency between them (unlike C2's stepwise chain, there is no reason one Preventive action should block another) | Simpler risk shape than C2's — correctly not over-engineered with a dependency mechanism this ticket doesn't need |

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| `classify_incident_preventive_action` | Yes — pure function, no I/O | N/A, deterministic |
| Authoring an `implementation_task` for one qualifying action | Not automated in the usual sense | N/A — one-time, human-or-Orchestrator-authored action per qualifying row |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Qualifying Preventive rows per RCA | Unbounded in principle if an RCA names many rows, but each is independently gated and independently dispatched — no compounding risk, same as C1. **Round-2 correction**: revision 1 claimed "0-3, per the report-template's own gold example" — verified false by direct read of `gold-rca-excerpt.md`, which has exactly **1** Preventive row. The "0-3" figure is this design's own unvalidated guess, not sourced from that example — stated honestly now, not attributed to evidence that doesn't support it | No existing precedent bounds this explicitly; disclosed, not enforced |
| `max_files_per_run` | 2, conditional bump to 3 (see Data model) — lower than both C1's 2-3 and C2's 5 | The narrowed, infra-as-code/architecture-excluded qualifying subset (round-2) selects for genuinely narrow, single-purpose fixes; the 3-file bump covers the one concrete wider-footprint sub-case SRE identified |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| `classify_incident_preventive_action` receives a malformed/unrecognized value on any of its **6** axes (round-2: was 4) | Fails toward `NOT_QUALIFYING` on that axis alone — never assumes an ambiguous input is safe |
| A Preventive action is phrased to evade the code-level-action keyword check, or evades the exclusion keywords (disclosed limitation; round 4: stem-prefix matching, split-on-hyphen tokenization and a larger term list, still evadable by a qualifying verb plus an unlisted infra noun) | Round 4: **not** left to ordinary Reviewer review (revision 3's claim overclaimed — no existing Blocking-standard condition fires on a live-infra PR). Condition 9's diff-path gate is the real control for the infra subset; for everything else the Reviewer's ordinary review is the only backstop, disclosed |
| A qualifying action actually requires live external credential/identity/secrets access | `reviewer.md` condition 7 (C1's own, reused unmodified) fires regardless of this ticket's own classification accuracy — round-2 disclosure: condition 7's own recall against incident-rca-sourced phrasing specifically is unvalidated |
| A qualifying action actually requires live infra/network-control-plane access (WAF, firewall, IAM, infra-as-code) — **not** covered by condition 7's real scope | Round 4: axis 6's exclusion list is a best-effort first gate; **condition 9** checks the PR's actual changed paths against an infra-path set and blocks, independent of the task text. Residual: depends on the path set fitting the repository's layout, and on whether autonomous merge plus CD-on-merge is enabled |
| `has_existing_task_branch` cannot be determined (lookup error, no SCM or run-log access, or a `Deploy`/`Software defect` RCA citing no causative MR) | Round 4: caller passes `None`; only literal `False` passes, so the action stays `NOT_QUALIFYING` and in the report for a human |
| The same RCA is handed off twice | Round 4: the deterministic `preventive_action_id` embedded in `task_id`/branch marker makes `orchestrator.md` §2's existing-branch/PR check match, instead of spawning a duplicate PR |
| A discovered `target` is a crafted string (`../../etc/passwd`, an absolute path, injected prose) | Round 4: `validate_task_target` returns `None`; the envelope falls back to service-name-only |
| This ticket's new row is confused with the existing task-branch-regression row | Both rows' own Trigger-column text states the distinguishing condition explicitly, AND (round-2 fix) `has_existing_task_branch` is now a real, fail-closed input, not prose alone |
| An upstream RCA report misfiles a genuinely Corrective item under the `Preventive actions` heading | Rounds 2 and 4: the `priority` allowlist `{P1, P2}` fails closed on `P0` and every malformed value regardless of `action_source`, catching this specific mislabeling the table-source check alone cannot |

## Observability

| Signal | What's measured |
|--------|-------------------|
| None new | Same reasoning as C1/C2 — the resulting task's own existing completion/review lifecycle is the only observable surface |

**`backlog-runner` interaction (round-2 addition, SRE)**: stated explicitly rather than left silent — a
qualifying Preventive-action task is a standalone task, like C1's single-finding tasks, with no
chain-ordering concern (unlike C2's stepwise chain). It may be dispatched directly or through
`backlog-runner`'s own queue like any other ordinary task; no new interaction or carve-out exists or is
needed here.

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 1 | New forward + reverse `cross-skill-escalation.md` rows, linking to the new reference doc, with Trigger-column text explicitly distinguishing this row from the existing line-~181 row (round-2 citation fix) | Documentation only |
| 2 | New `classify_incident_preventive_action` function at `skills/loop-task-implementer/scripts/classify_incident_preventive_action.py`, with real unit tests covering all **6** independent fail-closed axes, the `[a-z]+` tokenization cases (`waf-rule`, `IAM-policy`, `WAF's`, `security_group`, `network-policy`), the stem-prefix inflection cases (`alerting`, `autoscaling`, `Refactoring`, `migration`), the allowlist `priority` cases (`p0`, `P0/P1`, `Sev0`, empty, `None`), the gold-shaped `HIGH — ...` confidence cell, and the disclosed residual (qualifying verb plus unlisted infra noun) | New, tested code |
| 2b | New `validate_task_target` function at `skills/loop-task-implementer/scripts/validate_task_target.py`, with real unit tests (symbol accepted; absolute path, `..`, symlink escape, `.git`, `.env`, key files, nonexistent path and free-text injection rejected; `None` passthrough) (round-4 addition) | New, tested code |
| 2c | `workflow/reviewer.md` gains Blocking-standard **condition 9** with its `"incident_rca_infra: "` evidence prefix (round-4 addition; re-check the real current max condition number at implementation time) | Small, additive workflow-doc change |
| 3 | New `incident-rca-handoff.md` reference doc: selection rule, envelope-population mapping, the explicit distinction from the existing task-branch-regression row, the `target`-discovery rule (round-2 addition) | Documentation only |
| 4 | **Precedent note for Epic C**: the matrix-row format, legacy-envelope-bypass convention, and real-tested-classification-function pattern continue to generalize to C4-C8 (now established across 3 tickets); this ticket's own specific contribution — a free-text keyword-presence classification function, as opposed to C2's clean closed-enum exact match — is a reusable pattern for any future Epic-C ticket whose upstream report is similarly free-text rather than a closed vocabulary. **Round-2 correction** (Software Architect): revision 1 speculated specifically about C4's own `performance-review` report shape, a claim this design has no basis to make — trimmed to generic guidance: future tickets should check their own upstream report's actual shape before assuming either this pattern or C2's applies | Documentation only |
| 5 | First real dry-run | **Open question** — see below |

## Open questions

1. **No concrete validation target exists in this session's own immediate work** — mirrors C1/C2's own
   honest disclosure.
2. **`target` (the exact file/path a qualifying action should modify) has a cheap discovery rule
   (round-2 addition: scan Executive summary/Conclusion/Causal chain for a backtick-quoted symbol) but no
   RCA-internal structured field to ground
   it** — unlike C1's finding-evidence citation or C2's manifest path, `incident-rca`'s own report has no
   structured file/symbol field. Left to whoever authors the handoff to resolve from the action text and
   service name; a future improvement could have `incident-rca` itself name a suspected file/symbol in its
   own Preventive-action rows, out of scope for this ticket.
3. **The keyword heuristic's own precision/recall against real-world Preventive-action phrasing is
   unvalidated**, same disclosed-limitation class as C1's own `classify_security_finding`.
4. **Whether Corrective actions should ever get their own, differently-shaped handoff** (e.g. to an
   on-call/paging skill, not `loop-task-implementer`) is out of scope for this ticket — this design only
   closes the Preventive-action gap the backlog ticket names.
5. **(Round-2 addition, Security Architect)** The axis-6 exclusion list (infra-as-code/network-control-plane
   keywords plus `architecture`) is a keyword heuristic, same evasion class as the qualifying-keyword side
   — a cleverly-worded infra-as-code action could still slip through, and `reviewer.md` condition 7 would
   not catch it either (it's scoped to credential/identity/secrets, not infra generally). Disclosed, not
   solved. Round 4: condition 9's diff-path gate, not the Reviewer's ordinary review, is the real control for
   the infra subset; condition 9's own path set is best-effort and its blast-radius relevance depends on
   whether autonomous merge plus CD-on-merge is enabled.
6. **(Round-2 addition, Security Architect)** `reviewer.md` condition 7's own recall against
   incident-rca-sourced phrasing specifically has never been validated — it was authored and checked
   against C1's application-code-vulnerability domain. Disclosed here for consistency with this design's
   own honesty standard elsewhere, not a new mechanism to build.
7. **(Round-4 addition, Security Architect)** `target` is not validated anywhere in C1 or C2 either;
   this ticket adds `validate_task_target` for itself only. Retrofitting C1/C2 is flagged for follow-up.
8. **(Round-4 addition)** `report-template.md`'s own safe-output enumeration omits the Executive summary,
   Conclusion and the Preventive `Action`/`Notes` cells while claiming everything else needs no escaping —
   an upstream gap in `incident-rca`, outside this ticket, flagged rather than fixed here.
9. **(Round-4 addition)** Whether the Preventive table has a `Notes` column differs between the gold example
   (3 columns) and the template (5 columns); this design derives `acceptance_criteria` from `Action` plus a
   mandatory regression-test clause so it works for both, but real-world report shapes are unvalidated.
