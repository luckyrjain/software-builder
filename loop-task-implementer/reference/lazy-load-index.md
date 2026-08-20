# Lazy-load index

Load only the file(s) the active role needs. This is not an optimization — it's the isolation
guarantee: giving a role file it doesn't need is how implementation framing leaks into an
independent review.

| Active context | Load | Never load |
|-----------------|------|------------|
| Orchestrator | [workflow/orchestrator.md](../workflow/orchestrator.md), mandatory [workflow/orchestrator-lifecycle.md](../workflow/orchestrator-lifecycle.md), [state-schema.yaml](state-schema.yaml), [review-lifecycle-contract.yaml](review-lifecycle-contract.yaml); additionally load [workflow/lifecycle-gate.md](../workflow/lifecycle-gate.md) immediately before READY/COMPLETE/merge | `workflow/builder.md`, `workflow/reviewer.md` (dispatch these to fresh sessions instead of reading them yourself) |
| Builder (fresh session) | [workflow/builder.md](../workflow/builder.md), the assigned task + acceptance criteria, accepted findings (remediation only) | `workflow/reviewer.md`, prior Reviewer verdicts, Orchestrator scratchpad |
| Reviewer (fresh session) | [workflow/reviewer.md](../workflow/reviewer.md), assigned lens, neutral review package; after return the Orchestrator applies [workflow/reviewer-evidence.md](../workflow/reviewer-evidence.md) to normalize portable evidence | `workflow/orchestrator.md`, `workflow/builder.md`, PR narrative, branch name, commit messages, prior lens verdicts |
| Anyone setting up a new host agent | [platform-adapters.md](platform-adapters.md) | — |
| Anyone auditing schema fields | [state-schema.yaml](state-schema.yaml), [review-lifecycle-contract.yaml](review-lifecycle-contract.yaml) | — |

`SKILL.md` itself is thin by design — it is always safe to load for any role, since it contains no
role-specific scratchpad or narrative.
