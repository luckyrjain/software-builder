# Changelog — incident-triage-agent

All notable changes to the incident-triage-agent skill. Per-file `workflow_version` in `workflow/*.md`
frontmatter should match the version of the latest entry below that names that file.

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
