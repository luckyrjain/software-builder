# Agent Compatibility Expansion — Approved Phase 1 Requirements

This document records the Phase 1 requirements extracted from the approved
agent-compatibility architecture supplied on 2026-08-31. The full approved
architecture remains the governing product decision; this phase deliberately
implements only the baseline, canonical-skill validation, and host-registry
schema foundations.

## Invariants

- `SKILL.md` is the only canonical workflow implementation for a skill.
- `skills.yaml` remains the canonical owner of skill identity, composition,
  capability requirements, degraded modes, risk classes, and lint policy.
- `agent-hosts.yaml` is the canonical owner of host identity, aliases,
  surfaces, discovery roots, targets, precedence, host capabilities,
  isolation, constraints, evidence, and maintainer support.
- Host-specific workflow bodies and portable-skill permission broadening are
  forbidden.
- Existing `scripts/install.sh` command meanings, including `--agent all`,
  are frozen before behavior changes.
- Unknown and malformed registry values fail closed with deterministic errors.

## Agent Skills conformance in this phase

Every canonical skill must have a `SKILL.md` with valid YAML frontmatter that
contains `name` and `description`. The name must be lowercase kebab-case,
match the containing skill directory, be at most 64 characters, and have no
leading/trailing/consecutive hyphens. The description must be non-empty and at
most 1024 characters. The validator must not require host-specific fields.

## Host registry schema in this phase

`agent-hosts.yaml` uses schema version 1 and validates unique host IDs, unique
target IDs, known aliases and targets, supported execution surfaces, safe path
templates using only `{project_root}` and `~`, scope/path consistency,
capability values from `AVAILABLE`, `UNAVAILABLE`, and `UNKNOWN`, supported
discovery and verification enums, and evidence shape. Existing Cursor,
Claude, and Kiro behavior must be representable without a second per-skill
host matrix.

## Out of scope

This phase does not change installer destinations, add universal installation,
remove the current host model, implement shadow detection, change doctor
output, or publish compatibility claims for unverified hosts.
