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
  open MRs, never merged-in-a-date-range), per-MR pr-review `chat-only` invocation, per-service
  k8s-overprovisioning-datadog invocation, per-service incident-rca Phase-1-only invocation, aggregation
- `reference/gate-policy.md` — normative incident-rca gate answers: everything avoided by construction
  (explicit UTC times, `service` anchor always supplied) except the Phase 1 checkpoint, always answered
  "stop here" regardless of signal density, overriding incident-rca's own default-to-proceed
- `reference/report-format.md` — normative `RELEASE_READINESS_REPORT.md` structure and verdict derivation
- Has a gate-policy file despite being human-invoked, unlike `new-hire-guide` — the fan-out over
  potentially many MRs/services means live per-invocation confirmations would defeat one aggregated
  report; see [SKILL.md](SKILL.md) § "Why a gate policy, despite being human-invoked"
- No `disable-model-invocation` — ambiently invocable, like `new-hire-guide`
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-release-readiness-checker-design.md](../docs/superpowers/specs/2026-08-05-release-readiness-checker-design.md)
