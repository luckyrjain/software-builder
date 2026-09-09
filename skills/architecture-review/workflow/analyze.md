---
workflow_version: 1.0
phase: analyze
produces:
  - decision_rationale
  - risk_findings
  - scale_limit_findings
  - failure_mode_findings
  - security_findings
  - operability_findings
  - alternatives_findings
consumes:
  - proposal_text
  - design_description
  - diagram_description
  - repo_context
---

# Analyze — evaluate the proposed architecture

Run all six checks below over `design_description` (grounded in `proposal_text`, and where supplied,
`diagram_description`/`repo_context`). Every check produces a finding — including an explicit `Unknown`
when the check cannot be completed — never a silent skip.

## 1. Architecture decision (what + why)

State what is being proposed and why, in the proposal's/design's own terms — the shape of the system,
the core technical choice being made, and the stated motivation. This grounds every other check: a
finding in Scale limits or Failure modes should trace back to a specific element of this decision, not a
generic checklist item.

## 2. Scale limits

For each load/data-volume dimension the proposal itself implies matters (request rate, data volume,
concurrent users, fan-out, retention), identify where the design breaks down — the point at which a
described component or pattern (a single writer, an unindexed table, a synchronous fan-out call,
in-memory state) stops holding under stated or reasonably inferred growth. Cite the specific line or
element of `design_description` that creates the limit. If the proposal states no scale target at all,
record that gap explicitly rather than inventing one.

## 3. Failure modes

Enumerate what can fail — a dependency outage, a partial write, a message loss, a retry storm — and for
each, state whether the design specifies detection (how the failure becomes visible) and recovery (how
the system returns to a good state, or what a human must do). A failure mode with no stated detection or
recovery is a material, unresolved risk, not a "None found."

## 4. Security posture

Evaluate at the architecture level, not the code level: trust boundaries (where does untrusted input or
an external party cross into the system), data flow (what moves where, and is it the least amount
necessary), and blast radius (if one component is compromised or a boundary fails, what else is
reachable). When `diagram_description` is supplied, cross-check trust-boundary claims against it. When
absent, record boundary-dependent sub-checks as `Unknown` rather than assuming the prose description is
complete.

## 5. Operability

Identify who runs this once it ships (a named team, or `Unknown` if the proposal doesn't say) and what it
costs to operate — new on-call surface, new infra to provision/monitor, new failure classes an existing
runbook doesn't cover. A design with no named owner and no stated operating-cost signal is a material gap,
not an implicit "someone will handle it."

## 6. Alternatives considered

Extract what alternative designs the proposal/design states were considered and why each was rejected in
favor of this one. When `proposal_text`/`design_description` states no alternatives at all, record that as
a gap (`Unknown — no alternatives stated`), not as "no alternatives needed" — a high-stakes architecture
decision with zero stated alternatives is itself a finding worth surfacing to Report.

## Evidence gaps

Any of the six checks that cannot be completed — because `design_description` is too sparse, or a check
specifically depends on `diagram_description`/`repo_context` that wasn't supplied — is recorded as an
explicit finding of `Unknown`, with the specific reason named (what's missing, what it would take to
close the gap). Never silently skipped, never folded into a "clean" result. This feeds Report's verdict
derivation directly: a gap on a required check drives the verdict to at least `Needs rework`.
