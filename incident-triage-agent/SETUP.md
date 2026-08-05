# incident-triage-agent — Setup

## Ambient discovery is deliberately disabled

Unlike incident-rca and squad-map, this skill sets `disable-model-invocation: true` — it does not
auto-apply from a human's natural-language chat turn. It's meant to be invoked explicitly, with a
structured paging-webhook payload, by the automation described below. A human asking for an RCA or an
ownership lookup interactively should keep routing to **incident-rca** / **squad-map** directly.

## Install

```bash
cd ai-skills
make install-incident-triage-agent
```

This chains `make install-incident-rca` and `make install-squad-map` first — this skill has no
investigation or ownership logic of its own and is useless without both installed alongside it. Restart
Cursor so all three skills reload.

### Claude Code

```bash
cd ai-skills
make install-claude-incident-triage-agent
```

No restart needed. See [claude-code-setup.md](../docs/skill-framework/shared/claude-code-setup.md).

### Kiro / in-repo discovery

Working directly in this repo? `.cursor/rules/incident-triage-agent.mdc` and
`.kiro/steering/incident-triage-agent.md` point Cursor/Kiro at `incident-triage-agent/SKILL.md` without
an install step.

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| incident-rca installed and configured | ≥1 observability MCP (Datadog or KubeSense) — see [incident-rca/SETUP.md](../incident-rca/SETUP.md) |
| squad-map installed and configured | GitLab/Datadog, or CODEOWNERS fallback — see [squad-map/SETUP.md](../squad-map/SETUP.md) |
| A paging-webhook handler | Registers the PagerDuty/Opsgenie webhook and invokes an agent session with this skill — see § Integration contract |

## Integration contract (for whoever builds the paging-webhook handler)

This repo ships **agent instructions**, not a running webhook receiver — same boundary as
who-owns-x-bot's Slack handler and pr-gatekeeper's GitLab handler. The handler you build:

1. Registers a PagerDuty (or Opsgenie) webhook subscription for `incident.triggered` and
   `incident.resolved` (naming varies by paging system — map both to this skill's `event_type:
   page_triggered` / `event_type: incident_resolved`).
2. On each delivery, extracts `service`, `triggered_at` (and `resolved_at` for a resolved event),
   `alert_title`, `alert_id`, `severity` from the payload, normalizing all timestamps to UTC-suffixed
   ISO-8601 before passing them in — [workflow/inputs.md](workflow/inputs.md) HARD STOPs rather than
   guessing a timezone.
3. Starts (or reuses) an agent session with this skill installed, passing the fields above plus
   `workspace_root`.
4. Implements the **deterministic-reply protocol** this skill's workflow depends on for both wrapped
   skills — see [reference/unattended-gate-policy.md](reference/unattended-gate-policy.md) for the full,
   exhaustive list: answer every gate incident-rca or squad-map stops at with its one designated reply.
   Never send any other reply, never leave a stopped session unanswered.
5. Delivers the returned triage doc or postmortem draft to wherever § Config points (on-call channel,
   incident-channel thread, wiki, etc.) — this skill's own output is just text, the handler does the
   actual delivery.

## Config

| Setting | Where | Purpose |
|---------|-------|---------|
| Default `workspace_root` | Handler config, passed as input | Where squad-map should look for `SQUAD_MAP.md` / config |
| `jira_project_keys` | Handler config, or pre-provisioned via incident-rca's own org profile | Avoids [reference/unattended-gate-policy.md](reference/unattended-gate-policy.md) gate #9 in Postmortem mode — recommended, not required (the gate degrades gracefully if unset) |
| Pre-provisioned `squad-map-config.yaml` / `domain-config.yaml` at `workspace_root` | Repo config file | Avoids the squad-map HARD STOP gate entirely — recommended, not required (degrades to owner UNKNOWN if unset) |
| `ownership.datadog.service_aliases` in `squad-map-config.yaml` | Repo config file | Maps the paging system's `service` field to squad-map's expected repo/Datadog service name when they don't match verbatim — see [reference/unattended-gate-policy.md § squad-map gates](reference/unattended-gate-policy.md#squad-map-gates). Without it, a name mismatch degrades silently to owner UNKNOWN rather than failing loudly, so this is worth setting up even though nothing hangs without it |
| Notification target(s) | Handler config | Where triage docs / postmortem drafts get routed — on-call channel for triage, incident-retro channel or wiki for postmortem |

## Framework links

- [skill-framework README](../docs/skill-framework/README.md)
- [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
- [cross-skill-escalation](../docs/skill-framework/shared/cross-skill-escalation.md)

## Smoke test

After install, run the invocations in [reference/smoke-test.md](reference/smoke-test.md) (both modes)
against a service both incident-rca and squad-map can already resolve.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Every triage doc says "no defensible root cause" | Check incident-rca itself resolves the same service/window when asked directly — see [incident-rca/SETUP.md](../incident-rca/SETUP.md) |
| Owning team always UNKNOWN | Check squad-map itself resolves the same service — see [squad-map/SETUP.md § Troubleshooting](../squad-map/SETUP.md#troubleshooting) |
| Handler hangs waiting for a reply that never comes | Handler isn't answering every gate in [reference/unattended-gate-policy.md](reference/unattended-gate-policy.md) — a multi-site Datadog ambiguity or sparse signal stops incident-rca just as surely as a missing config stops squad-map |
| Postmortem mode blocked on Jira ticket search | Set `jira_project_keys` per § Config, or accept the documented "skip Jira search" fallback |
