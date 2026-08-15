# Batch 4 Host Portability Implementation Plan

## Goal

Implement platform backlog items 30–35 on top of the latest `main`:

1. Formal host adapter interface.
2. ChatGPT/Codex packaging validation.
3. Claude plugin validation.
4. Cursor generated-rule validation.
5. Kiro steering validation.
6. Deterministic generic-agent package generation.

## Design

Treat `scripts/registry/host_contracts.yaml` as the capability contract source. Add a small runtime API that resolves a host/capability to FULL, DEGRADED, or UNSUPPORTED without brand-specific branching inside skills. Add a repository-level portability validator that checks every supported host surface against `skills.yaml` and canonical `SKILL.md` files.

Cursor and Kiro remain generated per-skill adapters. Claude and Codex/ChatGPT remain canonical-root packages. Generic packaging is generated deterministically from canonical skill directories plus the shared framework/registry files needed to resolve references after extraction.

## TDD slices

### Slice 1 — Host adapter interface
- Add failing tests for the six canonical hosts, ten capability families, support-state validation, and unknown host/capability fail-closed behavior.
- Implement `scripts/registry/host_adapter.py`.

### Slice 2 — Host packaging parity
- Add failing tests for exact Cursor/Kiro skill surfaces, canonical `SKILL.md` references, Claude/Codex package roots, ChatGPT portable-package identity, automation-only semantics, and canonical routing/runtime contract reachability.
- Implement `scripts/registry/host_portability.py` and `evals/host-parity/expected.yaml`.
- Wire portability validation into `scripts.registry validate`.

### Slice 3 — Generic package
- Add failing tests that require a deterministic `software-builder-skills.tar.gz` payload containing all registered skills and required shared contracts, with no `.git`, CI, cache, or secret files.
- Implement `scripts/registry/generic_package.py` and a registry CLI `package-generic` command.
- Build the archive with normalized ownership, permissions, ordering, and timestamps.

### Slice 4 — Integration and review
- Run registry validation, evals, generated-file checks, full lint and security CI.
- Review the complete `main...head` diff for missing host semantics, stale generated surfaces, unsafe package contents, nondeterminism, path traversal, broken relative references, and host-brand leakage into core skill logic.
- Fix findings, then perform two consecutive independent deep reviews with zero actionable findings before marking the PR ready.
