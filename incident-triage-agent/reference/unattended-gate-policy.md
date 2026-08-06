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
[phase-2.md](../../incident-rca/workflow/phase-2.md),
[phase-3.md](../../incident-rca/workflow/phase-3.md),
[reference/thresholds.md](../../incident-rca/reference/thresholds.md),
[reference/query-playbook.md](../../incident-rca/reference/query-playbook.md),
[reference/mcp-capabilities.md](../../incident-rca/reference/mcp-capabilities.md).

| # | Gate | Avoidable by construction? | This skill's answer |
|---|------|------------------------------|------------------------|
| 1 | Vague prompt (no window/anchor) — [inputs.md](../../incident-rca/workflow/inputs.md) | **Yes** | Never invoke with a vague prompt — [workflow/triage.md](../workflow/triage.md) and [workflow/postmortem.md](../workflow/postmortem.md) always supply an explicit `service` anchor and UTC-suffixed window |
| 2 | Missing timezone suffix — "ask... confirm UTC or local — do not assume UTC silently" | **Yes** | Always emit fully-qualified ISO-8601 with `Z`/`±HH:MM` |
| 3 | Window < 10 min (ask) / < 5 min (blocks Phase 4 without confirmation) | **Yes** | Always construct a window ≥ 30 minutes wide (see per-mode window rules below) |
| 4 | No observability MCP at all (Datadog and KubeSense both absent) — [phase-0.md](../../incident-rca/workflow/phase-0.md) hard stop; same treatment covers the `oss-obs` degraded-mode variant in [mcp-capabilities.md](../../incident-rca/reference/mcp-capabilities.md) ("ask the user to paste PromQL/LogQL results" when only Prometheus/Loki/Grafana are configured with no query-execution MCP) | No — genuine setup gap | Cannot proceed with investigation. Produce the doc anyway, stating "incident-rca has no observability MCP configured" (or "query-execution unavailable in oss-obs mode") in place of findings, and route it via the same notification path as a squad-map-UNKNOWN case (§ below) — never leave the webhook caller with nothing |
| 5 | Multi-site Datadog, ambiguous — [phase-0.md](../../incident-rca/workflow/phase-0.md) | No — runtime-dependent | Query **all** known sites, cap confidence at **MEDIUM**, note the ambiguity in the doc's Gaps section — never pick one site silently |
| 6 | Symptom-only org-wide discovery ask (has a documented "pick highest-magnitude" escape hatch) — [phase-1.md](../../incident-rca/workflow/phase-1.md) | **Yes** | Never invoke with symptom-only — always supply `service` explicitly. If it fires anyway (unexpected), answer **"just pick one"** (the documented fallback phrase) |
| 7 | Sparse signal ask ("Signal is thin — continue to deploy correlation or stop here?") — [thresholds.md](../../incident-rca/reference/thresholds.md) | No — runtime-dependent | **"Continue"** — a triage/postmortem doc built on thin evidence is still more useful than none; note thinness in Gaps |
| 8 | **Phase 2 checkpoint (before Phase 3)** — [phase-2.md § Phase 2 checkpoint](../../incident-rca/workflow/phase-2.md#phase-2-checkpoint-before-phase-3) — fires on essentially every run that reaches Phase 2, not an edge case. Three signal-state rows offer different option sets, but the workflow separately documents two recognized reply phrases that apply regardless of which row fired: *"User says 'stop' → Phase 5 partial report. User says 'skip Jira'/'skip Phase 3' → jump directly to Phase 4."* | No — fires on the default path | **Triage mode: always reply `"skip Phase 3"`** — jumps straight to Phase 4 ranking, skipping Jira/recurrence search, regardless of which signal-state row is showing. This is the *actual* mechanism for triage mode's speed goal — not a phrase added to the opening invocation (see [workflow/triage.md](../workflow/triage.md), which no longer attempts that). **Postmortem mode: always reply `"continue to Phase 3"`** (option A) — full thoroughness includes Jira/recurrence search. **Neither mode ever replies `"stop"`** — a partial report short-circuits Phase 4 ranking entirely, which both modes need |
| 9 | Jira project keys unknown (blocks Jira ticket search in Phase 3) — [phase-3.md](../../incident-rca/workflow/phase-3.md) | Mode-dependent | **Triage mode:** N/A — gate #8's answer means triage never reaches Phase 3 at all. **Postmortem mode:** pre-configure `jira_project_keys` per [SETUP.md](../SETUP.md) § Config; if still unset when this fires, answer **"skip Jira ticket search"** and note the gap — never block the postmortem draft on it |
| 10 | `pd_service_id` unresolved from a name filter — [query-playbook.md § PagerDuty / OpsGenie](../../incident-rca/reference/query-playbook.md) — *"use `pd_list_services` filtered by service name if available, or ask the user"* | No — runtime-dependent, but low-likelihood (Phase 0's own PD quick-check queries `service_ids: [<service>]` directly and doesn't route through this resolution in the common path) | If it fires: skip PD-specific service-ID resolution and proceed using the `service` name and `alert_id` already passed through — never block investigation waiting on a PagerDuty service ID lookup |
| — | "None density" (no signals at all found) | N/A — not a gate | incident-rca's own terminal state: it renders "No observability data found for this window" and stops ranking — not a wait. No answer needed, just accept the terminal report |
| — | Insufficient evidence for a root cause (all hypotheses ≤ MEDIUM) | N/A — not a gate | incident-rca's own terminal state: "No defensible root cause identified." Also not a wait — render the doc with that conclusion |

**Jira-anchored path gates** (`phase-0b.md`'s window-from-ticket and its own timezone-confirm) never apply
— this skill always anchors on the page's own `triggered_at`/`resolved_at`, never a `jira_key`.

## squad-map gates

| Gate | Avoidable by construction? | This skill's answer |
|------|------------------------------|------------------------|
| squad-map not installed at all (no `squad-map/SKILL.md` reachable) | No — genuine setup error | Proceed with owning team **UNKNOWN**, note "squad-map not installed" in the doc's Gaps — mirrors [who-owns-x-bot/workflow/lookup.md](../../who-owns-x-bot/workflow/lookup.md) Step 1's identical handling. `make install-incident-triage-agent` always installs squad-map alongside it, so this should only happen from a broken manual install |
| `squad_path_segment` HARD STOP (no config file, GitLab available) — [squad-map/workflow/inputs.md](../../squad-map/workflow/inputs.md) | No — genuine setup/config gap unless pre-provisioned | Proceed with owning team **UNKNOWN**, noted as a gap in the doc — mirrors [who-owns-x-bot/workflow/lookup.md](../../who-owns-x-bot/workflow/lookup.md) Step 3's identical handling of this same squad-map gate. Never block the triage doc or postmortem on ownership resolution — a page needs a triage doc *now* even if ownership can't be resolved yet |

Pre-provisioning `squad-map-config.yaml` (or `domain-config.yaml`) at the configured `workspace_root`
avoids the second gate entirely — recommended in [SETUP.md](../SETUP.md) § Config, same as squad-map's
own setup guidance.

**Not a blocking gate, but a real reliability risk worth flagging explicitly:** squad-map's GitLab lens
matches repo/folder *names* and its Datadog lens matches service *names*
([squad-map/reference/squad-mapping.md](../../squad-map/reference/squad-mapping.md)) — neither is
guaranteed to equal the paging system's `service` field verbatim. A name mismatch degrades safely to the
`UNKNOWN` gate above (never a hang), but silently — the resulting doc says "owner UNKNOWN" with no hint
that the actual cause is a naming mismatch rather than a genuinely unmapped service. Configure
`ownership.datadog.service_aliases` in `squad-map-config.yaml` (paging `service` name → squad-map's
expected name) per [squad-map/reference/config-schema.md](../../squad-map/reference/config-schema.md) to
close this gap — see [SETUP.md](../SETUP.md) § Config.

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
| Triage | `triggered_at − 20m` | `triggered_at + 10m` | 30 min total, weighted toward before the page (20m pre / 10m post — not symmetric) — never depends on invocation latency (see [workflow/triage.md](../workflow/triage.md)) |
| Postmortem | `triggered_at` | `resolved_at`, extended per below | The actual incident duration, padded only enough to clear incident-rca's short-window gate — see below |

**Postmortem window extension (P1 fix — padding must not silently extend past `resolved_at` uncredited):**
when `resolved_at − triggered_at < 30m`, incident-rca's own gate #3 (window < 10m asks, < 5m blocks) would
fire on a genuinely short, already-resolved incident — undesirable, since this mode always wants Phase 4
to run. The fix is padding, not a redefinition of the incident's duration:

- `to_time` is extended to `triggered_at + 30m` **only to satisfy the gate** — this pads the *query*
  window, it does not mean the incident itself lasted 30 minutes.
- The padded portion (from the real `resolved_at` to the padded `to_time`) is **post-resolution
  context**, not incident-causal time — a signal that happens to fall in that padded slice occurred after
  the incident was already resolved and must not be attributed as part of the incident's own causal
  chain. [workflow/postmortem.md](../workflow/postmortem.md) records `resolved_at` alongside the padded
  `to_time` in the doc's window line specifically so a reader (or a later correlation pass) can tell real
  incident duration from query padding — never render only the padded `from_time`–`to_time` pair as if it
  were the incident's own duration.

Both always UTC-suffixed ISO-8601, both always paired with an explicit `service` anchor — see
[workflow/inputs.md](../workflow/inputs.md).
