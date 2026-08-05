# Unattended gate policy (normative)

**The one piece of new logic in this skill.** Everything else is incident-rca's and squad-map's own. This
file enumerates, exhaustively, every point either skill stops and waits for a human reply — and gives
each one a deterministic answer, so a webhook-triggered run never hangs. Written exhaustive from the
start: `pr-gatekeeper/reference/auto-post-policy.md` needed three review rounds to reach full gate
coverage for a single wrapped skill; this file covers **two** wrapped skills and is built directly on
that lesson — enumerate every gate up front, in both skills' actual documented text, not just the
obvious ones.

Two families of gate: ones **avoidable by construction** (a well-formed invocation string never triggers
them) and ones that are **genuinely runtime-evidence-dependent** (no invocation string avoids them; they
need an actual deterministic answer). Both families are listed below — do not skip the "avoidable"
category, since a mistake in constructing the invocation string turns it into a live gate.

## incident-rca gates

Source: [incident-rca/workflow/inputs.md](../../incident-rca/workflow/inputs.md),
[phase-0.md](../../incident-rca/workflow/phase-0.md),
[phase-1.md](../../incident-rca/workflow/phase-1.md),
[phase-3.md](../../incident-rca/workflow/phase-3.md),
[reference/thresholds.md](../../incident-rca/reference/thresholds.md).

| # | Gate | Avoidable by construction? | This skill's answer |
|---|------|------------------------------|------------------------|
| 1 | Vague prompt (no window/anchor) — [inputs.md](../../incident-rca/workflow/inputs.md) | **Yes** | Never invoke with a vague prompt — [workflow/triage.md](../workflow/triage.md) and [workflow/postmortem.md](../workflow/postmortem.md) always supply an explicit `service` anchor and UTC-suffixed window |
| 2 | Missing timezone suffix — "ask... confirm UTC or local — do not assume UTC silently" | **Yes** | Always emit fully-qualified ISO-8601 with `Z`/`±HH:MM` |
| 3 | Window < 10 min (ask) / < 5 min (blocks Phase 4 without confirmation) | **Yes** | Always construct a window ≥ 30 minutes wide (see per-mode window rules below) |
| 4 | No observability MCP at all (Datadog and KubeSense both absent) — [phase-0.md](../../incident-rca/workflow/phase-0.md) hard stop | No — genuine setup gap | Cannot proceed with investigation. Produce the doc anyway, stating "incident-rca has no observability MCP configured" in place of findings, and route it via the same notification path as a squad-map-UNKNOWN case (§ below) — never leave the webhook caller with nothing |
| 5 | Multi-site Datadog, ambiguous — [phase-0.md](../../incident-rca/workflow/phase-0.md) | No — runtime-dependent | Query **all** known sites, cap confidence at **MEDIUM**, note the ambiguity in the doc's Gaps section — never pick one site silently |
| 6 | Symptom-only org-wide discovery ask (has a documented "pick highest-magnitude" escape hatch) — [phase-1.md](../../incident-rca/workflow/phase-1.md) | **Yes** | Never invoke with symptom-only — always supply `service` explicitly. If it fires anyway (unexpected), answer **"just pick one"** (the documented fallback phrase) |
| 7 | Sparse signal ask ("Signal is thin — continue to deploy correlation or stop here?") — [thresholds.md](../../incident-rca/reference/thresholds.md) | No — runtime-dependent | **"Continue"** — a triage/postmortem doc built on thin evidence is still more useful than none; note thinness in Gaps |
| 8 | Jira project keys unknown (blocks Jira ticket search in Phase 3) — [phase-3.md](../../incident-rca/workflow/phase-3.md) | Mode-dependent | **Triage mode:** N/A — triage never runs Phase 3 Jira search (skipped for speed, see [workflow/triage.md](../workflow/triage.md)). **Postmortem mode:** pre-configure `jira_project_keys` per [SETUP.md](../SETUP.md) § Config; if still unset when this fires, answer **"skip Jira ticket search"** and note the gap — never block the postmortem draft on it |
| — | "None density" (no signals at all found) | N/A — not a gate | incident-rca's own terminal state: it renders "No observability data found for this window" and stops ranking — not a wait. No answer needed, just accept the terminal report |
| — | Insufficient evidence for a root cause (all hypotheses ≤ MEDIUM) | N/A — not a gate | incident-rca's own terminal state: "No defensible root cause identified." Also not a wait — render the doc with that conclusion |

**Jira-anchored path gates** (`phase-0b.md`'s window-from-ticket and its own timezone-confirm) never apply
— this skill always anchors on the page's own `triggered_at`/`resolved_at`, never a `jira_key`.

## squad-map gate

| Gate | Avoidable by construction? | This skill's answer |
|------|------------------------------|------------------------|
| `squad_path_segment` HARD STOP (no config file, GitLab available) — [squad-map/workflow/inputs.md](../../squad-map/workflow/inputs.md) | No — genuine setup/config gap unless pre-provisioned | Proceed with owning team **UNKNOWN**, noted as a gap in the doc — mirrors [who-owns-x-bot/workflow/lookup.md](../../who-owns-x-bot/workflow/lookup.md) Step 3's identical handling of this same squad-map gate. Never block the triage doc or postmortem on ownership resolution — a page needs a triage doc *now* even if ownership can't be resolved yet |

Pre-provisioning `squad-map-config.yaml` (or `domain-config.yaml`) at the configured `workspace_root`
avoids this gate entirely — recommended in [SETUP.md](../SETUP.md) § Config, same as squad-map's own
setup guidance.

## Post-report offers (both skills — always declined)

Neither skill ever gets to auto-post anything on this skill's behalf; every "offer, then wait" surfaces
as a **paste-ready block rendered into this skill's own doc** instead — mirrors exactly how
`pr-gatekeeper` resolved pr-review's analogous Jira/Slack offers.

| Offer | Source | This skill's answer |
|-------|--------|------------------------|
| Post-RCA actions Jira/Slack paste | [incident-rca/report-template.md § Post-RCA actions](../../incident-rca/report-template.md) | Decline the live post; include the paste-ready Jira comment / Slack brief text (per [post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md) §1, §4) as a block in the doc |
| Confluence/wiki export paste | incident-rca's report-template.md § Confluence/wiki export mapping | Decline the live post; include the export-ready text as a block in the doc |

## Per-mode window construction

| Mode | `from_time` | `to_time` | Width guarantee |
|------|-------------|-----------|-------------------|
| Triage | `triggered_at − 20m` | `triggered_at + 10m` | 30 min, symmetric around the page — never depends on invocation latency (see [workflow/triage.md](../workflow/triage.md)) |
| Postmortem | `triggered_at` | `resolved_at` | The actual incident duration; if `resolved_at − triggered_at < 30m`, extend `to_time` to `triggered_at + 30m` so gate #3 above never fires on a very short incident |

Both always UTC-suffixed ISO-8601, both always paired with an explicit `service` anchor — see
[workflow/inputs.md](../workflow/inputs.md).
