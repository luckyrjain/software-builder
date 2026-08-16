# Batch 5 Operationalize Upkeep Implementation Plan

## Goal

Implement the prompt-audit Batch 5 backlog (`I-01` through `I-08`) on top of the latest `main`:

1. Add `lint-prd-architect` to `.PHONY` and enforce target presence.
2. Publish a deterministic prompt-system health report.
3. Separate runtime, reference, and maintainer-only files visibly.
4. Add stable IDs to routes, stop conditions, and report fields.
5. Add owners to cross-cutting contracts and enforce ownership review metadata.
6. Add a deprecation policy for prompt modules and artifact schemas.
7. Pin review evidence/provenance in generated reports.
8. Add prompt-diff risk labeling and stronger validation for behavioral, authority/capability, schema, and routing changes.

## Exit gate

CI publishes deterministic health/provenance and enforces ownership, deprecation, and prompt-diff risk. Full CI must pass, followed by two consecutive independent deep reviews with zero actionable findings on the same unchanged head.

## Design

Keep upkeep policy machine-readable and fail closed. Extend the existing registry/eval platform rather than inventing a second metadata system. Generated outputs remain deterministic and checked for drift. Runtime prompts consume stable IDs and provenance only where those fields materially improve routing, evaluation, or handoff diagnostics; maintainer-only metadata must not inflate runtime context.

## TDD slices

### Slice 1 — Baseline upkeep invariants (`I-01`, foundation for `I-02`)
- Add a failing regression proving every repository lint target that is intended for direct invocation is declared `.PHONY`, including `lint-prd-architect`.
- Fix the Makefile declaration.
- Add a deterministic health-report model and tests for core counts and stable ordering before wiring generation.

### Slice 2 — Health report and file-role taxonomy (`I-02`, `I-03`)
- Define machine-readable file roles (`runtime`, `reference`, `maintainer`) with validation against registered skill trees.
- Generate a deterministic health snapshot covering skills, contracts, eval tiers, route/token-budget coverage, external dependencies, authority levels, and orphan runtime modules.
- Wire drift validation into `make lint` and publish the report as a CI artifact or committed generated snapshot.

### Slice 3 — Stable IDs and ownership (`I-04`, `I-05`)
- Define stable IDs for routes, stop conditions, and structured report fields at canonical contract boundaries.
- Add owner metadata for capability schema, composition schema, safe-output, artifact writes, routing, adapter generation, and eval infrastructure.
- Validate uniqueness/reachability of IDs and completeness of ownership declarations.

### Slice 4 — Lifecycle and provenance (`I-06`, `I-07`)
- Add a deprecation contract with compatibility window, replacement/alias metadata, migration notes, and removal criteria/tests.
- Add repository revision, registry schema version, prompt bundle version, and evaluator version to generated audit/eval outputs where applicable.
- Add regression tests proving deterministic provenance and fail-closed malformed lifecycle metadata.

### Slice 5 — Prompt-diff risk policy (`I-08`)
- Classify prompt changes as editorial, behavioral, authority/capability, schema, or routing.
- Require stronger checks for the latter four classes using changed-path/contract metadata rather than prose heuristics alone.
- Emit a deterministic risk summary suitable for CI and code review.

### Slice 6 — Integration and convergence
- Run registry validation, evals, generated-file checks, full lint and security CI.
- Review the complete `main...head` diff for stale/generated drift, runtime-context bloat, unenforced metadata, unstable IDs, ownership loopholes, lifecycle bypasses, provenance nondeterminism, and risk-label false negatives.
- Fix findings and reset the review counter after any code change.
- Finish only after two consecutive independent deep reviews report zero actionable findings on the same green head.
