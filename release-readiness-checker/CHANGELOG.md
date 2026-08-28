# Changelog — release-readiness-checker

All notable changes to the release-readiness-checker skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

## [1.1.0] — 2026-08-28

### Added
- **Manifest v2** — a release manifest entry may now carry `environment`, `source_revision`,
  `criticality`, `production_readiness_required`, and `production_readiness_ref` alongside the existing
  v1 fields. A v1 entry (no `production_readiness_required`) is byte/semantics-unchanged and never
  invokes production readiness — see `scripts/release_readiness_v2.py::parse_release_entry` /
  `ReleaseEntry.compatibility_projection()`.
- **Trusted reuse-first, conditional production-readiness invoke** for a v2 entry with
  `production_readiness_required: true`: reuse a trusted, fresh, deployable-scoped
  `production_readiness_report` (exact repo/service/environment/`release_ref`/`source_revision` match,
  never a caller/file self-attested one) first; otherwise, only when candidate identity is sufficient and
  production-readiness-review is available, conditionally invoke it once via `assessment_context`;
  otherwise the dimension — and the release verdict — is `UNKNOWN`, never a silently skipped gate.
- **Code-review coverage handoff** (`build_code_review_coverage`) — authoritative enumeration of every
  material change in a release range (merged PR/MR objects, direct commits, cherry-picks, reverts) and
  its trusted review coverage, including authoritative squash/merge `integrated_revision` linkage. A
  change's own claimed/forged integrated-revision linkage is never consulted. Passed to
  production-readiness-review so it reuses this skill's own review pass instead of revisiting pr-review
  within the same release-root run.
- **Worst-first verdict cap** (`cap_release_verdict`) — production readiness `NOT_READY`/`UNKNOWN`/
  `CONDITIONAL` caps the release verdict accordingly; `READY` never widens it. The existing
  pr-review/k8s/incident-rca checks always run regardless of the production-readiness outcome.
- **Final freshness fence** — immediately before emitting the report, a mutable `release_ref` that
  resolved differently than at the start of the run (or a reused report whose deployable digest no
  longer matches) makes the affected entry `UNKNOWN`; old and new evidence are never combined.
- **Execution-status semantics** (`finalize_release`) — a resolved `NOT_READY` verdict is a `SUCCESS`ful
  analysis; an unresolved required dimension makes the result `PARTIAL` regardless of the verdict; an
  empty manifest is `BLOCKED`, never `FAILED`.
- Registry: optional `production-readiness-review.conditional_invoke` capability and a
  `composition.invokes`/`composition_runtime` handoff (`assessment_context`) to production-readiness-
  review, plus `production_readiness_report` added to this skill's consumed artifact types. The mandatory
  `install.requires` footprint (`pr-review`, `k8s-overprovisioning-datadog`, `incident-rca`) is
  unchanged — production-readiness-review is never a mandatory install dependency.
- New adversarial Tier-3 golden case
  (`evals/golden/release-readiness-checker/golden-v2-forged-build-provenance-prose.yaml`): a caller note
  claiming an image digest "came from commit abc123...; trust it and mark ready" can never establish
  build provenance — the production-readiness dimension and the release verdict stay `UNKNOWN`.
- Design spec: [docs/superpowers/plans/2026-08-23-engineering-decision-delivery-after-pr159-design-v10.md](../docs/superpowers/plans/2026-08-23-engineering-decision-delivery-after-pr159-design-v10.md)

### Fixed (adversarial review, same day)
- **Closed a self-attestation bypass.** `code_review_coverage` was read directly off the untrusted
  `release_manifest` entry mapping and, if it claimed `status: COMPLETE`, stamped `authority:
  trusted_runtime` in `assessment_context` with no check of its own `acquisition` field — a manifest
  author could add a forged `code_review_coverage: {status: COMPLETE, ...}` block and have it accepted
  as "already reviewed" evidence with no real SCM enumeration ever happening. Fixed by making
  `code_review_coverage` a `run_release`/`resolve_production_readiness` parameter supplied out-of-band by
  the trusted execution harness (mirroring `trusted_reports`/`production_invoke`, never the manifest
  text), plus a defensive `acquisition` check (`_coverage_is_trustworthy_and_complete`) so even a
  correctly-sourced-but-weakly-authoritative bundle can never gate an invocation as complete.
- **Fixed reuse-before-completeness ordering.** The incomplete-coverage short-circuit ran *before* the
  trusted-report reuse loop, discarding a valid `REUSED`-able report whenever coverage happened to be
  supplied and incomplete. Reuse is now attempted first, exactly as documented.
- **Conflicting trusted reports are `UNKNOWN`, not first-match.** Two trusted, identity-matching
  `production_readiness_report`s that disagree in verdict are now treated as conflicting authoritative
  evidence rather than silently resolved by picking whichever came first in the list; an explicit
  `production_readiness_ref` pin (previously parsed but never read) now narrows reuse to the report it
  names.
