# Depth selection

Select depth automatically. Word limits are **ceilings, not targets**.

Begin PRD and Review output with:

```
Depth: Lite | Standard | Rigorous — <brief reason>
```

## Lite

**Use for:** clearly isolated, low-risk, reversible changes with few actors and minimal integrations.

**Target PRD body:** ≤1,500 words.

**Prefer sections:** Overview; Problem; Goals / Non-Goals; MVP; Functional Requirements; Key Failure /
Edge Cases; Acceptance Criteria; Risks; Assumptions (short in-body subsection when needed); Build
Readiness.

Use cases may fold into MVP or requirements. Metrics may fold into Goals. Avoid formal traceability,
assumption tables, extensive NFRs, and review appendices unless materially triggered.

For Lite, include assumptions as a short subsection inside the PRD body. Do not create a separate
Assumptions appendix unless ≥3 consequential assumptions or a Risky assumption affects Build Readiness.

## Standard

**Default** for meaningful product work.

**Use for:** customer-facing features; multiple actors; meaningful state; integrations; business rules;
cross-team delivery; moderate operational impact.

**Target PRD body:** ≤5,000 words.

If uncertain between Lite and Standard, choose **Standard**.

## Rigorous

**Use when** material risk involves: money movement; lending; payments; billing; sensitive personal
data; regulated workflows; security-critical behavior; fraud; distributed state; asynchronous
multi-system workflows; irreversible actions; significant migration; high availability; major financial
or operational exposure.

**Target PRD body:** ≤12,000 words.

If uncertain between Standard and Rigorous, choose **Rigorous** when plausible failure could cause:
financial loss; data corruption/loss; security incident; regulatory exposure; irreversible user harm;
material operational disruption.

Do **not** choose Rigorous merely because the system is technically interesting.

## Depth hint override

Honor `depth_hint` from inputs only when the user explicitly requests a depth level.
