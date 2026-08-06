---
workflow_version: 1.2
phase: 5
produces:
  - rca_report
consumes:
  - ranked_hypotheses
  - evidence_json
  - cli_available
  - causal_graph
---

# Phase 5 — Render the final report

**Read this file** at the start of Phase 5, after Phase 4. Also load
[reference/gold-rca-excerpt.md](../reference/gold-rca-excerpt.md) (format few-shot),
[reference/root-cause-depth.md](../reference/root-cause-depth.md),
[reference/evidence-quality.md](../reference/evidence-quality.md), and
[reference/evidence-coverage.md](../reference/evidence-coverage.md) before rendering.

**Exit:** [phase-exit-criteria.md](../reference/phase-exit-criteria.md) §Phase 5.

## Pre-render attestation (required)

Print this checklist before authoring the RCA report body. Every box must be checked or annotated N/A:

```markdown
### Pre-render attestation
- [ ] `causal_graph` validated (`validate_causal_graph.py` pass) or Gaps note if validation impossible
- [ ] Confidence caps applied; no decimal scores in executive narrative
- [ ] Headline metrics stated once in executive summary (anti-repetition)
- [ ] No best-guess primary when all hypotheses ≤ MEDIUM after caps
- [ ] Mandatory sections per report-template order (or Partial RCA header if stopped early)
- [ ] Post-RCA actions table queued for chat only — not inside report body
```

If causal-graph validation failed critically → return to Phase 4; do not render polished RCA.

Merge logic (no duplicate sections):

1. **Causal-graph gate** — confirm the Phase 4 causal-graph artifact validated cleanly
   ([causal-graph-schema.md](../reference/causal-graph-schema.md)). Unvalidated or failing → return to
   Phase 4; render only with a Gaps note when validation was impossible (no Python/PyYAML).
   The report's **Causal graph** section must mirror the validated artifact's nodes and edges.
2. **CLI output is canonical when present** — start from `rca_report.md`, then **enrich in place**
   (MCP deep links, sample log lines, MR/changeset summaries). Do not regenerate sections the CLI
   already produced.
3. **No CLI** — build the report from [report-template.md](../report-template.md) + the manual scoring.
4. **CLI ran but `rca_result.json` empty/unreadable** — same as no CLI: manual scoring + **Gaps** note
   explaining CLI failure; do not present CLI-ranked hypotheses.
5. Validate the result against [report-template.md](../report-template.md) — every required section
   present, deep links on every evidence row.
6. Present in chat:
   - **TL;DR** (3 bullets: window, primary hypothesis + confidence, top action)
   - Optional **2-min read** (executive summary + conclusion)
   - Link to full report file
   Full template: [report-template.md](../report-template.md) §Executive Summary.

## Report body hygiene

The rendered RCA report (file or chat paste of full sections) MUST NOT include agent mode instructions
(`Type ACT`, `PLAN/ACT`, MCP setup steps, posting confirmations). Those belong in **chat only** after
the report — see [post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md).

Required narrative sections from [report-template.md](../report-template.md) (mandatory order):

- **Incident class** in scope (from Phase 4)
- **Customer impact**, **Detection analysis**, **Unified timeline** (Evidence quality column)
- **Causal chain**, **Causal graph** (acyclic)
- **Initiating event / trigger / root cause / contributing factors**
- **Ranked hypotheses** — supporting and contradicting evidence blocks per hypothesis
- **Evidence matrix** + **Evidence coverage** (completeness %, confidence ceiling, blocking gaps)
- **Recovery analysis** — mitigation, effect, verification, residual risk, MTTR
- **Corrective actions** and **Preventive actions** (separate sections)
- **Five whys**, **Known vs unknown**, **Resolution**, **Lessons learned**
- **Confidence** + **Risks**
- **Conclusion** — *No defensible root cause* when all hypotheses ≤ MEDIUM after caps (no best-guess primary)
- **Anti-repetition** — headline metrics once in executive summary

**`infra_capacity`, `query_governance`, or `dependency_failure` ≥ MEDIUM** — also include when applicable: mechanism narrative,
blast radius tree + dependency explanation sentence + upstream top-3 callers (first 10m), key metrics snapshot, **query execution profile**
(OpenSearch/ES — Phase 1 APM), **executed queries investigated**
(run [query-investigation.md](../reference/query-investigation.md) — Phase 1 for ES, Phase 3 for other engines),
trigger workload analysis table.

