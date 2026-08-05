# incident-rca Round 3 Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 4 gaps from the Round 3 gap analysis for the incident-rca skill: Phase 0b window expansion (P2-2), slo_breach-only investigation path (P1-3), runbook lookup deduplication (P2-3), and PagerDuty/OpsGenie detection (P3-1).

**Architecture:** All changes are targeted additions to existing workflow and reference files. Task order: P2-2 first (smallest, lowest risk), then P1-3 (phase-1.md addition), then P2-3 (dedup across phase-1.md and phase-4.md), then P3-1 (phase-0.md + query-playbook.md).

**Tech Stack:** Markdown skill documents under `incident-rca/`.

## Global Constraints

- All files are under `incident-rca/`
- Pressure tests file is `reference/pressure-tests.md`
- Changes are purely additive — do not restructure or rewrite existing content
- `phase-0b.md` is only loaded when `jira_key` is given (keep that scope)
- All new query recipes in `reference/query-playbook.md` follow the existing format with `telemetry` blocks

---

### Task 1: P2-2 — Phase 0b Window Anchor Expansion

**Files:**
- Modify: `incident-rca/workflow/phase-0b.md` (add backstroke step after anchoring from_time)
- Modify: `incident-rca/reference/pressure-tests.md` (add 1 pressure test row)

**Interfaces:**
- Produces: `analysis_from_time` (= `from_time − 15m`) as the actual query start used in Phase 1
- Consumes: `from_time` as anchored from ticket description/comments

- [ ] **Step 1: Add pressure test row**

  Read `incident-rca/reference/pressure-tests.md` to find the table. Append:

  ```markdown
  | Jira ticket `created_at` = 14:30; description says "issues started around 14:25" | `from_time = 14:25`; `analysis_from_time = 14:10` (−15m backstroke); Phase 1 queries use `analysis_from_time` |
  ```

- [ ] **Step 2: Add the backstroke step to `incident-rca/workflow/phase-0b.md`**

  Read the current file. After step 3 ("Set / refine `from_time`, `to_time`, `service`, and `symptom` from the ticket, then proceed to Phase 1."), append a step 4:

  ```markdown
  4. **Backstroke 15 minutes:** after anchoring `from_time`, automatically subtract 15 minutes:

     ```
     analysis_from_time = from_time − 15m
     ```

     Use `analysis_from_time` for **all Phase 1 observability queries**. Report both values clearly:

     > **Window:** Incident start (reported): `<from_time>` | Query start (backstroke): `<analysis_from_time>` | End: `<to_time>`

     **Rationale:** on-call response lag and human reporting delay mean the reporter's first timestamp
     is often 10–20 minutes after the first abnormal signal. The backstroke exposes the pre-ticket
     degradation period where the earliest root-cause signal typically lives.

     Do not expand `to_time` — the backstroke applies to the start only.
  ```

- [ ] **Step 3: Verify additions**

  ```bash
  grep -n "backstroke\|analysis_from_time" \
    /Users/luckyjain/Projects/ai-skills/incident-rca/workflow/phase-0b.md \
    /Users/luckyjain/Projects/ai-skills/incident-rca/reference/pressure-tests.md
  ```
  Expected: hits in both files.

- [ ] **Step 4: Commit**

  ```bash
  git add \
    incident-rca/workflow/phase-0b.md \
    incident-rca/reference/pressure-tests.md
  git commit -m "feat(rca): P2-2 — Phase 0b window backstroke 15 minutes before reported from_time"
  ```

---

### Task 2: P1-3 — SLO Breach Investigation Path When Logs Are Missing

**Files:**
- Modify: `incident-rca/workflow/phase-1.md` (add slo_breach-only fallback block)
- Modify: `incident-rca/reference/pressure-tests.md` (add 2 slo_breach pressure test rows)

**Interfaces:**
- Consumes: `error_signals` array after the Phase 1 SLO breach check
- Produces: guidance for trace-based fallback, burn-rate widening, and war-room escalation

- [ ] **Step 1: Add slo_breach pressure test rows**

  Append to `incident-rca/reference/pressure-tests.md` table:

  ```markdown
  | SLO breach recorded in error_signals; `analyze_datadog_logs` returns 0 rows (log retention expired) | Run APM trace fallback; widen to 48h SLO burn rate; if still nothing → Phase 5 partial report with war-room escalation note |
  | SLO breach is the only signal; agent auto-proceeds to Phase 2 deploy correlation | **Wrong** — skip Phases 2–3 when slo_breach-only; jump to Phase 5 partial report |
  ```

