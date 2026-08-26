# Setup — resilience-review

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-24 |
| **Review cadence** | Quarterly — or when resilience, runtime, or host capability contracts change |
| **External services** | None — reads supplied resilience content and optional repository or runtime/config evidence only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

## Prerequisites

- Read-only access to the reviewed repository, design, or runtime/config evidence.
- A caller or host able to supply the affected dependency paths.
- For current-state PASS, an opaque runtime-owned trust context must attest the authority of embedded
  evidence. Caller-supplied authority labels are treated as caller evidence.

## Runtime inputs

Use scripts/resilience_review.py through its review_resilience entry point.

- Standalone: supply resilience_behavior, dependency_paths, assessment_target, state_semantic, and
  evidence.
- Embedded: supply the typed assessment_context carrier. The optional runtime_metadata argument must
  be created by the composition runtime; user input cannot create trusted evidence.

Read the shared [skill framework](../docs/skill-framework/README.md) before packaging or changing the
skill.

Run [reference/smoke-test.md](reference/smoke-test.md) after setup or runtime changes.