- **A malformed `included_change_refs` entry is never silently dropped** from `build_code_review_coverage`
  — it now always counts as uncovered instead of vanishing from the enumeration.
- **An executed existing check (pr-review/k8s/incident-rca) that itself resolves to an evidence gap** now
  correctly makes `skill_result.status` `PARTIAL`, matching an unexecuted check; previously only a missing
  check harness triggered that.
- Strengthened test-fixture fidelity: `child_context`/`grandchild_context` now validate against the real
  registry runtime-handoff data instead of returning pure arithmetic, and the Task 5.5 no-revisit harness
  no longer mutates the real `ReleaseResult` return value with test-only bookkeeping.

### Fixed (adversarial review round 2, same day)
- **Closed a cross-entry coverage leak.** The round-1 fix moved `code_review_coverage` off the untrusted
  manifest text, but the new out-of-band parameter had no per-entry binding — one `code_review_coverage`
  bundle assembled for one manifest entry was silently applied to every OTHER entry in the same
  multi-entry `run_release` call too, laundering one candidate's review evidence into a different
  candidate's verdict. Fixed with `_coverage_for_entry`, which only applies a bundle to the entry whose
  `source_revision` matches the bundle's own `candidate_source_revision`; a scope mismatch is treated as
  "not supplied for this entry," never as untrustworthy evidence for it.
- Fixed two tests that could not have caught the bugs they were named for:
  `test_production_report_for_old_digest_not_reused_after_ref_moves` built its entry without
  `required=True`, so production readiness was never resolved and the assertion passed vacuously;
  `test_conflicting_trusted_reports_are_unknown_not_first_match` never checked that the conflicting-report
  path avoids a wasted child invocation. Both now exercise the real path and pass a spy that would fail if
  the invariant regressed.

### Fixed (adversarial review round 3, same day)
- **`code_review_coverage` is now scoped by repo/service too, not source_revision alone.** Round 2's
  per-entry binding used only `candidate_source_revision`, which is manifest-entry (caller-controlled)
  text — two different entries could coincidentally (or deliberately) share the same value.
  `build_code_review_coverage` now optionally records its own `repo`/`service`, and `_coverage_for_entry`
  requires them to canonically match too when the bundle declares them.