- [ ] **Step 2: Add slo_breach-only fallback block to `incident-rca/workflow/phase-1.md`**

  Read the current file. The SLO breach block ends with:
  ```
  See [query-playbook.md](../reference/query-playbook.md#slo-breach) for mapping.
  ```

  After that closing line, append:

  ```markdown

  **SLO-breach-only fallback (when `slo_breach` is the only signal and logs are sparse or missing):**

  After the Phase 1 checkpoint, check: if `slo_breach` is the **only** entry in `error_signals`
  and `infra_signals` is empty:

  1. **Try APM traces as alternative** — run `search_datadog_spans` / `aggregate_spans` for
     `status:error` spans in the incident window:

     ```text
     aggregate_spans: query="service:<service> status:error", from=<from_time>, to=<to_time>
     telemetry: {"intent": "find error traces during SLO breach when logs are absent"}
     ```

     If error spans are found: add to `error_signals` with `signal_type: "trace_error"` and
     proceed to the Phase 1 checkpoint normally.

  2. **Widen the error-budget burn rate** — re-query the SLO with a 48h or 7d window:

     ```text
     search_datadog_slos: query="service:<service>", window=48h
     telemetry: {"intent": "check SLO burn trajectory to narrow failure onset time"}
     ```

     Record the burn rate (error budget consumed per hour). A sudden step-change in burn rate
     narrows the actual failure onset time. Add as `signal_type: "slo_burn_rate"` with
     `magnitude: "<rate>/h"` in `error_signals`.

  3. **Widen the log search window** — retry `analyze_datadog_logs` with ±2h then ±24h:

     ```text
     analyze_datadog_logs: filter="service:<service> status:error",
                           from=<from_time - 2h>, to=<to_time + 2h>
     telemetry: {"intent": "find any logs near the SLO breach window"}
     ```

     If logs appear outside `[from_time, to_time]` but not inside, note:
     *"Logs absent during incident window — possible log retention cutoff or sampling gap."*
     Add this note to `Gaps` in the Phase 5 report.

  4. **If still only `slo_breach`** after steps 1–3, transition to manual war-room posture:

     > **Investigation limited.** SLO breach is confirmed but no error logs, traces, or infra signals
     > were found in the analysis window. Proceeding with partial Phase 5 report.
     >
     > Required escalation steps:
     > 1. Confirm log retention policy — is the window within retention?
     > 2. Check Datadog log sampling rate for `<service>` in `<env>`.
     > 3. Try APM if not already connected (`search_datadog_spans`).
     > 4. Check whether the SLO error-budget consumption matches any known infra event (PagerDuty/OpsGenie).

     Skip Phases 2–3 (deploy correlation and Jira search will return noise without error signal
     anchoring). Jump directly to **Phase 5 partial report** with `primary_hypothesis: inconclusive`.
  ```

- [ ] **Step 3: Verify additions**

  ```bash
  grep -n "SLO-breach-only\|war-room\|slo_burn_rate\|trace_error" \
    /Users/luckyjain/Projects/ai-skills/incident-rca/workflow/phase-1.md \
    /Users/luckyjain/Projects/ai-skills/incident-rca/reference/pressure-tests.md
  ```
  Expected: hits in both files.

- [ ] **Step 4: Commit**

  ```bash
  git add \
    incident-rca/workflow/phase-1.md \
    incident-rca/reference/pressure-tests.md
  git commit -m "feat(rca): P1-3 — slo_breach-only investigation path with trace fallback and war-room escalation"
  ```

---

### Task 3: P2-3 — Runbook Lookup Deduplication

**Files:**
- Modify: `incident-rca/workflow/phase-1.md` (tag Phase 1 runbook result as `phase_1_preliminary`)
- Modify: `incident-rca/workflow/phase-4.md` (add dedup check before Phase 4 runbook search)
- Modify: `incident-rca/reference/pressure-tests.md` (add 1 runbook dedup pressure test row)

**Interfaces:**
- Produces: a single `runbook_match` entry in `evidence_links[]` — tagged `phase_1_preliminary` at Phase 1, promoted at Phase 4
- Consumes: `evidence_links[]` array across both phases

- [ ] **Step 1: Add runbook dedup pressure test row**

  Append to `incident-rca/reference/pressure-tests.md` table:

  ```markdown
  | Phase 1 runbook search finds `runbooks/oom-handling.md`; Phase 4 runs a second runbook search and finds the same file | **Wrong** — Phase 4 must detect the Phase 1 result and reuse it; only one `runbook_match` entry in evidence_links |
  ```

