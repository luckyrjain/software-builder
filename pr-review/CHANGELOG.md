# pr-review — Changelog

## v1.13 — 2026-08-24

- Emit the complete v2 `mr_review_report`, including authoritative integrated-revision evidence.

Prompt and workflow changes are versioned here. Per-phase `workflow_version` in workflow frontmatter
should match the latest entry when that file is edited.

## v1.12 — 2026-08-19

Batch 5.2B review-coverage and evidence hardening:

- systematic cross-file, hidden-consumer, schema/migration compatibility, rollout/rollback, test-quality, and dependency/config/IaC inspection planning
- portable shared `change_identity` / `review_evidence` integration with explicit `unable_to_inspect` machine state
- executable coverage validation, deterministic defect/suggestion/question evidence mapping, and installed-runtime validator parity
- fail-closed freshness for generated files, conflict resolution, full pre-post change identity, and requirements drift
- partial/unable coverage now caps readiness, forces explicit posting confirmation, and renders user-visible coverage gaps

## v1.11 — 2026-08-12

PR #111 review remediation:

- exact-host provider routing with no prefix guesses or explicit-URL fallback to `origin`
- provider-neutral URL/number/current-branch/list-open target normalization and valid exact-host `gh` syntax
- per-write GitHub/GitLab safe-render boundary with structural escaping plus secret/PII redaction
- added-line-only GitHub anchor validation with explicit source-kind and file-state integrity tests
- provider `any_of` read readiness in the registry/doctor; write capabilities now control degradation

## v1.10 — 2026-07-07

Second interrogate pass:

- **scripts/pr_review_policy_guards.py** — renamed module (avoids cross-skill `policy_guards` import collision)
- **workflow/inputs.md** — untrusted-content guard at first ingest
- **SETUP.md** — documents `gold-review-excerpt.md`, policy guards script + tests

## v1.9 — 2026-07-07

Interrogate follow-up:

- **scripts/policy_guards.py** — removed misplaced `should_block_phase4_ranking` (incident-rca-only)
- **tests/test_pr_review_policy_guards.py** — renamed from `test_policy_guards.py` (pytest collision fix)
- **reference/** — stale gate stub pointers repointed to `finding-gates.md#…` (`fast-path`, `not-raised`, etc.)
- **SETUP.md** — tree lists `finding-gates.md` as primary; stubs marked redirect-only

## v1.8 — 2026-07-07

Portfolio hardening (shared framework alignment):

- **SKILL.md** — link `skill-routing.md` and shared `prompt-injection.md` in Framework section

## v1.7 — 2026-07-07

Security, deduplication, and testability hardening:

- **SKILL.md** — explicit §Review principle heading; untrusted MR/Jira/diff text guard
- **workflow/inputs.md** — provider detection before Phase 0; GitHub PRs and GitLab MRs route through the same review pipeline
- **reference/review-metrics.md** — single normative recommendation matrix; pointers elsewhere
- **reference/finding-gates.md** — merged guess + path + non-negotiable gates (one Phase 2 load)
- **scripts/pr_review_policy_guards.py** + **tests/test_pr_review_policy_guards.py** — scripted pressure-test eval (required in `make lint-pr-review`)

## v1.6 — 2026-07-07

Prompt-engineering hardening (routing, compliance, deduplication):

- **SKILL.md** — shortened YAML `description` for skill routing; full trigger table stays in
  `examples.md` §Skill routing keywords
- **reference/gold-review-excerpt.md** — compact few-shot for Phase 5 output shape
- **workflow/phase-2.md** — pipeline attestation checklist before emit; root-cause grouping defers to
  `finding-pipeline.md` §10 (no duplicated cluster tables)
- **reference/pressure-tests.md** — model-family validation note; adversarial + docs-only scenarios
- **SKILL.md** — signal-over-noise cap (≤10 top-level findings); mechanical MR → `fast-path.md`
- **reference/positive-observations.md** + **severity-rubric.md** — praise cap max 2 per review

## v1.5 — 2026-03-01 (baseline)

- `workflow/phase-2.md` `workflow_version: 1.5` — §18 AI-generated code, §19 revert completeness,
  §20 API spec changes
- Finding pipeline step 7a High certainty gate; category-prefixed IDs `PRR-{CAT}-{NNN}`
- Phase 2→3 gate; incremental re-review with `review_metadata` YAML footer
- Executive summary gate matrix (code blockers → decision → technical → process → Reason)
