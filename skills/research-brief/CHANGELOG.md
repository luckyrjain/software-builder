# Changelog — research-brief

## 1.0.0 — 2026-09-10

### Added

- Initial ambient, read-only research-brief skill: investigates a bounded research question against
  repository evidence and, when available, external documentation, citing every claim's source and
  evidence status. Degrades to repository-only research and marks external-dependent claims `UNKNOWN`
  when `host.web.search`/`host.web.fetch` are unavailable. Produces report-only `RESEARCH_BRIEF.md` /
  `research_brief` output. Never edits source, tests, configuration, or docs, and never commits, pushes,
  or opens a PR.
