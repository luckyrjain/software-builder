# Changelog — incident-triage-agent

All notable changes to the incident-triage-agent skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

## [1.1.0] — 2026-08-09

### Added
- **workflow-contract.yaml** — route-aware contract modeling the `event_type` selector (`page_triggered`
  → triage route, `incident_resolved` → postmortem route), converting `workflow/inputs.md`,
  `workflow/triage.md`, `workflow/postmortem.md` frontmatter's `produces`/`consumes` from plain lists to
  the typed-mapping shape `scripts/validate_workflow_contracts.py` requires; wired into
  `make lint-incident-triage-agent`
- **reference/triage-doc-format.md**, **reference/postmortem-format.md** — "Safe rendered-output
  boundary" sections: `service`, `alert_title`/`symptom`, `alert_id`, `severity` (webhook payload) and
  squad-map's resolved squad name are untrusted here too — squad-map's own boundary (see squad-map's
  `[1.2.5]`) already structurally escapes the squad name but deliberately skips code-span wrapping, so
  this skill applies both steps locally rather than trusting squad-map's escaping blindly — short
  identifiers (`service`, `alert_id`, squad name) get structural escaping plus code-span wrapping, since
  `triage_doc`/`postmortem_draft` are terminal documents no downstream skill re-parses for exact
  matches; free text (`alert_title`, incident-rca's own
  not-yet-escaped hypothesis/report text) gets structural escaping only
- **reference/postmortem-format.md** — the Owner-column substitution bullet now also calls out that Step
  1 structural escaping applies at that exact site (a raw newline/pipe in the substituted squad name
  would break the table row it's substituted into), on top of the existing backtick-strip-not-escape
  guidance for the pre-existing code span
- **SKILL.md** — links [safe-output.md](../docs/skill-framework/shared/safe-output.md)
- `evals/golden/incident-triage-agent/injection-inert-triage-doc.yaml` — golden fixture proving a
  spoofed "## Likely cause" heading injected via `alert_title` never becomes a second live section, and
  that `service`/`alert_id`/`severity`/squad-map's squad name all render backtick-stripped and
  code-span-wrapped
- `evals/golden/incident-triage-agent/injection-inert-postmortem-owner.yaml` — golden fixture covering
  `postmortem_draft`'s Owner-column substitution specifically: a squad name containing an embedded pipe
  plus a raw newline and spoofed heading, substituted inside an existing table row and code span, must
  render inert without breaking the row into extra columns or extra lines

## [1.0.0] — 2026-08-05

### Added
- Initial skill release — paging-webhook-triggered composition of incident-rca (root cause) and
  squad-map (owning team), two modes: Triage (`page_triggered`) and Postmortem (`incident_resolved`)
- `reference/unattended-gate-policy.md` — exhaustive enumeration of every blocking gate in both
  incident-rca and squad-map with a deterministic answer, written exhaustive from the start using the
  lesson from pr-gatekeeper's `auto-post-policy.md` (which needed three review rounds to reach full
  coverage for a single wrapped skill)
- Per-mode window construction rules (30-min symmetric window for Triage; full incident duration,
  width-guaranteed, for Postmortem) so incident-rca's own timezone/window-width input gates never fire
- Postmortem mode reuses incident-rca's own Corrective/Preventive/Post-RCA-actions tables — no new
  action-item schema; its only original contribution is squad-map owner-column substitution
- `disable-model-invocation: true` — does not compete with incident-rca's or squad-map's ambient chat
  invocation
- Shared framework compliance (confidence-bands, cross-skill-escalation, prompt-injection, skill-routing)
- Design spec: [docs/superpowers/specs/2026-08-05-incident-triage-agent-design.md](../docs/superpowers/specs/2026-08-05-incident-triage-agent-design.md)
