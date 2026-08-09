# ADR 0001: Canonical `skills.yaml` registry

**Status:** Accepted  
**Date:** 2026-08-08

## Context

Twenty-two portable skills lived in sibling directories with install edges scattered across the `Makefile`, generated adapters duplicated routing prose, and no single place to answer “what skills exist, how are they invoked, and what do they require?”

## Decision

- Add root `skills.yaml` as the **canonical platform registry** for install dependency edges, host discovery metadata, invocation mode, composition graph facts, and capability contracts.
- Keep agent-facing policy and workflow prose in each skill’s `SKILL.md`; the registry holds machine-checkable platform facts only.
- Generate thin `.cursor/rules/*.mdc` and `.kiro/steering/*` adapters from the registry (`make generate`).
- Gate merges with `make validate-registry` and `make generate-check`.

## Consequences

- **Positive:** One source of truth for install allowlists, composition validation, and generated discovery wrappers.
- **Positive:** Registry-driven installer can default to “install all registered skills” safely.
- **Negative:** Skill authors must update `skills.yaml` when install edges or invocation mode change; drift fails CI.
- **Follow-ups:** Capabilities backfill (#18), composition contracts v2 (#19), compatibility matrix generation (#17).
