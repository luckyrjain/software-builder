# Changelog — new-hire-guide

All notable changes to the new-hire-guide skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — thin composition wrapper around domain-comprehension + squad-map
- `workflow/inputs.md` — `new_hire` (name, squad, optional start date/role) + `workspace_root` +
  `delivery_mode` parsing, HARD STOP on missing required fields
- `workflow/run-tour.md` — resolves the new hire's squad to repos via squad-map's own `SQUAD_MAP.md`
  (auto-discover, reusing squad-map's own `refresh: false` default), runs domain-comprehension
  **unscoped**, curates `ONBOARDING_TOUR.md` down to just the matched repos afterward
- `reference/tour-format.md` — normative `ONBOARDING_TOUR.md` structure; curate-and-link, never restate
- No gate-policy override file — unlike `pr-gatekeeper`/`incident-triage-agent`/`backlog-runner`, both
  wrapped skills' own live gates (domain-comprehension's Session 0 checkpoint, squad-map's
  `squad_path_segment` HARD STOP) surface unscripted, since a human is always present for this flow
- No `disable-model-invocation` — ambiently invocable, unlike the four unattended/webhook wrappers
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing,
  phase-glossary)
- Design spec: [docs/superpowers/specs/2026-08-05-new-hire-guide-design.md](../docs/superpowers/specs/2026-08-05-new-hire-guide-design.md)

### Fixed (round-1 review, same day)
- **Removed `domain-config.yaml scope.seed_repos` narrowing** — the original design scoped
  domain-comprehension's own census to the matched repos, which cascaded through its mandatory Session 0b
  squad-map delegation and triggered squad-map's own scope-shrink archival on the **shared**
  `SQUAD_MAP.md`, silently moving every other squad's rows to § Out of scope (archived) on every run.
  domain-comprehension now always runs unscoped; curation to the new hire's repos happens entirely in
  `workflow/run-tour.md` § 4, over domain-comprehension's full output.
- **Corrected a false "no ambient-routing collision" claim** — domain-comprehension's own `description`
  frontmatter does mention "subsystem onboarding," genuinely overlapping with this skill's trigger
  phrases. Added an explicit person-named disambiguation rule to `skill-routing.md` and a cross-reference
  row to `domain-comprehension/SKILL.md`'s own routing table.
