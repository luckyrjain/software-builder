# incident-triage-agent

**Paging-webhook-triggered composition of incident-rca and squad-map.** Page fires → fast triage doc
(root cause + owning team) for on-call. Incident resolves → drafted postmortem using incident-rca's own
report with squad-map-filled owner columns. No new investigation or ownership logic — a thin composition.

Unlike incident-rca and squad-map, this skill does **not** auto-invoke from ambient chat
(`disable-model-invocation: true`). It's called explicitly by the paging-webhook integration described
in [SETUP.md](SETUP.md).

## What it does

1. **Fires on a paging-system webhook** — `page_triggered` → Triage mode; `incident_resolved` →
   Postmortem mode.
2. **Invokes incident-rca** for root-cause investigation — fast/narrow window in Triage mode, full
   window/thoroughness in Postmortem mode.
3. **Invokes squad-map** for the owning team.
4. **Answers every gate either skill stops at**, deterministically, per
   [reference/unattended-gate-policy.md](reference/unattended-gate-policy.md) — never hangs, never
   invents an answer beyond what's documented there.
5. **Produces one doc per event** — a short triage doc, or a full postmortem draft with pre-assigned
   follow-up owners — routed to the configured notification path.

## When to use

| Use incident-triage-agent | Use instead |
|------------------------------|--------------|
| PagerDuty/Opsgenie page-fire or incident-resolved webhook | Interactive "RCA for X" → **incident-rca** directly |
| — | Interactive "who owns X" → **squad-map** directly |
| — | Full multi-repo squad map, not one incident's ownership → **squad-map** |

## Invocation examples

```
event_type: page_triggered, service: neo-disbursement-service, triggered_at: 2026-08-05T14:22:00Z, severity: P1
event_type: incident_resolved, service: neo-disbursement-service, triggered_at: 2026-08-05T14:22:00Z, resolved_at: 2026-08-05T15:40:00Z
```

## What you get

**Triage:** a short doc — likely cause (or "no defensible root cause"), owning team (or UNKNOWN), gaps,
a pointer to the full RCA. **Postmortem:** incident-rca's full report, unedited except for owner-column
substitution in its own Corrective/Preventive/Post-RCA-actions tables.

## Install

```bash
cd software-builder
make install-incident-triage-agent
```

Restart Cursor. Requires **incident-rca** and **squad-map** installed and configured (the make target
chains both automatically) — see [incident-rca/SETUP.md](../incident-rca/SETUP.md) and
[squad-map/SETUP.md](../squad-map/SETUP.md) — plus the paging-webhook integration contract in
[SETUP.md](SETUP.md).

## Related skills

- **incident-rca** — does the actual investigation; this skill decides when to invoke it unattended and
  how to answer its gates
- **squad-map** — does the actual ownership computation
- **who-owns-x-bot**, **pr-gatekeeper** — the same "thin webhook wrapper, deterministic gate answers"
  pattern applied to a single wrapped skill each; this skill applies it to two at once

Agent instructions: [SKILL.md](SKILL.md).
