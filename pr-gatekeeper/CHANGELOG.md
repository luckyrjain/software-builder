# Changelog — pr-gatekeeper

All notable changes to the pr-gatekeeper skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — thin webhook-triggered wrapper around pr-review, auto-running review on every
  push to an open MR
- `reference/auto-post-policy.md` — the two-message protocol reconciling an unattended run with
  pr-review's own Phase 3 confirmation gate (opening phrase depends on `auto_post_authorized`; a single
  deterministic "Hold — don't post" reply whenever pr-review's Phase 3 stops and waits) — never bypasses
  `general-only` or draft-MR confirmation, matching pr-review's own non-negotiable rules
- `workflow/inputs.md` — webhook event filtering (push-only, open-MR-only, `head_sha` dedupe short-circuit)
- `disable-model-invocation: true` — does not compete with pr-review's ambient chat invocation
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing)
- Design spec: [docs/superpowers/specs/2026-08-05-pr-gatekeeper-design.md](../docs/superpowers/specs/2026-08-05-pr-gatekeeper-design.md)
