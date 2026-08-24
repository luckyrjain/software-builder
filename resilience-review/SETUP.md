# Setup — resilience-review

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

Run [reference/smoke-test.md](reference/smoke-test.md) after setup or runtime changes.
