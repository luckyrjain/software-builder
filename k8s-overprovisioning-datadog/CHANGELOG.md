# k8s-overprovisioning-datadog — Changelog

## v3.5 — Route-aware workflow contract + safe rendered-output boundary (2026-08-10)

- New `workflow-contract.yaml`: `intent_route` (this skill's own `orchestrator.md`-produced routing
  field, five values — `full`, `cost_savings`, `replicas_too_high`, `throttle_oom`,
  `namespace_ranking`) selects a fixed, exhaustively-checkable phase-file list per route, the same
  route-aware contract pattern already applied to incident-rca/pr-review/prd-architect. Selection
  happens at `route_selection.after_phase: orchestrator` — before any evidence collection starts,
  cleaner than every prior mid-run-produced selector field in this rollout since it needs no phase
  execution beyond the routing table itself to resolve.
- Formalized `intent_route`'s five canonical string values directly in `workflow/orchestrator.md`'s
  own Intent routing table (previously only `namespace_ranking` had a literal identifier; the other
  four were prose-only column labels) — the contract references these IDs, so they needed to exist
  as real identifiers, not just table row descriptions.
- Fixed a genuine ambiguity in that same table found while authoring the contract: the "Cost savings"
  row's `…` ellipsis didn't state which dimension modules (cpu/memory/replica/workload) actually run,
  unlike the "Replicas too high?" and "Throttle / OOM" rows, which name theirs explicitly. Resolved
  in favor of cpu + memory + workload (no replica) — `cost-analysis.md`'s own skip condition ("No
  ALLOW/DEFER dimension with savings potential") and `cost-estimation.md`'s savings formulas both
  require `DEC_CPU_REQUEST`/`DEC_MEMORY_REQUEST` decisions and cpu-analysis.md's/memory-analysis.md's
  percentile/peak-proxy output to even be computable, and every dimension module's own gating already
  cites workload's `OBS_KAFKA_LAG_*` output (`reason.md`'s own `DEC_CPU_REQUEST` example), so workload
  always loads alongside any of cpu/memory/replica.
- Converted all 21 `workflow/*.md` files' `produces`/`consumes` frontmatter from flat lists to the
  typed `{field: type}` / `{required, optional, conditional}` shape the contract validator requires
  — including two previously-implicit fields made explicit: `evidence.md` now formally produces
  `evidence_ids` (the `EVID_*`-only id list every dimension module already consumed by that name) and
  `confidence.md` now formally produces `computed_confidence` (the combined output `build-graph.md`
  already consumed by that name) — both field names were already load-bearing across multiple files'
  prose and frontmatter, just never actually produced by anyone until now. `confidence.md` also gained
  an explicit route-phase slot (after `validate`/`cost`, before `build-graph`) in the four routes that
  need it — it wasn't previously a top-level phase in any route despite `build-graph.md` requiring its
  output. `reason.md` and `build-graph.md` get `namespace_ranking`-specific `consumes.conditional`
  overrides, since that route's abbreviated `resolve → reason → graph → render` chain never produces
  `observation_registry`/`evidence_registry`/`validated_decisions`/etc. — the same conditional-input
  pattern incident-rca established for `jira_anchored`.
- New "Safe rendered-output boundary" section in `render/markdown.md` (linked from `SKILL.md`'s
  Framework line, within the 150-line `SKILL.md` budget — tighter than the rollout's usual 180):
  `delivery_pointer.path` (a Git-manifest-derived path already rendered in a code span — needs
  explicit backtick-strip before wrap) and string-valued `OBS_*`/`EVID_*` observations (Kafka
  consumer-group names, KEDA scaler types, HPA names) get the short-identifier treatment; Human Report
  narrative prose (`WhyThisMatters`, `Explanation`, RisksSummary/RecommendationsSummary/Conclusion) gets
  structural escaping only, never wrapped; fixed enums (`final_decision`, confidence bands,
  `STOP_REASON` IDs, `DEC_*`/`REC_*`/`OBS_*`/`EVID_*` ID strings) need no escaping.
- `reference/pressure-tests.md` gained a new row: a Jira ticket instructing the agent to skip the
  throttle gate — distinct from the pre-existing "User says 'recommend aggressive CPU cuts regardless
  of p95'" row, which covers the *caller* directly asking for a bypass; this covers the untrusted
  *third-party content* class (Jira/monitor notes/dashboard text) SKILL.md's own guardrail names.
- Two new golden evals: `injection-throttle-gate-not-bypassed.yaml` (Jira-sourced instruction can't
  bypass the throttle gate or INV-12's delivery-pointer requirement) and
  `injection-inert-delivery-pointer.yaml` (a backtick-embedding manifest path and a
  pipe/newline/spoofed-heading-embedding consumer-group name both render inert).
- `make lint-k8s-skill` gained `route-aware workflow contract` and `safe rendered-output boundary`
  steps.
- Bumped every touched `workflow/*.md` file's `workflow_version` to 3.5 (per this skill's own
  convention that per-file `workflow_version` matches the latest CHANGELOG entry) and `SKILL.md`'s own
  version line to v3.5.

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
