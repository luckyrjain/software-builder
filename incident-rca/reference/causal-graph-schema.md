# Causal graph artifact (schema_version 1)

Machine-checkable form of the report's **Causal graph** section. Phase 4 writes
`rca_causal_graph.yaml` next to the evidence bundle; Phase 5 must not render until
[validate_causal_graph.py](../scripts/validate_causal_graph.py) passes. Prose rules it enforces live in
[evidence-quality.md](evidence-quality.md) (§Causal graph rules, §Hypothesis score algorithm,
§Confidence caps, §Insufficient evidence).

## Top-level fields (all required)

| Field | Type | Meaning |
|-------|------|---------|
| `schema_version` | int | `1` |
| `service` | string | Investigated service (matches evidence bundle) |
| `window` | object | `from_time` / `to_time` (matches evidence bundle) |
| `trigger_status` | enum | `identified` \| `unknown` |
| `observability_sources_responded` | int | Count of independent observability sources that returned data (Datadog, KubeSense, …) |
| `nodes` | list | Causal graph nodes |
| `edges` | list | Directed cause → effect edges |
| `hypotheses` | list | Ranked hypotheses with scoring arithmetic |
| `conclusion` | object | `primary` (hypothesis id or `"none"`) + `statement` |

## Nodes

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | Unique within the graph |
| `kind` | enum | `event` \| `trigger` \| `root_cause` \| `contributing` \| `systemic` |
| `label` | string | One-line description; customer-visible symptoms are `event` nodes at the bottom of the chain |

## Edges

Directed **cause → effect**. Feedback loops stay in report prose — the graph must be acyclic.

| Field | Type | Meaning |
|-------|------|---------|
| `from` / `to` | string | Node ids |
| `evidence` | list of string | ≥1 reference into the evidence bundle: `<list_field>[<index>]`, e.g. `error_signals[0]`, `deploy_events[0]`. Valid list fields: `error_signals`, `deploy_events`, `jira_issues`, `infra_signals`, `known_issue_matches`, `evidence_links`, `query_signals`, `recurrence_history` |

## Hypotheses

Mirror the Ranked hypotheses table; the validator recomputes the arithmetic from
[evidence-quality.md](evidence-quality.md) §Hypothesis score algorithm.

| Field | Type | Meaning |
|-------|------|---------|
| `id` | string | `H1`, `H2`, … |
| `type` | string | Hypothesis type from [evidence-schema.md](evidence-schema.md) |
| `base` | number | Sum of matched signal weights ([manual-scoring.md](manual-scoring.md)) |
| `quality_bonus` | number | ≤ 15 |
| `source_bonus` | number | `0` or `10` |
| `counter_penalty` | number | `10 ×` unresolved contradicting signals (≥ 0) |
| `gap_penalty` | number | `0` or `15` |
| `adjusted` | number | `max(0, base + quality_bonus + source_bonus − counter_penalty − gap_penalty)` |
| `display_score` | int | `round(adjusted / Σ adjusted × 100)`, half-up; `0` when Σ = 0 |
| `band` | enum | `HIGH` \| `MEDIUM` \| `LOW` \| `UNKNOWN` — after confidence caps |
| `unresolved_contradictions` | int | Count feeding `counter_penalty` and the MEDIUM cap |
| `supporting_quality` | list | Evidence-quality labels of supporting signals (`Observed` / `Correlated` / `Inferred` / `Assumed`) |
| `ruled_out` | bool | True iff `adjusted < 0.5 × max(adjusted)` |

## Invariants (validator)

| ID | Check |
|----|-------|
| CG-01 | Graph is acyclic |
| CG-02 | Node ids unique; kinds valid; edge endpoints exist |
| CG-03 | Every edge has ≥1 evidence ref; every ref resolves in the evidence bundle |
| CG-04 | `adjusted` matches the formula; `quality_bonus` ≤ 15 |
| CG-05 | `display_score` matches normalization (half-up rounding) |
| CG-06 | Band respects caps: sources < 2 → ≤ MEDIUM; contradictions > 0 → ≤ MEDIUM; all-Assumed support → ≤ LOW; `trigger_status: unknown` → ≤ MEDIUM; band never exceeds the score-implied band (75+ HIGH, 50–74 MEDIUM, 25–49 LOW, else UNKNOWN) |
| CG-07 | `conclusion.primary` is `"none"` unless some hypothesis band is HIGH; when set it names an existing HIGH hypothesis (see §Insufficient evidence — no best-guess primary) |
| CG-08 | `ruled_out` consistent with the 0.5 × primary rule |

Run: `python3 incident-rca/scripts/validate_causal_graph.py <graph.yaml> <evidence.json>`
