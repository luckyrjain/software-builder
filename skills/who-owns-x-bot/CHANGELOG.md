# Changelog — who-owns-x-bot

All notable changes to the who-owns-x-bot skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — thin Slack-bot-facing wrapper around squad-map
- `workflow/inputs.md` — `query` + optional `workspace_root` parsing, HARD STOP on empty query
- `workflow/lookup.md` — delegates ownership computation entirely to squad-map; classifies into
  Resolved / Ambiguous / Unknown; LOW confidence folded into Unknown (no confidence caveat possible in a
  single-shot reply)
- `reference/slack-format.md` — normative three-shape reply spec
- `disable-model-invocation: true` — does not compete with squad-map's ambient chat invocation
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing)
- Design spec: [docs/superpowers/specs/2026-08-05-who-owns-x-bot-design.md](../docs/superpowers/specs/2026-08-05-who-owns-x-bot-design.md)
