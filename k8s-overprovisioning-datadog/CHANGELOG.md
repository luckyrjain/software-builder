# k8s-overprovisioning-datadog — Changelog

## v3.4 — Kubernetes MCP-first capability routing (2026-08-06)

- Prefer Kubernetes MCP for live workload/configuration state and equivalent metrics.
- Fall back to Datadog per missing capability; keep Datadog for unique history, monitors, incidents,
  APM, change events, and optional cost.
- Continue when either source is absent but the other supplies sufficient evidence; block with
  `insufficient_metrics` only when combined evidence cannot support sizing.
- Preserve dual-source observations and trigger `conflicting_signals` on material disagreement.

Prompt and workflow changes are versioned here. Per-file `workflow_version` in workflow frontmatter
should match the latest entry when that file is edited.

## v3.3 — 2026-07-31

Version-drift catch-up (cross-skill gap audit):

- **report-template.md** — header said "Graph-first (v3.1)"; corrected to v3.3 (this release)
- **workflow/collect-metrics.md** — `workflow_version` stale at 3.0 despite the v3.2 ingest-phase
  injection reminder edit; bumped to 3.3
- **workflow/anomalies.md**, **cost-analysis.md**, **cpu-analysis.md**, **memory-analysis.md**,
  **replica-analysis.md**, **resolve-service.md**, **trends.md**, **workload-analysis.md** — all 8
  dimension modules were frozen at `workflow_version: 1.0` despite real content added across several
  unlogged commits since the v3.0 baseline (limit-ratio tables, StatefulSet/KEDA sections). No prior
  CHANGELOG entry named these files, so their edit history can't be reconstructed to intermediate
  versions — bumped to 3.3 (current) rather than leave them permanently untracked
- **reference/report-schema.md**, **workflow/checklists.md**, **README.md** (×2), **workflow/report.md**,
  **templates/appendix.md**, **reference/smoke-test.md** (×2) — cited "INV-01–INV-12", dropping INV-13
  (a real, critical, blocking invariant) from the stated gate range
- **reference/report-schema.md** — "Human Report (fixed order)" table omitted `PostChangeVerification`
  entirely despite 3 other files treating it as mandatory
- **templates/human-report.md** — deleted a duplicate confidence-band threshold table that contradicted
  `reference/confidence-formula.md`'s normative thresholds
- **reference/decision-graph.scale-up.example.yaml** — stripped a bogus "capped 0.8" arithmetic
  annotation; no cap mechanism for `assessment_confidence` exists

## v3.2 — 2026-07-07

Portfolio hardening (shared framework alignment):

- **SKILL.md** — untrusted Datadog/Jira guard; `skill-routing` + `prompt-injection` links
- **workflow/collect-metrics.md** — ingest-phase injection reminder

## v3.1 — 2026-07-07

Prompt-engineering hardening (phase alignment, render compliance, precedence):

- **reference/phase-index.md** — full pipeline: NORMALIZE, VALIDATE, optional COST
- **reference/gold-human-report-excerpt.md** — compact few-shot for RENDER
- **workflow/render.md** — pre-render attestation checklist
- **reference/precedence.md** — confidence/threshold/gate conflict resolution
- **report-template.md** — index header points to gold excerpt; extended examples for maintainers
- **reference/pressure-tests.md** — model-family note; happy/edge/adversarial scenarios
- **SKILL.md** — P0 guardrails (never invent metrics; invariant failure → no polished report)

## v3.0 — 2026-03-01 (baseline)

- Graph-first architecture: `decision_graph` primary artifact; `schema_version: 3`
- Pipeline: COLLECT → NORMALIZE → REASON → VALIDATE → BUILD_GRAPH → VALIDATE_INVARIANTS → RENDER
- Human Report + Technical Appendix split; INV-01–INV-13; `validate_decision_graph.py`
- Stop-reason registry; VPA+HPA conflict; KEDA external-metric path; confidence formula (INV-07/11)
