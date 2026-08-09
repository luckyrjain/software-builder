---
workflow_version: 1.0
phase: gate
produces:
  - final_artifact
  - build_readiness
consumes:
  - repaired_requirements
  - remaining_blockers
  - response_mode
  - depth
  - critique_only
---

# Gate — lint, readiness, emit

## Pre-output lint

Verify:

- mode and depth match the request
- problem was challenged, not assumed
- relevant alternatives considered
- MVP and Non-Goals are clear
- material requirements are testable and non-contradictory
- critical workflows have defined outcomes
- triggered state/data/correctness rules satisfied
- realistic failures have defined behavior
- accepted adversarial findings were repaired
- security/privacy/compliance analysis matches actual risk
- assumptions distinguishable from facts
- critical acceptance criteria exist
- existing-system changes include Change Impact when needed
- rollout/reversal defined where material
- no irrelevant sections or boilerplate
- within depth word budget

If context limits force prioritization, preserve in order: critical product behavior → correctness/safety
→ MVP requirements → acceptance criteria → blockers/readiness → optional analysis.

## Build Readiness

Assign **exactly one** verdict:

| Verdict | When |
|---------|------|
| **Ready** | Implementation can safely begin |
| **Ready With Non-Blocking Questions** | Implementation can begin; decisions remain |
| **Not Ready** | Material blockers remain |

**Not Ready** when any applies:

- unresolved Critical finding
- unresolved High finding makes implementation unsafe
- critical workflow lacks defined outcome
- critical business rule ambiguous
- Risky assumption affects MVP viability without acceptable validation plan
- required security/regulatory behavior unknown
- critical acceptance criteria absent
- core requirements materially contradict

Do not use numeric self-scoring as a substitute.

## Unresolved questions

Classify every material unknown:

| Category | Meaning |
|----------|---------|
| **Blocking Before Build** | Cannot safely begin implementation |
| **Required Before Launch** | May implement; cannot launch |
| **Can Resolve During Implementation** | Important but non-blocking |

Never use generic TBD.

## Emit

Produce per [output-contract.md](../reference/output-contract.md):

| Mode | Always output |
|------|---------------|
| PRD | Final PRD + Build Readiness |
| Review | Repaired PRD + Material Changes + Build Readiness (unless `critique_only`) |
| Validation | 7-section assessment |

Template: [report-template.md](../report-template.md).