- [ ] **Step 2: Tag Phase 1 runbook results in `incident-rca/workflow/phase-1.md`**

  Read the runbook lookup section. It currently says:
  ```
  **If found** — record runbook URL/path in `evidence_links[]` with `signal_type: "runbook_match"`
  ```

  Change that sentence to:
  ```markdown
  **If found** — record runbook URL/path in `evidence_links[]` with `signal_type: "runbook_match"`,
  `tag: "phase_1_preliminary"`, and the source (user-provided / repo / Confluence). Example:

  ```json
  {
    "signal_type": "runbook_match",
    "tag": "phase_1_preliminary",
    "source": "repo",
    "url": "runbooks/oom-handling.md",
    "matched_on": "OOM hypothesis forming in Phase 1"
  }
  ```
  ```

  And change the "If not found" line to:
  ```markdown
  **If not found** — record `{"signal_type": "runbook_match", "tag": "phase_1_preliminary",
  "result": "none"}` in `evidence_links[]`. Phase 4 uses this as the signal to run its own search.
  ```

- [ ] **Step 3: Add dedup logic to Phase 4 runbook linkage section in `incident-rca/workflow/phase-4.md`**

  Read the Phase 4 file. The "## Runbook linkage (after hypothesis identified)" section begins:
  ```
  Once the primary hypothesis is ranked (or tentatively selected in manual scoring), check for a matching
  runbook **before** rendering the final report:
  ```

  Prepend a dedup check before this paragraph:

  ```markdown
  ## Runbook linkage (after hypothesis identified)

  **Dedup check first:** before running any Phase 4 runbook search, scan `evidence_links[]` for an
  entry with `signal_type: "runbook_match"` and `tag: "phase_1_preliminary"`:

  - **Found with a URL/path result** (Phase 1 found a runbook):
    - Promote the entry: remove `tag: "phase_1_preliminary"`, add `confirmed_at: "phase_4"`.
    - Reference the confirmed runbook in the Phase 5 report.
    - **Do NOT run a second runbook search** — the Phase 1 result is authoritative.

  - **Found with `"result": "none"`** (Phase 1 found nothing):
    - Run the Phase 4 runbook search below as the definitive lookup.
    - Replace the `{result: "none"}` entry with the Phase 4 result (or keep `none` if still not found).

  - **Not found in evidence_links** (Phase 1 runbook step was skipped, e.g. no hypothesis forming):
    - Run the Phase 4 runbook search below.

  Once the primary hypothesis is ranked (or tentatively selected in manual scoring), check for a matching
  runbook **before** rendering the final report:
  ```

  Note: the rest of the existing section (the search steps) follows unchanged.

- [ ] **Step 4: Verify additions**

  ```bash
  grep -n "phase_1_preliminary\|Dedup check\|confirmed_at" \
    /Users/luckyjain/Projects/ai-skills/incident-rca/workflow/phase-1.md \
    /Users/luckyjain/Projects/ai-skills/incident-rca/workflow/phase-4.md \
    /Users/luckyjain/Projects/ai-skills/incident-rca/reference/pressure-tests.md
  ```
  Expected: hits in all three files.

- [ ] **Step 5: Commit**

  ```bash
  git add \
    incident-rca/workflow/phase-1.md \
    incident-rca/workflow/phase-4.md \
    incident-rca/reference/pressure-tests.md
  git commit -m "feat(rca): P2-3 — runbook lookup deduplication across Phase 1 and Phase 4"
  ```

---

### Task 4: P3-1 — PagerDuty/OpsGenie Incident Lookup

**Files:**
- Modify: `incident-rca/workflow/phase-0.md` (add PD/OG detection and quick-check)
- Modify: `incident-rca/reference/query-playbook.md` (add PD/OG query recipes)
- Modify: `incident-rca/reference/pressure-tests.md` (add 1 PD/OG pressure test row)

**Interfaces:**
- Produces: `mcp_profile.pagerduty` and/or `mcp_profile.opsgenie` flags; `pd_alerts[]` array seeded from Phase 0 quick-check
- Consumes: MCP tool descriptors checked in Phase 0

- [ ] **Step 1: Add PagerDuty/OpsGenie pressure test row**

  Append to `incident-rca/reference/pressure-tests.md` table:

  ```markdown
  | PagerDuty MCP connected; incident `triggered_at = 14:22`; Jira ticket `created_at = 14:38`; user provided `from_time = 14:38` | Use PD `triggered_at` to refine `from_time` to `14:22`; apply Phase 0b backstroke to `14:07` |
  ```

