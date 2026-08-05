# Changelog — new-hire-guide

All notable changes to the new-hire-guide skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — thin composition wrapper around domain-comprehension + squad-map
- `workflow/inputs.md` — `new_hire` (name, squad, optional start date/role) + `workspace_root` +
  `delivery_mode` parsing, HARD STOP on missing required fields
- `workflow/run-tour.md` — resolves the new hire's squad to repos via squad-map's own `SQUAD_MAP.md`
  (auto-discover, reusing squad-map's own `refresh: false` default), scopes domain-comprehension to just
  those repos via `domain-config.yaml`'s existing `scope.seed_repos`, builds `ONBOARDING_TOUR.md`
- `reference/tour-format.md` — normative `ONBOARDING_TOUR.md` structure; curate-and-link, never restate
- No gate-policy override file — unlike `pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`, both
  wrapped skills' own live gates (domain-comprehension's Session 0 checkpoint, squad-map's
  `squad_path_segment` HARD STOP) surface unscripted, since a human is always present for this flow
- No `disable-model-invocation` — ambiently invocable, unlike the four unattended/webhook wrappers
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-new-hire-guide-design.md](../docs/superpowers/specs/2026-08-05-new-hire-guide-design.md)
