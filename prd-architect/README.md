# prd-architect

Turn rough product ideas, feature proposals, workflows, and existing PRDs into **validated,
implementation-ready** Product Requirements Documents — or a concise **build/no-build** assessment when
that is what you need first.

Unlike a template filler, PRD Architect **challenges the premise**, considers alternatives, models
realistic failure, runs adversarial review, repairs validated gaps, and assigns **Build Readiness**
before engineering should start.

## When to use

- Write or refine a PRD from an idea or proposal
- "Should we build this?" / challenge an idea / build vs buy
- Review an existing PRD for gaps, contradictions, and implementation readiness
- Define MVP scope, requirements, acceptance criteria, and rollout for a new feature

Full routing table: [SKILL.md](SKILL.md#when-to-use-not-to-use).

## Modes

| Mode | Output |
|------|--------|
| **PRD** | Final PRD + Build Readiness |
| **Validation** | Problem assessment, alternatives, recommendation — no full PRD unless asked |
| **Review** | Repaired PRD + material changes + Build Readiness |

## Depth

Automatic: **Lite** (small, low-risk) · **Standard** (default product work) · **Rigorous**
(payments, PII, regulated, irreversible, high exposure).

## Install

```bash
make install-prd-architect
```

Details: [SETUP.md](SETUP.md).

## Pipeline

```
Classify → Validate → Specify → Break → Repair → Gate
```

Agent instructions: [SKILL.md](SKILL.md).

## Eval suite

Regression tests for maintainers: [prd-architect.eval.md](prd-architect.eval.md).
