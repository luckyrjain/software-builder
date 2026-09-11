# Changelog — stakeholder-questionnaire

## 1.0.0 — 2026-09-11

### Added

- Initial ambient, read-only stakeholder-questionnaire skill: turns an unresolvable decision into a
  discovery questionnaire for one named recipient. Drafts `STAKEHOLDER_QUESTIONNAIRE.md` /
  `stakeholder_questionnaire` output — questions targeted at the gap between what the recipient
  knows and what the caller needs back, grouped by theme, most-important-first. Never sends, posts,
  or writes the questionnaire to disk; it is the report/artifact response only.
- Routing requires the questionnaire to be the object of an active request — a create/prepare/send
  verb taking it (singular or plural) as its object, or "the questionnaire you draft …". A bare
  mention of a questionnaire inside another skill's question, and "the questionnaire
  service/form/table" naming a system under discussion, deliberately do not route here: both were
  reproduced false-positive classes against the original bare `\bquestionnaire\b` anchor. See the
  routing comment in `scripts/registry/skills.d/stakeholder-questionnaire.yaml` and
  `scripts/tests/test_stakeholder_questionnaire_routing.py`.
- The report opens with a `title` that names the decision being unblocked — the same string as the
  typed artifact's `title` field, bound in the Report phase and asserted by both golden fixtures.
