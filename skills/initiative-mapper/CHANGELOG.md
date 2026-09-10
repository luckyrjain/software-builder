# Changelog — initiative-mapper

## 1.0.0 — 2026-09-10

### Added

- Initial ambient, read-only initiative-mapper skill: breaks a large, foggy, too-big-for-one-session
  effort into a decision-ticket map with dependency edges, states which downstream skill each ticket
  is ready for (`engineering-decision-discovery`, `prd-architect`, or `implementation-planner`), and
  proposes report-only `INITIATIVE_MAP.md` / `initiative_map` output. Never writes a ticket, PRD, or
  plan directly.
