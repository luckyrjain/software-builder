# Changelog — squad-map

All notable changes to the squad-map skill. Per-file `workflow_version` in `workflow/*.md` frontmatter
should match the version of the latest entry below that names that file.

## [1.2.5] — 2026-08-09

### Added
- **reference/squad-mapping.md** — "Safe rendered-output boundary" section: `Repo`/`GitLab namespace`/
  `GitLab squad`/`Datadog service`/`Datadog team` all get structural newline/heading/pipe/fence/
  lone-backtick escaping (deliberately **not** code-span wrapping — several already-shipped downstream
  skills read these columns with an exact/verbatim string match, and wrapping would break every ordinary
  row's match, not just malicious ones)
- **workflow/phase-1.md** — Unmapped repos section, and the Scope-shrink bullet under Idempotency &
  partial runs (covering the Out of scope (archived) table), both cross-reference the same boundary
- **SKILL.md** — links `safe-output.md` and the new boundary section in its own "Untrusted content"
  paragraph

## [1.2.4] — 2026-07-31

### Added
- **reference/config-schema.md** — "Finding your own value" section for `squad_path_segment` (previously
  only a worked example using someone else's namespace) plus a wrong-value diagnostic
- **SETUP.md** — GitLab MCP JSON snippet inline (previously pointed elsewhere with no config of its own);
  clarified "optional config file" means the file, not the value — the skill asks interactively if
  neither config file exists
- **README.md** — rendered `SQUAD_MAP.md` excerpt in "What you get"

### Changed
- Marked acme-shaped examples (config-schema.md, gold-squad-map-excerpt.md) as illustrative — this
  org's real structure used to anchor the example, not a fixed convention

## [1.2.3] — 2026-07-31

### Added
- **templates/SQUAD_MAP.md** — "Out of scope (archived)" section, previously required by
  `workflow/phase-1.md` § Scope shrink but missing from the template and SKILL.md's Deliverable list
- **workflow/phase-1.md** — CODEOWNERS fallback behavior for no-matching-pattern (fall through to git
  log) and multiple-team-handle (record all, cap LOW, note ambiguity) cases, previously undefined

### Fixed
- **workflow/phase-1.md** — Required Outputs row for "Out of scope (archived)" pointed at a
  nonexistent `§ Out of scope` heading; corrected to match the actual section name

## [1.2.2] — 2026-07-07

### Added
- **workflow/phase-1.md** — pre-render attestation checklist before `SQUAD_MAP.md`

## [1.2.1] — 2026-07-07

### Fixed
- **scripts/squad_mapping.py** — `fuzzy_alias_match` → LOW; `confidence_for_codeowners_fallback()` → LOW
- **tests/test_squad_mapping.py** — coverage for fuzzy alias and CODEOWNERS paths
- **workflow/inputs.md** — untrusted-content guard at first ingest

## [1.2.0] — 2026-07-07

### Added
- **reference/gold-squad-map-excerpt.md** — format few-shot for Phase 1
- **reference/pressure-tests.md** — happy/edge/adversarial scenarios
- **scripts/squad_mapping.py** + **tests/test_squad_mapping.py** — namespace extraction, reconciliation, HARD STOP
- Shared **prompt-injection** and **skill-routing** links in SKILL.md

### Changed
- SKILL.md slimmed — mapping algorithm lives in workflow/phase-1 only

## [1.1.0] — 2026-07-06

### Added
- `squad_path_segment` documentation in SKILL.md (Critical config section)
- Mapping algorithm summary in SKILL.md
- This CHANGELOG

### Fixed
- HARD STOP behavior now documented for missing `squad_path_segment`

## [1.0.0] — 2026-06-30

### Added
- Initial skill release
- GitLab namespace → squad mapping via `get_project`
- Datadog service → team mapping via `search_datadog_services`
- CODEOWNERS fallback (confidence capped at LOW)
- Reconciliation logic (GitLab squad ≠ Datadog team → conflict flag)
- Integration with domain-comprehension Session 0b
- Shared framework compliance (confidence-bands, cross-skill-escalation)
