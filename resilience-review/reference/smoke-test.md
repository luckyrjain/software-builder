# Smoke test — resilience-review

Run this after installation or a runtime change.

1. Invoke the runtime with proposed_state, all ten documented controls, one dependency path, and
   repository evidence. Confirm an Approved report with normalized_decision.status PASS.
2. Invoke current_state with the same caller-supplied evidence but no opaque runtime trust metadata.
   Confirm Blocked — insufficient evidence and UNKNOWN.
3. Invoke current_state through typed assessment_context with runtime-owned trust metadata that
   attests repository evidence. Confirm PASS only when the candidate revision and required
   environment identity match.
4. Mark timeout_budgets as runtime_config_dimensions and omit the source environment. Confirm the
   timeout condition is UNKNOWN rather than PASS.

The report must contain the canonical runtime envelope sections and exactly the eight declared
resilience_review_report payload fields.

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
