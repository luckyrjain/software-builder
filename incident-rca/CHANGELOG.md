# Changelog — incident-rca

## 2026-07-31 — team adoption readiness

- **SETUP.md** — added copy-pasteable MCP JSON for GitLab, Jenkins, and Jira (previously prose-only for
  all three; Jenkins config didn't exist anywhere in the repo); added a "Minimum viable setup" callout
  (Datadog + GitLab alone gets a MEDIUM-confidence RCA — the rest is additive, not required for a first run)
- **reference/org-profiles.md** — clarified the mpokket/KubeSense-primary section is this org's real,
  specific guardrail, not an illustrative example a different org's setup should inherit
- **README.md** — marked `neo-disbursement-service` as a fictional placeholder used consistently across
  docs; added a rendered report-output fragment to "What you get"

## 2026-07-31 — cross-skill gap audit fixes

- **causal-graph.example.yaml**, **evidence.example.json**, **scripts/validate_causal_graph.py** — the
  flagship example claimed 2 observability sources with only 1 real one (datadog); added a genuine
  second KubeSense corroborating signal and a validator cross-check (CG-09) so the count is never just
  self-reported
- **dependencies.md** — documented `kubesense-alerts`/`kubesense-dashboards` as escalation-target skills
- **SKILL.md**, **reference/thresholds.md**, **reference/evidence-schema.md** — standardized "single
  source" terminology on "observability source" with explicit GitLab/Jenkins/Jira exclusion
- **SKILL.md** — added missing squad-map row to the cross-skill escalation table
- **reference/evidence-quality.md**, **reference/manual-scoring.md** — resolved the dual-HIGH
  multi-cause claim and an unresolved MEDIUM-or-HIGH disjunction against actual worked-example evidence
- **reference/assessment-metadata.md**, **workflow/phase-4.md** — added `precision.correlator_sha` so
  the `skills-lock.json` correlator CLI pin is actually consumed per-report, not just recorded

## 2026-07-07 — database slow-query dashboard

- **SETUP.md** — shared dashboards table with `database-slow-query` (`uwk-w92-5ys`)
- **reference/query-investigation.md**, **reference/query-playbook.md** — dashboard fast-path for DB saturation / `query_governance` RCA

## 2026-07-07 — interrogate pass 2

- **scripts/incident_rca_policy_guards.py** — renamed module (pytest import collision fix)
- **workflow/phase-0.md** — read-only guardrail block (fixes SKILL.md link target)
- **tests/test_incident_rca_policy_guards.py** — expanded coverage (empty hypotheses, infra-only Phase 4)

## 2026-07-07 — portfolio hardening (v2.2)

- **docs/skill-framework/shared/prompt-injection.md** — shared untrusted-content guard
- **SKILL.md** — untrusted Jira/log guard; `skill-routing` + `prompt-injection` links
- **workflow/inputs.md**, **workflow/phase-1.md** — ingest-phase injection reminders
- **scripts/incident_rca_policy_guards.py** + **tests/test_incident_rca_policy_guards.py** — confidence caps, Phase 4 gate, unknown policy

## 2026-07-07 — prompt-engineering hardening (v2.1)

- **reference/gold-rca-excerpt.md** — compact few-shot for Phase 5 (deploy regression + inconclusive paths)
- **workflow/phase-5.md** — pre-render attestation checklist (`workflow_version: 1.2`)
- **reference/org-profiles.md** — OpenSearch/mpokket guardrails moved out of SKILL.md
- **reference/precedence.md** — scoring and evidence conflict resolution
- **SKILL.md** — slimmed entry (~110 lines); P0 guardrails (never invent metrics)
- **reference/phase-index.md** — exit-check column per step
- **report-template.md** — index header points to gold excerpt
- **reference/pressure-tests.md** — model-family note; happy/edge/adversarial + attestation rows
- **examples.md** — §Skill routing keywords

## 2026-07-02 — causal-graph invariant validator

- **`reference/causal-graph-schema.md`** — `causal_graph` YAML artifact (`schema_version: 1`): typed nodes
  (event/trigger/root_cause/contributing/systemic), evidence-backed edges (`field[index]` refs into the
  evidence bundle), hypothesis scoring arithmetic, conclusion.
- **`scripts/validate_causal_graph.py`** — CG-01–CG-08: acyclicity, edge evidence resolution, score
  arithmetic, confidence caps (single source / contradictions / trigger unknown / Assumed-only), display-score
  normalization, ruled-out consistency, no best-guess primary.
- **Phase 4** emits + validates the artifact; **Phase 5** gates rendering on it (workflow_version 1.1).
- **Lint** — `lint-incident-rca` validates the example graph; 22 new pytest cases.

## 2026-07-01 — Official kubesense-mcp skill dependency

- **dependencies.md**, **skills-lock.json**, **scripts/install-incident-rca-deps.sh** — pin and install
  `kubesense-ai/kubesense-mcp-skills` (`kubesense-mcp` skill).
- **Makefile** — `install-incident-rca-deps`; `install-incident-rca` runs deps first.
- **SKILL.md**, **SETUP.md**, **phase-0/1**, **lazy-load-index**, **mcp-capabilities.md** — MCP body
  primary via official skill; SPL CLI fallback only.
- **kubesense-spl.md**, **query-playbook.md** — reframed as MCP-first workflow.
- **phase-exit-criteria.md**, **pressure-tests.md**, **smoke-test.md** — aligned.

## 2026-07-01 — KubeSense-primary logs (mpokket — no Datadog logs)

- **query-playbook.md** — mpokket profile: `logs_primary: kubesense`; Datadog logs N/A; SPL mandatory
  for query text; `logs_source_profile` replaces mislabeled `log_coverage_gap`.
- **workflow/phase-1.md** — separate KubeSense-primary vs Datadog+KubeSense log workflows.
- **kubesense-spl.md**, **evidence-schema.md**, **evidence-coverage.md**, **SKILL.md** — aligned.
- **pressure-tests.md** — do not treat Datadog 0 rows as gap on mpokket.

## 2026-07-01 — Expensive-query onset signature (mpokket ES gap closure)

- **query-investigation.md** — mandatory §Phase 1 Expensive-query onset signature: CPU vs throughput
  divergence, caller baseline, onset APM slice, wildcard auto-flag, user reconciliation.
- **workflow/phase-1.md** — gate Phase 2 on onset signature; checkpoint announces traffic-spike ruled out.
- **SKILL.md** — red flags: `traffic_anomaly` ≠ causation; CPU↑ + requests↓; full-window retry drowning.
- **phase-exit-criteria.md**, **lazy-load-index.md** — onset signature exit checks.
- **evidence-schema.md** — rationalizations for traffic anomaly / service-owner contradictions;
  expanded `query_governance` steps.
- **manual-scoring.md** — bonuses for expensive-query signature, wildcard onset, `service_owner_finding`.
- **pressure-tests.md** — mpokket 2026-06-21 regression scenarios.
- **kubesense-spl.md** — §Query-string hunt for long `name=` / company endpoint / client channel.
- **query-playbook.md** — onset metric recipes; CWJ client-channel vs JVM watchdog disambiguation.
- **evidence.example.opensearch-query-governance.json** — updated to mpokket 2026-06-21 pattern.

## 2026-07-01 — KubeSense SPL log body integration

- **scripts/kubesense_logs.py** — SPL REST CLI with `--evidence` fragment for `error_signals[]`.
- **reference/kubesense-spl.md** — Phase 1 workflow when MCP logs are metadata-only.
- **phase-0/1**, **lazy-load-index**, **phase-exit-criteria**, **evidence-schema** — SPL CLI mandatory
  before `kubesense_metadata_only` gaps when `KUBESENSE_API_KEY` is set.
- **Makefile** — `kubesense-errors` target; `EVIDENCE=1` for evidence JSON.

## 2026-07-01 — phase exit criteria and evidence coverage dashboard

- **phase-exit-criteria.md** — normative exit gates per phase; linked from all workflow files.
- **evidence-coverage.md** — domain coverage dashboard, freshness, overall completeness %, confidence ceiling.
- **Unknown hardening** — no primary when all hypotheses ≤ MEDIUM after caps; no best-guess wins.
- **Initiating event** layer — distinct from trigger and root cause ([root-cause-depth.md](reference/root-cause-depth.md)).
- **Causal graph** — must be acyclic; feedback loops in prose only.
- **Incident class** taxonomy — Deploy, Software defect, Data quality, Security, etc.
- **Recovery effectiveness** — mitigation, effect, verification, residual risk.
- **Corrective vs preventive** — separate report sections.
- Red flags: conflicting evidence ignored, circular causal graph.

## 2026-07-01 — reproducible scoring and causal graph

- **evidence-quality.md** — normative score algorithm (base + bonuses − penalties → 0–100), confidence caps,
  counter-evidence requirements, hypothesis deduplication, multi-cause rules, incident type mapping.
- **SKILL.md** — inline evidence hierarchy and caps; causal graph in schema; dedup/multi-cause red flags.
- **report-template.md** — incident type, expanded customer impact, timeline Quality column, causal graph,
  per-hypothesis counter-evidence blocks, recovery trigger/owner/residual risk.
- **phase-3/4/5** — timeline quality, dedup before ranking, incident_type output, render checklist.
- **thresholds.md**, **manual-scoring.md**, **evidence-schema.md**, **root-cause-depth.md** — aligned with formula and graph.

## 2026-07-01 — deterministic executive RCA output

- **SKILL.md** — required inputs, mandatory report schema, strengthened read-only boundary, correlation guardrail wording.
- **report-template.md** — customer impact, detection analysis, ranked hypotheses (0–100 scores), evidence matrix,
  recovery analysis, corrective/preventive actions with owner/priority/ETA, Unknown conclusion path, read tiers.
- **reference/evidence-quality.md** — evidence hierarchy, quality labels, matrix rules, hypothesis scoring.
- **reference/root-cause-depth.md** — trigger vs root cause vs contributing factors vs systemic cause.
- **workflow/inputs.md** — expanded anchors (namespace, deploy SHA, consumer group, error signature).
- **workflow/phase-3.md** — timeline assembly + detection metadata before Phase 4.
- **workflow/phase-5.md** — updated render checklist and chat TL;DR tiers.

## 2026-07-01 — schema v4: query_signals validator

- **`query_signals[]` item validation** — `_validate_query_signals` enforces required `query_text`, `source`, `detected_at`; optional string/number field types mirror `error_signals` depth.
- **Tests** — opensearch example validity, missing `detected_at`, non-object entry, invalid `exec_count`.
- **Lint** — `lint-incident-rca` validates `evidence.example.opensearch-query-governance.json` alongside the base example.

## 2026-06-30 — KubeSense org profile: mpokket

- **Org profile — mpokket** in [query-playbook.md](reference/query-playbook.md) — `workload` not `service`;
  metadata-only logs (`body_length`, no message text); `level = 'ERROR'`; ≤1h `analyze-logs` windows;
  retry once on transient fetch errors.
- **Field discovery default** — when discovery shows `workload` and no `service`/`message`, apply mpokket profile.
- **Parallel caller log pivot** — workload filters; skip URI/text search when no body field; traces for attribution.
- **Evidence** — optional `kubesense_schema_profile: "mpokket"`; `kubesense_metadata_only` in `evidence_links[]`.
- **Gaps templates** — report-template + phase-1 for metadata-only KubeSense limitations.

## 2026-06-30 — schema v4: query governance & log coverage

- **schema_version 4** — add `query_governance` hypothesis (narrative alias `expensive_query`).
- **Expensive-query branch** — saturation + flat/<2× throughput triggers query investigation before pure `infra_capacity`.
- **Upstream mandate** — top-3 `@base_service` callers in first 10 min for ES/Redis/Kafka blast radius.
- **Log coverage fallback** — mandatory KubeSense when Datadog returns 0 rows (ES/OpenSearch); field discovery via `get-trace-or-log-fields` first.
- **Process failure guardrails** — `mcp_process_failure` vs `observability_backend_error`; MEDIUM cap when trigger Unknown and KubeSense skipped.
- **MCP profile format** — `(queried)` / `(attempted — no rows)` / `❌`; forbid Datadog-sufficient rationalizations.
- **Parallel caller log pivot** — Datadog + KubeSense when logs empty for top caller.
- **RUM + CWJ** — client-side RUM in Phase 1; JVM watchdog heuristics with user override.
- **OpenSearch example** — `query_governance` primary + `infra_capacity` co-cause.
- Validator accepts schema_version 4; new `evidence.example.opensearch-query-governance.json`.
