# architecture-review

**Architecture decision review** for a PRD/proposal and a proposed design, before implementation begins.
Evaluates the decision itself (what + why), scale limits, failure modes, security posture at the
architecture level, operability, and the alternatives considered — closing on a validated verdict:
Approved, Approved with conditions, Needs rework, or Rejected.

An optional architecture diagram description and read-only repository context sharpen the review
(trust-boundary cross-checks, current-state grounding) but are not required to run it.

## When to use

- "Should we build it this way?" with a PRD/proposal and a design in hand
- Pre-implementation sign-off on risks, scale limits, and failure modes before work starts
- Weighing a proposed design against the alternatives it claims to have considered
- Checking an architecture's security posture at the trust-boundary level (not a full security audit)
- Deciding whether an approved decision is ready to hand to implementation-level design or straight to
  build

## Install

```bash
cd software-builder
make install-architecture-review
```

See [SETUP.md](SETUP.md) for Claude Code / Kiro-in-repo variants and the smoke test.

## Pipeline

`Inputs → Analyze → Report`

Inputs resolves `proposal_text`/`design_description` (HARD STOP if either is absent) plus optional
`diagram_description`/`repo_context`. Analyze runs the six checks — decision rationale, scale limits,
failure modes, security, operability, alternatives considered — recording any evidence gap explicitly.
Report derives the verdict by fixed worst-first precedence and builds `ARCHITECTURE_REVIEW_REPORT.md`.

Agent instructions: [SKILL.md](SKILL.md).
