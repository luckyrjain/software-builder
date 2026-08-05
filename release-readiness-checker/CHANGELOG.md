# Changelog — release-readiness-checker

All notable changes to the release-readiness-checker skill. Per-file `workflow_version` in
`workflow/*.md` frontmatter should match the version of the latest entry below that names that file.

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
