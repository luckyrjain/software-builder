---
workflow_version: 3.0
phase: report
produces:
  - dora_report
consumes:
  - validated_graph
---

# Report presentation

**v3.0:** Graph is built in [build-graph.md](build-graph.md), validated in [validate-invariants.md](validate-invariants.md), transformed in [render.md](render.md). This file defines **how the rendered DORA reads to humans** — not graph construction.

Pipeline: DISCOVER_SOURCES → RESOLVE → COLLECT → … → VALIDATE_INVARIANTS → **RENDER** ([render.md](render.md))

## Two layers

| Layer | Spec | When |
|-------|------|------|
| **Human Report** | [report-template.md](../report-template.md#human-report-primary) · [templates/human-report.md](../templates/human-report.md) | Always — default deliverable |
| **Technical Appendix** | [report-template.md](../report-template.md#technical-appendix-audit-debug) · [templates/appendix.md](../templates/appendix.md) | Full DORA: always; summary-only: omit |

Renderer field mapping: [render/markdown.md](../render/markdown.md).

## Human-first rules

Apply to the Human Report only. The graph and appendix keep full IDs.

1. **Translate IDs to labels** — use human names from [observation-ids.md](../reference/observation-ids.md) (e.g. `OBS_CPU_P95_FLEET` → "Fleet CPU p95"). Never show `OBS_*` / `DEC_*` / `REC_*` / `EVID_*` in the human body.
2. **Recommendation lead** — open with emoji recommendation block ([human-report.md](../templates/human-report.md#executivesummary)): heading `## Recommendation`; 🟢 keep/trim · 🟡 investigate/defer · 🔴 blocked · ⬆️ scale up. **Lead with changes, then holds** — first sentence states what will change (concrete values/range when known); second sentence states what stays unchanged and brief why (max two sentences before Severity). Pure KEEP: lead with the hold. Canonical: *"Increase memory requests to approximately 1.5–1.75 GiB. Keep CPU requests and replica count unchanged until Kafka lag telemetry is available."*
3. **Confidence** — show band + numeric + **Basis** bullets in Human Report (e.g. `Assessment confidence: Very High (0.9)` then factor bullets). Formulas (`0.35 × …`) → [reference/confidence-formula.md](../reference/confidence-formula.md) / [reason.md](reason.md) — **never** default render.
4. **Metadata** — `schema_version`, `threshold_version`, hashes, `AssessmentFingerprint` → Assessment Metadata appendix only.
5. **Validation** — `INV-01`–`INV-14`, contradiction/cost gate tables → Validation appendix only.
6. **Evidence registry** — full ID tables → Evidence Registry appendix only. Human Report Evidence uses label + value prose/table, **sorted by importance** (fleet p95 → Kafka lag → memory peak → HPA → CPU avg → HTTP → restarts → manifest).
7. **Decision graph** — `DEC_*` Reasons lines with `✓ OBS_*` → Decision Graph appendix only. Human Report Optimization Decision uses plain language.
8. **Recommendations** — sort **concrete work before holds**; when observability and sizing both apply, list observability first (Instrument Kafka lag → Raise memory → Keep CPU → Keep replicas). Tier spec: [render/markdown.md](../render/markdown.md#recommendationssummary-sort-order). **Decision** (`Keep` / `Ready` / `Defer` / `Blocked`) and **Decision confidence** on separate lines — not `(Blocked, High confidence)`. `REC_*_KEEP` + graph `BLOCKED` → **Decision: Keep**, not Blocked. `REJECTED` recs → **Changes evaluated but not recommended** section only. Appendix LifecycleSummary **State** uses display labels (`KEEP` / `DEFER` / `CHANGE` / `NOT RECOMMENDED`) — [render/markdown.md](../render/markdown.md#appendix-recommendation-status); graph JSON keeps raw enum.
9. **Risks** — open with `Overall:` one-sentence framing; then order bullets by operational impact: missing telemetry → partition skew → fixed HPA → batch behavior → cost.
10. **Conclusion** — last Human Report section before appendix separator; 2–4 sentences, no automation CTAs.
11. **No agent instructions** — Human Report MUST NOT include agent mode instructions (e.g. "Type ACT"), posting confirmations, or MCP setup steps. Post-render chat instructions live in `SKILL.md` and [post-action-templates.md](../../docs/skill-framework/shared/post-action-templates.md).
12. **Uppercase budget** — target **< 20** uppercase tokens in the Human Report (verdict enums and severity OK; registry IDs not OK).

Internal reasoning ([reason.md](reason.md)) and normalization ([evidence.md](evidence.md)) still use IDs — only **render** translates for humans.

## Full DORA vs summary-only mode

| Mode | Human Report | Technical Appendix | Trigger |
|------|--------------|-------------------|---------|
| **Full DORA** (default) | Yes | Yes — Decision Graph + Evidence Registry + metadata/validation | Standard assessment, audit trail, repeat reviews |
| **Summary-only** | Yes | No | User asks for "summary", "executive brief", "no appendix", or channel limits (Slack, ticket comment) |

Summary-only still requires a validated graph internally; omit only the rendered appendix. JSON export ([render/json.md](../render/json.md)) is always lossless regardless of markdown mode.

## Delivery pointers (Ready recommendations)

For every **READY** change recommendation, render a **Where to apply** line in
[RecommendationsSummary](../templates/human-report.md#recommendationssummary). Source:

1. Git MCP manifest path from [collect-metrics.md](collect-metrics.md) / [SETUP.md](../SETUP.md)
2. User-provided chart or overlay path
3. Inferred layout (`helm/`, `k8s/`, `deploy/`, Terraform module) with *confirm with owner* when unverified

Map resource field to human label (e.g. *CPU requests under `resources.requests`*). Full table:
[templates/recommendations.md](../templates/recommendations.md#delivery-pointer-change-recs-only).

## Post-change verification block

When ≥1 **READY** change rec exists, append [PostChangeVerification](../templates/human-report.md#postchangeverification)
after Recommendations. Default soak: **7d** (or `assessment.review_after`). Instruct the user to
re-run this skill and compare throttle, p95, OOM, and lag against rollback triggers — **in chat only**, not as "Type ACT" in the Human Report body.

## Section order (markdown)

```text
# Deployment Optimization Readiness Assessment

## Recommendation
## Current Health
## Optimization Decision
## Evidence
## Recommendations
## Changes evaluated but not recommended  (when REJECTED recs exist)
## Risks
## Conclusion

---
## Technical Appendix
[Decision Graph → Evidence Registry → Assessment Metadata → Validation — full DORA only]
```

Section contract: [reference/report-schema.md](../reference/report-schema.md).

## Smoke test

Human Report hygiene checks are consolidated in [reference/smoke-test.md](../reference/smoke-test.md) (items 5–7).
Run the full checklist there after any skill edit.

## `assessment_metadata` footer (platform analytics)

Emit a fenced ` ```yaml ` block after **Conclusion** in the Human Report (and in full DORA appendix when
`full` mode). Normative spec: [review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md) §8.2.

| Block | When to emit |
|-------|----------------|
| **Core** | Every assessment — `service`, `final_decision`, `assessment_confidence` |
| **`history`** | Repeat assessment on same service when prior `assessment_metadata` or DecisionHistory parseable |
| **`precision`** | Every assessment with evaluated recommendations |
| **`investigation_quality`** | When computable; omit on blocked/stop-reason reports |

**`history` population:** mirror DecisionHistory from graph `decision_history` when present; set
`assessment_iteration` from prior footer count + 1. When ≥1 **READY** change rec exists, also set:

```yaml
history:
  review_after: "7d"                    # from assessment.review_after or default 7d
  next_assessment_due: "<ISO-8601>"     # finished + review_after — machine-schedulable recheck
  scheduled_recheck_prompt: "Re-run rightsizing assessment for `{deployment}` `{env}` — 7d post-change verification"
```

Populate `next_assessment_due` from `finished` + `review_after` (default **7d**). The Human Report
PostChangeVerification block remains user-facing prose; **`assessment_metadata.history`** is the
machine-readable scheduling hook for cross-session analytics.

**Precision linkage:** count `recommendations[]` by lifecycle state (`READY`, `DEFER`, `BLOCKED`,
`REJECTED`); set `avg_decision_confidence` from graph `assessment.assessment_confidence.score`.

Renderer: append block in [render/markdown.md](../render/markdown.md) §Assessment metadata footer.
