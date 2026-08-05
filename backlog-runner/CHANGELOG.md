# Changelog — backlog-runner

All notable changes to the backlog-runner skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — item #7 of the [team-facing agents roadmap](../docs/superpowers/plans/2026-08-05-team-facing-agents-roadmap.md):
  a scheduled queue-management wrapper around loop-task-implementer, pulling N tickets from a
  Jira/GitHub Issues query and working through them overnight in dependency order
- `reference/queue-policy.md` — session-level state (extends, never modifies, loop-task-implementer's
  own per-task `state-schema.yaml`), queue pull/ordering/skip-existing rules, and — the one real
  ambiguity found in loop-task-implementer's own documented workflow — an explicit resolution that
  `HUMAN_ACTION_REQUIRED` continues the run (expected, normal outcome) while only a session-level
  circuit breaker stops it early
- `autonomous_merge_authorized` has no input path in this skill at all — hardcoded never-`true`, not a
  default that could be overridden
- Confirmed (not assumed) that loop-task-implementer, unlike pr-review/incident-rca, has no live
  synchronous "ask and wait" chat gates — every stop resolves to a terminal per-task report state
  (`HUMAN_ACTION_REQUIRED`/`ESCALATED`), so this skill needed no `pr-gatekeeper`-style "answer every
  gate" policy, only session-level queue bookkeeping
- `disable-model-invocation: true` — does not compete with loop-task-implementer's ambient invocation
- Shared framework compliance (cross-skill-escalation, prompt-injection, skill-routing);
  `confidence-bands.md`/`phase-glossary.md` don't apply, inheriting loop-task-implementer's own
  documented exemption
- Design spec: [docs/superpowers/specs/2026-08-05-backlog-runner-design.md](../docs/superpowers/specs/2026-08-05-backlog-runner-design.md)
