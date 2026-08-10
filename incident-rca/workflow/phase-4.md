---
workflow_version: 1.3
phase: "4"
produces: {evidence_json: object, ranked_hypotheses: list, incident_class: string, evidence_coverage: object, causal_graph: object}
consumes:
  required: {error_signals: list, infra_signals: list, deploy_events: list, jira_issues: list, known_issue_matches: list, recurrence_history: list, cli_available: boolean}
  optional: {}
  conditional: {}
---

# Phase 4 — Correlate & rank hypotheses

**Read this file** at the start of Phase 4, after Phases 1–3.

Also load **[reference/evidence-schema.md](../reference/evidence-schema.md)**,
**[reference/evidence-quality.md](../reference/evidence-quality.md)**,
**[reference/evidence-coverage.md](../reference/evidence-coverage.md)**, and
**[reference/precedence.md](../reference/precedence.md)**.

**Do not advance to Phase 5** until [phase-exit-criteria.md](../reference/phase-exit-criteria.md) §Phase 4 passes.

## Conflicting evidence (before ranking)

If traces, logs, and metrics disagree on timing or attribution:

1. Apply [evidence-quality.md](../reference/evidence-quality.md) hierarchy — resolve or document conflict.
2. **STOP** ranking until contradiction is explained in **Gaps** or one signal is excluded with reason.
3. Unresolved conflict → confidence cap **MEDIUM** maximum.

**Clock skew, not a real conflict:** when two sources disagree on a shared event's timestamp by **under
2 minutes** (e.g. Datadog vs KubeSense for the same event), presume ordinary clock/ingestion skew, not
a genuine conflict — do not STOP or cap confidence for this alone. Escalate to a real conflict only if
the skew is large enough to change which event is causally first.

## Hypothesis deduplication (before ranking)

Review candidate hypotheses **before** writing evidence JSON:

1. If H2/H3 describe **steps in the same chain** as H1 (e.g. slow query → saturation → errors), **merge**
   into one causal graph — do not rank them as independent competitors.
2. Keep **separate** hypotheses only for **independent competing explanations** (deploy vs external vs unrelated infra).
3. Record merges in **Gaps**: *"Merged query_governance + infra_capacity chain steps; single primary with multi-layer graph."*
4. Set **`incident_class`** from primary hypothesis per [evidence-quality.md](../reference/evidence-quality.md) §Incident class.
5. Compute **evidence coverage** dashboard per [evidence-coverage.md](../reference/evidence-coverage.md) — overall %, confidence ceiling, blocking gaps.
6. If **no hypothesis exceeds MEDIUM** after caps → primary = `inconclusive`; do not pick highest score.

## Minimum evidence gate (run first)

Before writing evidence JSON or invoking the correlator CLI, check signal counts from Phases 1–3:

```
IF error_signals is empty AND infra_signals is empty
  → Do NOT run hypothesis ranking.
  → Emit a blocked/partial report per Phase 5 with primary hypothesis inconclusive / UNKNOWN.
  → State explicitly: "No observability data found for this window — investigation blocked."
  → List attempted queries in Gaps; skip CLI invocation.
```

Deploy events, Jira tickets, or known-issue matches alone are **not** sufficient to rank hypotheses —
at least one `error_signals` or `infra_signals` entry is required.

**Truncated-window check:** if the earliest `error_signals`/`infra_signals` timestamp falls within a
few minutes of the queried window's `from_time`, treat the trigger as possibly cut off — the true
onset may be before the window. Re-query error/infra signals for an additional **±30 min before**
`from_time` (same expansion the deploy-correlation lookup already uses per
[inputs.md](inputs.md)) and check for earlier evidence **before** ranking, rather than ranking against
a truncated causal chain. Note in **Gaps** when backward widening was attempted and found nothing
further.

