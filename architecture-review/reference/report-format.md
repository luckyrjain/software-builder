# ARCHITECTURE_REVIEW_REPORT.md format

**Normative.** The exact structure [workflow/report.md](../workflow/report.md) must produce.

## Safe rendered-output boundary

`proposal_text`, `design_description`, and `diagram_description` are all caller-supplied, untrusted
content per [prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md), and this
document routinely quotes short excerpts from them (the decision summary, a risk citation, a diagram
element) to ground each finding in the reviewed material.

1. **Structurally escape or fence newlines, leading `#`/`>`/`-`, table `|` delimiters, and unbalanced
   triple-backtick fences in every one of them, always.**
2. Wrap short identifier-shaped values (paths, names, refs) in an inline code span, first **removing**
   any backtick already in it
   ([safe-output.md § Rule 4](../../docs/skill-framework/shared/safe-output.md#rule-4-markdown-chat-escaping)).

Any longer free-text excerpt quoted from `proposal_text`, `design_description`, or
`diagram_description` (e.g. a risk citation, a copied design paragraph) must also go through
[safe-output.md § Rule 5](../../docs/skill-framework/shared/safe-output.md#rule-5-pii-secret-redaction-in-rendered-output)
redaction before being rendered — this skill cites raw proposal/design/diagram content directly when
grounding a finding, so the redact-then-escape-or-fence sequence applies to every quoted excerpt, not
just the short identifier-shaped values.

## Structure (order fixed)

```markdown
# Architecture review — <subject>

**Decision: <Approved | Approved with conditions | Needs rework | Rejected>**

<When not Approved, one line naming which contributing finding(s) set the verdict — never just the bare
state.>
> e.g. `Needs rework — no detection/recovery plan for the payment-writer failure mode; see Failure modes below.`

## Architecture decision

<What is being proposed and why — one paragraph grounded in `proposal_text`/`design_description`.>

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| <risk description> | Scale limits \| Failure modes \| Security \| Operability | Blocking \| Conditional \| Informational | <grounding excerpt or Unknown> |

<"None found" is itself a valid row when no risk exists — never omit the section.>

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| <load/data-volume dimension> | <limit, or Unknown if uncheckable> | <citation from proposal/design, or "Unknown — <what's missing>"> |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| <what fails> | <how it's detected, or Unknown> | <how it recovers, or Unknown> | <grounding excerpt> |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| <security concern> | <boundary crossed, or Unknown if no diagram supplied> | <what's exposed if it fails> | <grounding excerpt> |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| <who runs this / what it costs> | <team or Unknown> | <cost signal or Unknown> | <grounding excerpt> |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| <alternative design> | <stated rationale, or "Unknown — no alternatives stated in proposal_text/design_description"> | — |

## Conditions

<Only when Decision is "Approved with conditions": numbered list of specific conditions that must be
met before/during implementation. Omit this section entirely for any other verdict.>
```

## Rules

- **Every required check appears in the document even when clean or "none found"** — Risks, Scale
  limits, Failure modes, Security, Operability, and Alternatives considered are never silently omitted
  for having nothing to report; a clean check still gets a row (e.g. "None found").
- **The verdict derivation is fixed, precedence `Rejected` > `Needs rework` > `Approved with conditions`
  > `Approved`** (worst-first; full derivation in [workflow/report.md](../workflow/report.md)):
  - `Rejected` — a check finds a fundamental, unmitigated flaw: the design violates a hard constraint
    stated in `proposal_text`, a failure mode causes unrecoverable data loss or a security breach with
    no feasible fix within the proposal's own scope, or the design cannot plausibly meet its own stated
    scale requirement and no alternative path is offered.
  - `Needs rework` — at least one required check surfaces a material, unresolved risk (a scale limit
    inside the proposal's stated growth horizon, a failure mode with no detection/recovery plan, a
    security trust-boundary gap, no named operability owner) that must be addressed before
    implementation proceeds, **or** a required check could not be completed at all because
    `design_description` (or a required optional input the check specifically depends on) was too
    sparse or absent — an evidence gap on a required check is not a proven flaw, but it still blocks a
    clean approval.
  - `Approved with conditions` — the decision is sound overall, but specific, named conditions must be
    met before or during implementation (e.g. a load test before launch, a stated revisit threshold, a
    named monitoring hook) — including a gap confined to an optional input (`diagram_description` or
    `repo_context`) that a follow-up can close without blocking the decision itself.
  - `Approved` — no material risk found in any required check, alternatives were considered and
    justified, and no evidence gaps remain on any required check.
- **An evidence gap is its own explicit state, never silently merged into a pass or a fail.** Any check
  that could not be completed is recorded as `Unknown` in its own table cell (never left blank, never
  marked as if the check passed) and the reason is named ("Unknown — no diagram supplied to verify trust
  boundaries"). A gap on a required check drives the verdict to at least `Needs rework` per the rule
  above; a gap confined to an optional input is instead surfaced as a named condition under `Approved
  with conditions`.