- [ ] **Step 2: Add PagerDuty/OpsGenie detection to `incident-rca/workflow/phase-0.md`**

  Read the current file. After the `## Multi-site Datadog` section (the last section), append:

  ```markdown

  ## PagerDuty / OpsGenie detection (optional)

  After detecting Datadog and KubeSense, also check for alerting/on-call MCP tools:

  **PagerDuty:** look for tools named `pd_get_incident`, `pd_list_incidents`, `pagerduty_list_incidents`,
  or similar PD-prefixed tools in connected MCPs.

  **OpsGenie:** look for tools named `opsgenie_list_alerts`, `og_list_incidents`, or similar.

  Record in the MCP profile announcement (add columns when present):

  > **RCA MCP profile:** Datadog ✅ | KubeSense ✅ | PagerDuty ✅ | OpsGenie ❌ | ...

  **Phase 0 quick-check (when PD or OpsGenie available):**

  Run immediately after the Datadog incidents quick-check:

  *PagerDuty:*
  ```text
  pd_list_incidents: service_ids=[<service>], since=<from_time>, until=<to_time>,
                     statuses=["triggered","acknowledged","resolved"]
  ```

  *OpsGenie:*
  ```text
  opsgenie_list_alerts: query="tag:<service> OR alias:<service>",
                        createdAt>=<from_time>, createdAt<=<to_time>
  ```

  For each matched alert/incident, record in `pd_alerts[]`:

  ```json
  {
    "source": "pagerduty",
    "alert_id": "<id>",
    "title": "<summary>",
    "severity": "P1",
    "triggered_at": "<iso_utc>",
    "acknowledged_at": "<iso_utc_or_null>",
    "resolved_at": "<iso_utc_or_null>",
    "link": "<web_url>"
  }
  ```

  **Window refinement:** if `pd_alerts[].triggered_at` is earlier than the current `from_time`,
  use it to pull `from_time` backward — PD alert timestamps are set by the monitoring system and
  are more accurate than ticket `created_at`. Then apply Phase 0b backstroke on top.

  If no PD/OG tools are available, note `| PagerDuty ❌ | OpsGenie ❌ |` in the profile and
  continue — these tools are optional.
  ```

- [ ] **Step 3: Add PD/OG query recipes to `incident-rca/reference/query-playbook.md`**

  Read the current file. After the `## Known issues cross-check (optional)` section, append a new section:

  ```markdown

  ---

  ## PagerDuty / OpsGenie

  ### PagerDuty — list incidents in window

  **Tool:** `pd_list_incidents` (or `pagerduty_list_incidents` — name depends on MCP server)

  ```json
  {
    "statuses": ["triggered", "acknowledged", "resolved"],
    "since": "<from_time>",
    "until": "<to_time>",
    "service_ids": ["<pd_service_id>"]
  }
  ```

  To find `pd_service_id`: use `pd_list_services` filtered by service name if available, or ask the user.

  **Map to `pd_alerts[]`:**
  ```json
  {
    "source": "pagerduty",
    "alert_id": "<incident.id>",
    "title": "<incident.title>",
    "severity": "<incident.urgency or priority.name>",
    "triggered_at": "<incident.created_at>",
    "acknowledged_at": "<incident.acknowledged_at or null>",
    "resolved_at": "<incident.resolved_at or null>",
    "link": "<incident.html_url>"
  }
  ```

  Use `triggered_at` as a more accurate `from_time` anchor than Jira `created_at` when it precedes
  the current window start.

  ### OpsGenie — list alerts in window

  **Tool:** `opsgenie_list_alerts` (or `og_list_incidents`)

  ```json
  {
    "query": "tag:<service> OR alias:<service>",
    "createdAt": ">= <from_time>",
    "limit": 20,
    "sort": "createdAt",
    "order": "asc"
  }
  ```

  **Map to `pd_alerts[]`** (same schema, `"source": "opsgenie"`):
  - `triggered_at` = `alert.createdAt`
  - `acknowledged_at` = `alert.acknowledgedAt`
  - `resolved_at` = `alert.closedAt`
  - `severity` = `alert.priority` (P1–P5 scale)

  ### Window refinement from PD/OpsGenie

  If the earliest `triggered_at` from `pd_alerts[]` is before `from_time`:
  - Set `from_time = min(pd_alerts[].triggered_at)` (more accurate onset)
  - Re-apply Phase 0b backstroke: `analysis_from_time = from_time − 15m`
  - Note in Phase 5 report: *"Window refined from PagerDuty/OpsGenie alert timeline."*
  ```

- [ ] **Step 4: Verify additions**

  ```bash
  grep -n "PagerDuty\|OpsGenie\|pd_alerts\|pagerduty\|opsgenie" \
    /Users/luckyjain/Projects/ai-skills/incident-rca/workflow/phase-0.md \
    /Users/luckyjain/Projects/ai-skills/incident-rca/reference/query-playbook.md \
    /Users/luckyjain/Projects/ai-skills/incident-rca/reference/pressure-tests.md
  ```
  Expected: hits in all three files.

- [ ] **Step 5: Commit**

  ```bash
  git add \
    incident-rca/workflow/phase-0.md \
    incident-rca/reference/query-playbook.md \
    incident-rca/reference/pressure-tests.md
  git commit -m "feat(rca): P3-1 — PagerDuty and OpsGenie incident lookup with window refinement"
  ```