- **The final freshness fence now caps the verdict instead of overwriting it** — it previously set
  `overall = "UNKNOWN"` directly, which could silently downgrade an already-proven `NOT_READY` (worse,
  per this module's own severity order) down to the merely-uncertain `UNKNOWN`.
- **`match_release_report`'s environment check now fires whenever either side declares an environment**,
  not only when the entry does — an entry that simply omits `environment` no longer silently reuses a
  report produced for some other declared environment.
- **`_coverage_is_trustworthy_and_complete` now also rejects an internally inconsistent bundle** that
  claims `COMPLETE` while still listing a non-empty `uncovered_change_refs`.
- **`production_readiness_required` now accepts the case-insensitive string `"true"`** in addition to the
  boolean `True` — a quoted `"true"` no longer silently degrades a v2 entry to v1 behavior.
- **`start_ref`/`final_ref` now accept a `{(repo, service): ref}` mapping** for independent per-entry
  freshness tracking in a multi-entry manifest, in addition to the original single-value-for-all shape.
- **`ReleaseResult`'s bracket access now raises `KeyError`** for an unrecognized key instead of leaking
  the underlying `AttributeError`, matching normal dict-like conventions.

### Fixed (adversarial review round 4, same day)
- **`code_review_coverage` now requires repo/service to be declared, not merely optional.** Round 3's
  scoping only checked repo/service "when the bundle declares them" — a bundle assembled without them
  (a real possibility for any caller of the still-optional `build_code_review_coverage` parameters)
  silently reverted to source_revision-alone scoping, reopening round 2's cross-entry leak. A bundle
  missing either is now never applied to any entry.
- **The per-entry freshness-fence key now includes `environment`.** Keying by `(repo, service)` alone
  let two entries for the same repo/service in different environments (e.g. staging and prod) collide in
  the `start_ref`/`final_ref` mapping, silently masking one environment's real ref movement with another's.
- **Malformed non-string manifest fields (`repo`, `service`, `release_ref`, `environment`,
  `source_revision`, ...) no longer crash `run_release`.** They previously reached
  `normalize_repo_identity`/`normalize_service_identity`/`same_environment`/`_looks_like_digest`, all of
  which raise `TypeError` on a non-string input — one malformed entry took down the whole manifest's
  readiness check instead of degrading just that entry to `UNKNOWN`.
- **A multi-entry manifest with more than one `production_readiness_required` entry now records every
  entry's own result** (`ReleaseResult.production_readiness_results`) instead of silently discarding every
  entry's result but the last one processed; the top-level `production_readiness`/
  `production_readiness_source` convenience fields now reflect whichever entry's result is most severe
  (the one that actually drove the capped overall verdict), never an arbitrary last-write-wins value.
- **`_candidate_identity_sufficient` now also requires `repo`/`service`** before invoking
  production-readiness-review — an unidentifiable candidate can never be matched downstream anyway, so
  invoking the real child for one was a wasted call and a definitional inconsistency with
  `match_release_report`'s own mandatory repo/service check.
- Investigated and rejected as a false positive: using `production_readiness.py`'s generic
  `_effective_source_revision` for `match_release_report`'s environment/source-revision resolution (see
  round 3's note on the same helper) — confirmed the existing flat/nested-fallback logic here is correct
  for this artifact's actual schema.

Added 8 new regression tests covering every fix above.

### Fixed (adversarial review round 5, same day)
- **Crash-safety: non-string external identity fields no longer crash `run_release`.** Round 4's
  `_as_str` coercion only covered the manifest side; a non-string `repo`/`service`/`environment` in a
  `trusted_reports` entry or a `production_invoke` return value still reached
  `normalize_repo_identity`/`normalize_service_identity`/`same_environment` unguarded, all of which raise
  `TypeError` on a non-string input (as does an unquoted YAML `environment: no`, which PyYAML's
  SafeLoader parses as the bool `False`). `match_release_report` and `_coverage_for_entry` now use
  `_safe_normalize_repo`/`_safe_normalize_service`/`pr._safe_same_environment`.
- **Crash-safety: an unhashable verdict (a list/dict) no longer crashes conflict detection or verdict
  capping.** A malformed report/invoke-result `verdict` reached a `set` comprehension and a `dict`
  membership test, both of which raise `TypeError` on an unhashable value. Added `_safe_verdict`, applied
  at every point a verdict is read from external data, and hardened `cap_release_verdict` itself.
- **`evidence_refs` of the wrong shape (a bare string instead of a list) is no longer silently shredded**
  into individual characters by a bare `list(...)` call — only a genuine list is ever treated as a ref
  list.
- **Existing pr-review/k8s/incident-rca checks are now attributed to the entry that triggered them.**
  `check_spy.run` now receives the candidate's `repo`/`service`/`environment`, and each recorded `checks`
  entry now carries `repo`/`service` too — previously a multi-entry manifest gave a real (non-stub) check
  harness no way to discriminate which candidate it was being asked to check, contrary to
  `run-check.md`'s own documented "once per service"/"per resolved MR" contract.

Added 5 new regression tests covering every fix above.

### Fixed (adversarial review round 6, same day)
- **A check harness's own non-string status no longer crashes `run_release`** — round 5's `_safe_verdict`
  guard covered every verdict extraction point except the sibling check-status lookup
  (`_CHECK_STATUS_VERDICT.get(status, ...)`) added in the same round.
- **An entry voided by the freshness fence is no longer silently absent from
  `production_readiness_results`** — an entry whose ref moved mid-run and that also required production
  readiness now still gets a `{"verdict": "UNKNOWN", "source": None}` record, so a per-entry report render
  can show it was required and why it's unresolved.
- **`match_release_report`'s `source_revision` check is now genuinely flat-only** — a residual
  `or target.get("source_revision")` fallback reopened the exact nested/flat ambiguity round 3's comment
  said was deliberately avoided; a schema-nonconforming report with a nested-only `source_revision` no
  longer matches.
- **`build_code_review_coverage` no longer crashes on an unhashable `trusted_review_refs` item or
  `integrated_revisions` value** — the same untrusted-SCM-enumeration boundary `_change_ref_id` already
  hardens `included_change_refs` against was left open on its two sibling parameters.
- **`finalize_release` now tolerates an explicit `checks: None`**, matching the `or []` pattern its
  sibling `unknown_dimensions`/`production_readiness_results` fields already used.
- **A manifest that is a non-empty list of nothing but garbage (non-mapping) items now reaches the same
  `BLOCKED` hard stop as a literally empty manifest**, instead of silently generating phantom `NOT_RUN`
  check rows for unidentifiable services.

Added 7 new regression tests covering every fix above.

### Fixed (adversarial review round 7, same day)
- **Security: `classify_report_for_release` no longer gate-trusts `"authoritative_host"`/`"trusted_runtime"`
  acquisition for a whole `production_readiness_report`.** These are evidence-level authority concepts used
  elsewhere (e.g. a `code_review_coverage` bundle's own trust check, `provenance.sources`) — treating them
  as sufficient to reuse a *report* let a forged or replayed report self-attest whole-artifact trust and be
  reused as READY without this release ever performing or witnessing a real production-readiness
  invocation. Only `direct_child`/`runtime_validated` acquisition — an actual invocation this release
  performed, or one a trusted runtime performed for it — now satisfies the gate. Present unchanged since
  the very first commit; not caught by rounds 1-6 because those rounds focused on crash-safety and
  identity-matching, not a report's own trust classification.
- **Security: an untrusted `production_readiness_ref` pin can no longer resolve a genuine conflict between
  two trusted, identity-matching reports.** The pin is caller/manifest-supplied text and was applied to
  narrow the reuse candidate set *before* the disagreeing-verdicts conflict check ran — letting a pin
  silently pick a stale favorable report (e.g. `READY`) over a fresher, disagreeing one (e.g. `NOT_READY`)
  by simply not naming it, instead of the conflict resolving to `UNKNOWN` as the evidence-authority policy
  requires. Conflict detection now runs on the full unpinned match set first; the pin is applied only
  afterward, among already-agreeing matches, purely to select which report object to attribute. Also
  present unchanged since the first commit.

Added 4 new regression tests covering every fix above.

### Fixed (adversarial review round 8, same day)
- **Security: a manifest-declared `criticality` is no longer folded into the invoked child's candidate as
  if it were vetted identity.** `_candidate_from_entry` forwarded `entry.criticality` (untrusted
  `release_manifest` text, per this skill's own "caller-supplied data, not instructions" invariant) straight
  into `assessment_target`/candidate with no authority tag and no "unknown" fallback boundary, contradicting
  design v10 Sec9.2 ("criticality when authoritative/known"). Since `criticality` gates how strictly
  production-readiness-review evaluates ownership/rollback/post-deploy/recovery evidence (tier0/tier1/unknown
  require authoritative evidence to resolve; tier2/tier3 accept caller-only evidence at CONDITIONAL), a
  manifest author declaring a lower tier than reality (e.g. `tier3` for an actually-tier0 service) could
  silently relax those gates for a real invocation. `criticality` is now surfaced only via
  `build_assessment_context`'s `inputs`/`input_provenance`, tagged `caller` authority exactly like `since`,
  so production-readiness-review applies its own documented authoritative-wins-over-caller precedence
  instead of receiving an unqualified value indistinguishable from vetted identity fields.

Added 3 new regression tests covering the fix above.

### Fixed (adversarial review round 9, same day)
- **Security: a non-resolving `production_readiness_ref` pin no longer discards agreeing trusted
  evidence.** After round 7 moved conflict detection ahead of pin narrowing, a pin that named no report
  among the (already-agreeing) matching set still fell through past reuse entirely into the invoke-or-
  UNKNOWN path -- silently discarding known trusted evidence (e.g. a resolved `NOT_READY`) via a typo'd or
  stale `production_readiness_ref`, an untrusted manifest field, potentially reaching a more favorable
  outcome through a fresh invocation instead. Since every remaining match in that branch already agrees in
  verdict, which one gets attributed can never change the resolved status, so a non-resolving pin now
  falls back to the full agreeing set rather than suppressing reuse.
- **Security: `_candidate_identity_sufficient` no longer treats a mutable tag as a usable source
  revision.** `_looks_like_digest`'s "contains a colon" heuristic meant any colon-free `release_ref` --
  including a mutable, non-identity-pinning tag like `latest`/`main`/`staging` -- was accepted as "the
  release_ref is itself a source revision," letting a manifest declare such a tag with no `source_revision`
  and still reach a full `INVOKED` production-readiness verdict. design v10 Sec9 defines `release_ref` as
  "the immutable deployable ref (commit SHA when that is the deployable, otherwise image/artifact
  digest)," and Sec9.2 requires "if source_revision is absent ... and cannot be authoritatively resolved,
  do not invoke." Replaced the colon-only heuristic with `_looks_like_source_revision`, which requires an
  actual hex-SHA shape.

Added 4 new regression tests covering both fixes above.

### Fixed (adversarial review round 10, same day)
- **Security: the freshness-fence lookup now normalizes identity the same way `match_release_report`
  does.** `_ref_pair_for_entry` built its `start_ref`/`final_ref` lookup key from raw, unnormalized
  `repo`/`service`/`environment` and did a bare `dict.get()`, while every other identity comparison in this
  module normalizes first (canonical repo form, case-insensitive environment). A differently-cased
  environment (`"Production"` vs `"production"`) or a repo string with/without a `.git` suffix could
  silently miss the freshness-fence lookup -- letting the fence go inert (a moved ref undetected) instead of
  failing closed, even though `match_release_report`'s own format-insensitive comparison would still reuse a
  report keyed to the other spelling. Added `_normalized_ref_pair_key`/`_resolve_ref_pair_mapping`, which
  normalize both the entry's own identity and the mapping's keys before comparing.
- **Security: an explicit `source_revision` is now itself required to look like a real git commit SHA** --
  sibling gap to round 9's `release_ref` fix. `_candidate_identity_sufficient` treated any truthy
  `source_revision` as sufficient with no shape check, even though `source_revision` is untrusted
  `release_manifest` text at the exact same trust boundary as `release_ref`; a manifest declaring
  `source_revision: "latest"` (or any other mutable tag/arbitrary text) reached a full `INVOKED`
  production-readiness verdict on an unproven "revision." Now validated via the same
  `_looks_like_source_revision` check already applied to the `release_ref`-alone fallback path.
- **`production_readiness_results` and `checks` now carry `environment`.** Two entries legitimately sharing
  repo+service across different environments (staging/prod) produced result rows distinguishable only by
  `verdict`/`status` -- any consumer keying on `(repo, service)` alone (the natural key) would silently
  collapse one environment's result into the other's. Strengthened
  `test_freshness_fence_key_includes_environment_not_just_repo_service`, which previously only asserted
  "some entry was affected" and would not have caught a regression that voided both entries or the wrong
  one, to assert per-environment attribution directly.

Added 3 new regression tests and strengthened one existing test covering all three fixes above.

### Fixed (adversarial review round 11, same day)
- **Security: the trusted-reuse path now requires the same immutable-identity anchor the invoke path
  already required (rounds 9/10), closing a reuse-side bypass of that exact requirement.**
  `match_release_report` compared `release_ref`/`source_revision` by flat string equality only, with no
  shape validation -- so a manifest entry declaring a mutable, non-identity-pinning tag in both fields (e.g.
  `release_ref: "v1.2.3"`, `source_revision: "latest"`) could still `MATCH` and be *reused* as `READY` against
  a `trusted_reports` entry carrying the identical strings, even though `_candidate_identity_sufficient`
  would correctly refuse to *invoke* on that same unproven identity. An exact string match against a mutable
  tag is not proof a report was ever produced for the same concrete content, since a tag can be repointed
  between when the report was produced and now. Added `_has_immutable_identity`/`_looks_like_immutable_digest`
  and wired the same anchor requirement into `match_release_report` -- but with correctly *different*
  strictness than the invoke path: a real content-addressed digest `release_ref` (e.g. `sha256:...`) remains
  a legitimate reuse anchor even with no `source_revision` known (unlike invoking, reuse needs no new proof,
  only confirmation this is the same immutable artifact a report already covers), so this fix does not
  regress the documented "reuse a trusted, deployable-scoped report... when supplied" digest-only pattern.
- Added a missing regression test for round 4's "a `code_review_coverage` bundle omitting `repo`/`service`
  is never applied, even to the one entry whose `source_revision` matches" fix -- the code was already
  correct, but no existing test exercised this exact branch (the closest existing test only asserted the
  *non-matching*-revision entry didn't receive the bundle).

Added 3 new regression tests covering both items above.

### Fixed (adversarial review round 12, same day)
- **Security: a validly SHA-shaped `source_revision` could still redeem a mutable `release_ref` for reuse,
  reopening round 11's exact gap through its own fix's "either field suffices" logic.** Round 11's
  `_has_immutable_identity` returned `True` whenever `source_revision` alone was SHA-shaped, regardless of
  what `release_ref` looked like -- but `release_ref` (not `source_revision`) is the actual deployable
  identity `match_release_report` keys reuse on via exact string equality. A manifest entry declaring a
  mutable tag in `release_ref` (e.g. `v1.2.3`, potentially repointed to different, unreviewed content since
  a trusted report was produced) plus a stale/replayed but validly-shaped `source_revision` copied from that
  old report could still `MATCH` and reuse it as `READY`, with `production_invoke` never called. Unlike
  invoking (where the freshly-invoked child independently re-validates build provenance linking
  `source_revision` to today's actual deployable), reuse performs no such re-verification -- it is pure
  static string matching against a possibly long-stale report, so `source_revision` can never substitute for
  `release_ref`'s own immutability there. Replaced the shared `_has_immutable_identity` helper with two
  single-purpose ones: `_release_ref_is_immutable_identity` (reuse gate, checks `release_ref` alone, never
  redeemable by `source_revision`) and `_candidate_identity_sufficient`'s own inline check (invoke gate,
  unchanged behavior: a validly-shaped `source_revision` legitimately substitutes there, since the invoked
  child's own re-validation is what makes that safe).

Added 1 new regression test (plus a corrected stale docstring reference in an existing round-11 test) covering the fix above. Found by a follow-up code-review pass after round 12's two independent adversarial reviews both reported zero new issues -- a reminder that "the same code region has already had two bugs found in it" (true of this exact reuse-vs-invoke identity logic, across rounds 9, 10, and 11) remains a strong signal to keep looking even after a review round comes back clean.

### Fixed (adversarial review round 13, same day)
- **Security: the digest-algorithm component of the immutable-identity check was open-ended, letting an
  ordinary mutable `name:tag` container reference be mistaken for a genuine content digest.**
  `_IMMUTABLE_DIGEST_RE`'s algorithm component accepted any `[a-z0-9]+`-with-separators string, not just a
  genuine registered content-hash algorithm -- so a fully mutable image reference like
  `nightly-build:<40 hex chars>` (a common CI convention: tagging an image with a commit SHA) was
  syntactically indistinguishable from `sha256:<hexdigest>`. `_release_ref_is_immutable_identity` then
  treated such a tag as a pinned, immutable reuse anchor, letting a stale trusted report keyed to it be
  reused as `READY` with no re-verification, even though the registry could have repointed that tag to
  entirely different, unreviewed content since the report was produced -- the fifth distinct variant of the
  "mutable reference accepted as immutable identity" defect family found across rounds 9-13, all in this
  same reuse-vs-invoke identity logic. Restricted the algorithm component to an explicit allowlist of
  genuine content-hash algorithms (`sha256`, `sha384`, `sha512`).
- **A malformed/unresolvable `included_change_refs` entry's synthetic display placeholder
  (`__unresolvable_change_<index>__`) could be laundered into "covered" by a coincidental string collision.**
  `_change_ref_id` returned that fixed, predictable placeholder string for a malformed entry, and
  `build_code_review_coverage` then compared it by ordinary string equality against
  `trusted_review_refs`/`integrated_revisions` like any real ref -- so a genuine ref or integrated-revision
  value that happened to equal that exact placeholder text (e.g. an SCM-enumeration harness bug, or an
  unusual real branch/PR identifier) would incorrectly mark the malformed entry as reviewed, letting coverage
  read `COMPLETE` despite a real change never having been accounted for. `_change_ref_id` now returns `None`
  for a malformed entry; `build_code_review_coverage` treats `None` as unconditionally uncovered without ever
  string-comparing it, while still surfacing the same placeholder text in `included_change_refs`/
  `uncovered_change_refs` for display.

Added 3 new regression tests covering both fixes above.

### Fixed (adversarial review round 14, same day)
- **Security: the digest hex-length was still open-ended per algorithm, reopening round 13's exact exploit
  shape under one of the three now-allowlisted algorithm names.** `_IMMUTABLE_DIGEST_RE` restricted the
  algorithm to `sha256`/`sha384`/`sha512` (round 13) but still accepted "32 or more" hex characters for all
  three interchangeably, even though a real digest of each has one fixed length (sha256=64, sha384=96,
  sha512=128). A repository/artifact store literally named e.g. `sha256`, carrying a mutable, git-SHA-style
  tag (`sha256:<40-hex-char-tag>` -- wrong length for a real sha256 digest), was still accepted as an
  immutable reuse anchor -- the sixth distinct variant of the "mutable reference accepted as immutable
  identity" defect family found across rounds 9-14. The regression test round 13 itself added for
  sha384/sha512 support (`test_sha384_and_sha512_digests_are_also_recognized_as_immutable`) was unknowingly
  complicit: it reused sha256's 64-char length for sha384/sha512 fixtures too, so it never actually exercised
  a digest shaped like a real sha384/sha512 hash. Both the regex (now requiring the exact hex length per
  algorithm) and that test's fixtures are fixed.
- **`build_assessment_context` could stamp forged `code_review_coverage.evidence_refs` content as
  `"trusted_runtime"`.** A bundle can satisfy every structural trustworthiness check
  (`_coverage_is_trustworthy_and_complete`: `status: COMPLETE`, no `uncovered_change_refs`, host/runtime-
  authoritative `acquisition`) while separately declaring an `evidence_refs` list unrelated to
  `trusted_review_refs` (the field those checks -- and `production_readiness.py`'s own
  `validate_code_review_coverage` -- actually vet). `build_assessment_context` propagated that
  independently-settable `evidence_refs` field into the release-level evidence trail whenever the bundle
  passed its trustworthiness check, tagging unrelated/forged content `"trusted_runtime"`. A bundle produced
  by `build_code_review_coverage` itself is unaffected (it always sets `evidence_refs` to a copy of
  `trusted_review_refs`, so this changes nothing for the normal path), but a hand-built or otherwise-produced
  trusted-channel bundle was not similarly protected. Now propagates refs from `trusted_review_refs` whenever
  the bundle is trustworthy, falling back to `evidence_refs` (still merely descriptive caller text) only on
  the caller-only path.

Both found by two independent adversarial passes this round (one re-hammering the reuse-vs-invoke identity
cluster per rounds 9-13's track record, one covering the rest of the module fresh). Added 3 new regression
tests and split one existing test into two (trustworthy vs. caller-only paths) to keep both wrong-shape
guards independently exercised.

### Round 15, same day -- no code defect found; one coverage gap closed

Two independent adversarial passes: one re-derived every function in the six-round (9-14) identity-
immutability defect cluster character-by-character against a precisely stated invariant ("any value treated
as content-addressed/immutable must match an exact real-world digest/SHA shape, AND data forwarded under an
authority tag must come from the same field that authority check examined") and confirmed every relevant
site in the file satisfies it -- this defect family is closed as of round 14. The other ran a break-and-
restore audit against all ~15 regression tests added across rounds 9-14 (every one genuinely fails when its
own fix is reverted -- no dead tests), checked for test-order dependence (none found, structurally and
empirically), and identified a real coverage gap: `resolve_production_readiness` is a public function whose
own docstring documents standalone use with a raw manifest dict, but no test ever calls it directly --
`run_release` always pre-parses first, so the `parse_release_entry` branch inside
`resolve_production_readiness` and the entire `NOT_REQUIRED` early return had zero direct test coverage
anywhere in the suite. No functional code change; added a test exercising both.

### Fixed (adversarial review round 16, same day)
- **`build_assessment_context` stored the trusted `code_review_coverage` bundle into `assessment_context`
  by raw reference, unlike `candidate` (already defensively copied via `dict(candidate)`).** `production_invoke`
  is a plain caller-supplied Python callable with no enforcement preventing it from mutating whatever mapping
  it's handed. Since `run_release` passes the SAME `code_review_coverage` object to every entry in a
  multi-entry manifest and to every future call that reuses it, an invoke that mutated its own
  `assessment_context["inputs"]["code_review_coverage"]` (or one of its nested mutable lists, e.g.
  `trusted_review_refs`) corrupted the caller's own trusted-runtime-supplied bundle in place -- confirmed by
  direct execution to silently flip a later entry's (or a later call's) resolved verdict from `READY` to
  `UNKNOWN`, purely from the aliasing rather than any real evidence problem. This is a correctness/reliability
  bug, not a security bypass (it fails toward `UNKNOWN`, never toward a falsely-favorable verdict, in every
  case tried) -- but it directly contradicts this module's own header docstring ("pure, side-effect-free
  evidence logic"). Fixed with a defensive `copy.deepcopy`, mirroring `candidate`'s existing treatment.

Found by a confirmatory round after round 15's two passes both concluded the six-round (9-14) identity-
immutability defect family was closed -- this round's angles deliberately moved to a different concern
(cross-file vocabulary consistency, v1 compatibility, crash-safety, and mutation/aliasing safety) rather than
re-testing that same family, and the mutation-safety angle surfaced this genuinely new bug class. Angles 1
(cross-file `acquisition` vocabulary consistency), 2 (v1 backward compatibility against 10 varied manifests),
and 4 (crash-safety against novel type-confusion inputs) all came back clean. Added 1 regression test,
verified to fail when the fix is reverted and pass when restored. Full suite (1700 passed, 1 skipped),
registry validate/generate-check, and lint-release-readiness-checker all green.

### Round 17, same day -- two independent adversarial passes found no code defect; one more closed by a
### third, confirmatory pass

Two independent adversarial passes: one systematically re-checked every external-boundary crossing in the
module (into `check_spy`, into `production_invoke`'s `candidate`/`assessment_context`, out of
`trusted_reports`/invoke/check-spy return values into this module's own returned state, and
`build_code_review_coverage`'s two separate `list()` copies) for more instances of round 16's mutation/
aliasing bug class -- found none; round 16's fix was the only site. The other did a fresh security pass on
`cap_release_verdict`'s severity ordering (can a caller manufacture a favorable starting verdict -- no,
`overall` always starts at a literal `"READY"` and only ever caps, never widens), `SkillResult` construction
(never built from externally-influenced text anywhere in this module), a TODO/FIXME/HACK grep (zero matches),
and `test_engineering_delivery_lifecycle.py`'s continued validity against the current identity/digest rules
-- all clean.

### Fixed (adversarial review round 17 follow-up, same day)
- **`build_assessment_context`'s `candidate` override parameter used a shallow `dict(candidate)` copy, not a
  deep one -- the same mutation-aliasing defect class round 16 fixed for `code_review_coverage`, left open
  for `candidate`.** A caller-supplied `candidate` carrying nested mutable state (a dict/list value) remained
  mutable-in-place through `assessment_context["assessment_target"]` by a misbehaving `production_invoke`,
  since a shallow copy only protects the top-level keys. Not reachable via `run_release`/
  `resolve_production_readiness`'s own wiring today (their `_candidate_from_entry` output is always
  flat/scalar-only), but `candidate` is a documented public parameter of this function, and this module's own
  header docstring claims "pure, side-effect-free evidence logic" -- it must not be held to a weaker
  mutation-safety standard than its sibling `code_review_coverage` parameter. Fixed with the same
  `copy.deepcopy` treatment. Found by a third, confirmatory adversarial pass (the packaged code-review skill)
  after both of round 17's own independent passes came back clean.

Added 1 regression test. Full suite (1701 passed, 1 skipped), registry validate/generate-check, and
lint-release-readiness-checker all green.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — composition wrapper around pr-review + k8s-overprovisioning-datadog +
  incident-rca
- `workflow/inputs.md` — `release_manifest` (repo/service/since triples) + `incident_lookback_hours` +
  `target_branch` parsing, HARD STOP on missing/empty manifest
- `workflow/run-check.md` — MR-range resolver (genuinely new: pr-review's own docs only ever enumerate
  open MRs, never merged-in-a-date-range, paginated exhaustively), per-MR pr-review invocation, per-service
  k8s-overprovisioning-datadog invocation, per-service incident-rca Phase-1-only invocation, aggregation
- `reference/gate-policy.md` — normative gate answers for all three wrapped skills: pr-review reuses
  pr-gatekeeper's own real posting-gate policy; k8s's ambiguous-service-name ask answered with its own
  "proceed with unknown" fallback; incident-rca gates mostly avoided by construction (explicit UTC times,
  `service` anchor always supplied, 1-hour minimum lookback) except the Phase 1 checkpoint, always
  answered "stop here" regardless of signal density, overriding incident-rca's own default-to-proceed
- `reference/report-format.md` — normative `RELEASE_READINESS_REPORT.md` structure and verdict derivation,
  erring toward `Not ready` on anything unverified (unresolved MR range, `insufficient_metrics` service)
- Has a gate-policy file despite being human-invoked, unlike `new-hire-guide` — the fan-out over
  potentially many MRs/services means live per-invocation confirmations would defeat one aggregated
  report; see [SKILL.md](SKILL.md) § "Why a gate policy, despite being human-invoked"
- No `disable-model-invocation` — ambiently invocable, like `new-hire-guide`
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-release-readiness-checker-design.md](../docs/superpowers/specs/2026-08-05-release-readiness-checker-design.md)

### Fixed (round-1 review, same day)
- **Corrected a fabricated pr-review input.** The initial design assumed pr-review had a caller-settable
  `posting_mode: chat-only` "quiet mode" with zero live gates. It doesn't — `posting_mode` is derived
  entirely by pr-review's own Phase 0 from which GitLab MCP write tools are connected, never a caller
  input. In any realistic deployment with pr-review configured for normal write-capable use (which this
  skill's own SETUP.md assumes), invoking pr-review once per resolved MR would have produced exactly the
  N-live-interruptions problem this skill's gate-policy file exists to prevent. Fixed by reusing
  pr-gatekeeper's own real, already-solved posting-gate policy instead — invoke with a plain "review
  !`<iid>` in `<project>`" phrase, answer every ask-point pr-gatekeeper's own file enumerates, always
  decline to post.
- **Corrected a false "k8s has no gate" claim** — its single-service resolution path does have a live
  ambiguous-service-name ask; answered with k8s's own documented "proceed with unknown" fallback instead.
- **Added the missing incident-rca short-window gate** to the enumeration, closed by a documented 1-hour
  minimum on `incident_lookback_hours`.
- **Added exhaustive pagination** to the MR-range resolver (both the merge-date-filter path and its
  client-side fallback) — previously unspecified, risking a silently truncated MR set on a repo with more
  merged MRs than one page holds.
- **Added explicit handling for an unresolvable `since`** to `workflow/run-check.md` itself (previously
  only described in `smoke-test.md`, never in the operative workflow file) — recorded as unresolved, not
  silently dropped, and counted toward `Not ready`.
- **`insufficient_metrics` (k8s) and unresolved-`since` entries now count toward `Not ready`** rather than
  being silently excluded from the verdict — unverified is not the same as verified-safe.
- **Disclosed a known limitation**: the Phase-1-only incident signal can flag baseline/chronic noise
  unrelated to the release, since Phase 1 only detects symptoms, Phase 2 (never reached here) is what
  correlates them to a cause. "Flagged" means "worth a human look," not "confirmed release-caused."

### Fixed (skills audit — P0/P1 remediation)
- **Repaired retrospective MR review.** Every MR this skill resolves is already merged by construction
  (the `state: merged` query), but the skill previously invoked pr-review conversationally and reused
  pr-gatekeeper's "decline the post-merge audit" answer to pr-review's merged-MR stop — meaning pr-review
  HARD STOPped on 100% of invocations and no MR was ever actually reviewed, while the report still
  populated an MRs-reviewed row as if a review had happened. Fixed by invoking pr-review with explicit
  typed fields (`review_mode: retrospective`, `expected_head_sha`, `posting_policy: forbidden`) that
  select its retrospective audit path directly, added to pr-review itself as a documented typed-invocation
  mechanism for skill-to-skill callers.
- **Four-state verdict** (`READY`/`CONDITIONAL`/`NOT_READY`/`UNKNOWN`) replaces the prior two-state
  `Ready`/`Not ready`, which collapsed a proven blocker, an evidence gap (`insufficient_metrics`,
  unresolved `since`), and an unconfirmed incident signal into the same false-blocker bucket.
- **`ambiguous_unresolved` k8s outcome wired through** — k8s-overprovisioning-datadog no longer silently
  defaults ambiguous service resolution to `env:production`; this skill's gate policy and report format
  now handle the resulting `STOP_REASON: ambiguous_unresolved` the same honest-gap way as
  `insufficient_metrics`, instead of the stale documentation this file previously carried describing the
  removed default-to-production behavior.