**Process failure:** when trigger Unknown and mandatory KubeSense log fallback was skipped while KubeSense ✅,
cap confidence at **MEDIUM** and flag in **Gaps** with `mcp_process_failure`. When KubeSense returned backend
fetch errors, use `observability_backend_error` in Gaps — distinct from skip.

## Post-RCA actions (required table)

After rendering the report, always output the **Post-RCA actions** table from
[report-template.md](../report-template.md#post-rca-actions):

| Action | Target | Owner | Priority | ETA | Notes |
|--------|--------|-------|----------|-----|-------|
| Follow-up Jira | linked INC or new ticket | team | P0/P1 | date | link RCA |
| Update runbook | path or wiki page | team | P1 | sprint | detection + rollback |
| PR review | causative MR | reviewer | P0 | date | when deploy_regression |

Use `—` for N/A rows. Read-only — offer text; never write Jira without explicit user consent.

## K8s handoff block

When **`infra_capacity`** is confirmed (primary or strong alternate), append the paste-ready
**Handoff → k8s-overprovisioning-datadog** block from
[report-template.md](../report-template.md#k8s-skill-handoff-infra-capacity-confirmed) in chat.
Populate evidence bundle fields from Phase 3 observability signals.

**k8s skill v3.1 expected context** — include these fields in the handoff block:

| Field | From RCA |
|-------|---------|
| Service name | `service` from inputs |
| Incident window | `from_time` / `to_time` — skill uses this for pre-flight staleness check |
| Confirmed hypothesis | e.g. `infra_capacity` — helps the skill focus on Throttle/OOM intent |
| Evidence summary | Top OOM/throttle signals from `infra_signals[]` — cite magnitudes for context |

The k8s skill runs its own graph-first analysis (DISCOVER_SOURCES → RESOLVE → COLLECT → BUILD_GRAPH →
RENDER). RCA evidence is *context*, not authoritative input — the skill independently discovers
Kubernetes MCP and Datadog capabilities, then re-queries the selected sources.

## Confluence export (optional)

If the user requests wiki/Confluence output, add the Confluence-friendly section per
[report-template.md](../report-template.md#confluence-wiki-export-optional) — no Confluence MCP
required unless available. **Strip `assessment_metadata`** from wiki body.

## Partial report path (user says stop)

When the user requests *"stop here"*, *"give me what you have"*, or a phase checkpoint ends with stop:

1. Render using [report-template.md](../report-template.md) but mark header: **Partial RCA — investigation stopped early**.
2. Include completed phases only — label skipped phases in **Gaps**.
3. Primary hypothesis: best available with confidence capped at **MEDIUM** if Phase 4 did not complete.
4. Required sections: Incident scope, Evidence collected (what exists), Hypothesis (if ranked), Gaps,
   Next steps (what Phase N would have done).
5. Do **not** present partial output as a complete RCA — state explicitly what was not investigated.

**Verdict rules:**

- State the primary hypothesis with confidence (`HIGH` / `MEDIUM` / `LOW` / `UNKNOWN`) using band +
  Reason / Remaining uncertainty — not decimal scores in the narrative body.
- Include **Risks** (Overall sentence first) and **Conclusion** before optional exports.
- List ruled-out hypotheses (score < 50% of primary).
- Never claim a root cause as fact when confidence is `LOW` or `UNKNOWN`.
- Emit **`assessment_metadata` YAML footer** — v2 platform analytics blocks (`history`, `precision`,
  `investigation_quality`). Normative spec: [reference/assessment-metadata.md](../reference/assessment-metadata.md);
  shared schema: [review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md) §8.1.

## `assessment_metadata` footer (platform analytics)

Append a fenced ` ```yaml ` block under **Appendix — machine metadata** (after **Conclusion**). Include
in the report file when written to disk and in chat when the full report is delivered. **Do not** paste
into Confluence/wiki export or Jira narrative body.

| Block | When to emit |
|-------|----------------|
| **Core** | Every complete RCA — `service`, `incident_window`, `primary_hypothesis`, `confidence` |
| **`history`** | Re-run on same incident/service when prior `assessment_metadata` parseable |
| **`precision`** | Every RCA where Phase 4 ranked hypotheses |
| **`investigation_quality`** | When computable; omit on partial/stopped reports |

**`history` population:** when user re-runs RCA on same service/incident, parse prior report or posted
note for latest `assessment_metadata`; set `investigation_iteration` from footer count + 1.

**Precision linkage:** mirror Phase 4 ranked hypothesis count and evidence bundle signal stats into
`precision`.

Field definitions: [reference/assessment-metadata.md](../reference/assessment-metadata.md).
