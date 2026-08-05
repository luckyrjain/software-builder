# PR Review — Governance Layer Design

**Date:** 2026-06-29  
**Status:** Implemented (workflow_version 1.4)  
**Scope:** Deterministic finding pipeline, precedence, non-negotiable baseline, workflow contracts, capability discovery, framework metrics

## Problem

After the workflow split (thin orchestrator + lazy-loaded modules), the skill behaves as a **review
framework** — but Phase 2 reasoning was still implicit: detection and judgment intertwined, gate order
ambiguous, module conflicts unresolved, and no versioned contracts between phases.

## Goals

1. **Deterministic pipeline** — explicit detect → judge steps for every candidate finding.
2. **Don't-guess gate** — separate from execution path; suppress inference without evidence.
3. **Precedence stack** — user → repo YAML → workflow/fast path → defaults.
4. **Non-negotiable baseline** — secrets, auth, injection always checked regardless of fast path/persona.
5. **Workflow contracts** — `workflow_version`, `produces`, `consumes` on each phase file.
6. **Capability discovery** — infer stack from manifests/paths; enable checklist triggers.
7. **Review metrics** — optional self-observability in summary Notes.

## Non-goals (v1.4)

- Cross-MR metrics persistence or dashboards.
- Automated import-graph or dependency tooling.
- Separate `/pr-review-governance` skill.
- Changing MCP tools or `diff-to-positions.py`.

## Artifacts

| File | Role |
|------|------|
| `reference/finding-pipeline.md` | Authoritative 11-step emit order |
| `reference/detection-vs-judgment.md` | Detector vs judge roles |
| `reference/dont-guess-gate.md` | Evidence sufficiency (step 3) |
| `reference/false-positive-suppression.md` | Execution path (step 4); order updated |
| `reference/non-negotiable-checks.md` | Always-on baseline |
| `reference/precedence.md` | Conflict resolution |
| `reference/capability-discovery.md` | Phase 1 `capability_profile` |
| `reference/review-metrics.md` | Optional `review_metrics` schema |
| `workflow/*.md` | Front matter contracts v1.4 |
| `workflow/phase-2.md` | Pipeline-centric rewrite |
| `workflow/phase-1.md` | Capability discovery after fast path |
| `reference/review-rules.md` | `always_review` schema |
| `SKILL.md` | Guardrails, lazy-load table, reference index |

## Finding pipeline (summary)

```text
Detect → Evidence → Don't-guess → Execution path → Dedupe → Non-negotiable waiver
  → Contextual severity → Feedback learning → Value filter → Rank → Output
```

Stop-search counts **emitted** findings after pipeline. Non-negotiable checks complete on current hunk
even when stop fires.

## Precedence (summary)

1. Explicit user request  
2. Repository `review-rules.yaml` (including `always_review`, `persona`, `stop_search`)  
3. Workflow phase + `fast_path` flags  
4. Reference defaults + non-negotiable list  

## Workflow contracts (v1.4)

Each `workflow/*.md` declares YAML front matter:

```yaml
workflow_version: 1.4
phase: 2
produces: [findings, review_metrics, root_cause_groups]
consumes: [review_boundary, fast_path, capability_profile, ...]
```

Phases must not assume artifacts not listed in a prior phase's `produces`.

## Capability discovery

Phase 1 step 2 (after fast path): infer from `go.mod`, `package.json`, `k8s/`, `*.tf`, etc. Emit
`capability_profile` — cached in `context_cache` when unchanged. Phase 2 uses for § triggers and persona
auto-detect.

## Review metrics

Optional Notes line: candidates, emitted, suppressed breakdown, stop_search, context_cache state.
Human tuning only — no required persistence.

## Verification

- `make lint-pr-review` — pytest + py_compile unchanged.
- `reference/smoke-test.md` — added pressure tests for don't-guess, precedence, capability profile.

## Future (post v1.4)

- Structured cross-MR metrics export.
- Repo-local `review-metrics.yaml` thresholds.
- Detector plugins as separate YAML (without bloating checklist).