**When the correlator CLI ranks this run's hypotheses:** read the pinned commit SHA from
`skills-lock.json` → `optionalExternal.incident-rca-correlator-cli.commitSha` and record it as
`assessment_metadata.precision.correlator_sha` at Phase 5 closeout ([assessment-metadata.md](../reference/assessment-metadata.md)).
Leave it `null` when [manual-scoring.md](../reference/manual-scoring.md) was used instead.

**Sample-message dedup:** re-apply the Phase 1 rule — deduplicate `error_signals[].sample_messages` across all sources (normalise whitespace and lowercase) before writing evidence JSON.

**Process failure check:** before ranking, verify mandatory KubeSense log-coverage attempts when triggered.
If trigger Unknown and KubeSense skipped while ✅, cap report confidence at **MEDIUM** and add Gaps note.

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

1. **User-provided path** — if the user named a runbook URL or repo path, fetch/link it when readable.
2. **Repo search** — when workspace access exists, check (in order):
   - `runbooks/`, `docs/runbooks/`, `playbooks/`
   - `KNOWN_ISSUES.md`, `docs/KNOWN_ISSUES.md`
   - Match on hypothesis type + service + symptom keywords.
3. **Record in report** — add a **Runbook** section when found:
   - Runbook title + link/path
   - Which steps apply to this incident
   - Gaps when no runbook exists: *"No runbook found for `<hypothesis>` — consider documenting."*

Do not auto-execute runbook steps (read-only RCA).

### If the CLI is present (`cli_available` from Phase 0)

Write the evidence bundle JSON (schema in evidence-schema.md), then run:

> Use the session scratchpad path when available; otherwise `$TMPDIR`. Do not hardcode `/tmp/`.

```bash
scratchpad="${CURSOR_SCRATCHPAD:-${TMPDIR:-/tmp}}"
incident-rca run \
  --input "$scratchpad/rca_evidence.json" \
  --result-output "$scratchpad/rca_result.json" \
  --report-output "$scratchpad/rca_report.md"
```

Read `rca_result.json` for ranked hypotheses; `rca_report.md` is the base report.

**CLI output fallback:** if `rca_result.json` is empty, missing, or not valid JSON after the run, treat
the CLI as **absent** — rank with [reference/manual-scoring.md](../reference/manual-scoring.md) and add a
**Gaps** note explaining the CLI failure (exit code, parse error, or empty output).

### If the CLI is absent (manual fallback)

Do **not** claim CLI-ranked hypotheses. Score by hand using
[reference/manual-scoring.md](../reference/manual-scoring.md) and the display-score formula in
[reference/evidence-quality.md](../reference/evidence-quality.md), then deliver a **partial report**
whose **Gaps** section explicitly states *"hypotheses ranked manually — correlator CLI not installed."*
Apply confidence caps from evidence-quality.md. Every ranked hypothesis needs supporting and contradicting
evidence blocks in Phase 5. Emit evidence coverage for Phase 5 render.

## Causal graph artifact (required)

After ranking (CLI or manual), write the machine-checkable causal graph per
[causal-graph-schema.md](../reference/causal-graph-schema.md) and validate it:

```bash
scratchpad="${CURSOR_SCRATCHPAD:-${TMPDIR:-/tmp}}"
python3 incident-rca/scripts/validate_causal_graph.py \
  "$scratchpad/rca_causal_graph.yaml" \
  "$scratchpad/rca_evidence.json"
```

Fix every reported `CG-*` violation before Phase 5 — the validator enforces acyclicity, evidence-backed
edges, score arithmetic, confidence caps, and the no-best-guess-primary rule
([evidence-quality.md](../reference/evidence-quality.md)). If Python or PyYAML is unavailable, state that
in **Gaps** ("causal graph not machine-validated") and verify the CG checks by hand against
[causal-graph-schema.md](../reference/causal-graph-schema.md) §Invariants.

## Phase 4 exit

Announce: hypotheses ranked, incident class, overall coverage %, confidence ceiling, causal-graph
validator pass (or Gaps note if validation skipped), blocking gaps.
See [phase-exit-criteria.md](../reference/phase-exit-criteria.md) §Phase 4.
