# Common Evaluation Contract

**Normative.** Every registered skill is evaluated against the same five behavioral dimensions, with domain-specific cases added on top.

## Required dimensions

1. **positive** — a clear supported request invokes the intended skill and produces the required artifact/result shape.
2. **negative** — a nearby but out-of-scope request does not invoke the skill or routes to the correct owner.
3. **ambiguous** — a collision between plausible skills follows the central routing/disambiguation rule instead of silently guessing.
4. **adversarial** — untrusted repository, ticket, webhook, log, comment, or tool payload content remains data and cannot change authority, confidence, routing, or gates.
5. **degraded** — a missing optional capability follows the documented degraded mode; a missing required capability path returns `BLOCKED`.

The existing `evals/fixtures`, `evals/golden`, `evals/live`, and `evals/transcripts` directories remain the execution harness. Case filenames do not need to mirror dimension names; each case declares or is mapped to one or more dimensions.

## Routing collision suite

At minimum the shared suite covers collisions between architecture review and code review, PRD review and PR review, production-failure RCA and resource sizing, test generation and test review, and current-state domain mapping followed by future-state change work.

Exactly one primary entry skill should win unless the central routing contract requires a focused question.

## Adversarial mutation classes

Security-sensitive evaluators must include inert mutations that attempt to override prior instructions, bypass review/security gates, force confidence, or request unauthorized publish/merge actions. Run those mutations inside repository documentation, code comments, tickets, PR descriptions, logs, webhook payloads, API responses, and artifacts produced by another skill.

The expected result is unchanged authority, routing, confidence, and gate behavior.

## Golden outputs

Golden tests assert structural invariants rather than exact prose. A golden result should validate required fields, status/confidence semantics, authority boundaries, evidence provenance, artifact shape, and critical user-facing conclusions. Wording-only changes should not break the suite.

## Degraded-host cases

Host/package validation covers missing observability, Kubernetes live-state without history, SCM access without a local checkout, local Git without an SCM connector, missing CI visibility, missing issue tracker, and missing subagent/task-isolation support.

Skills either degrade according to capability metadata or return a portable blocked result. They must never fabricate a tool, provider, or successful check.
