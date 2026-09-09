# Depth selection

Select depth automatically. Word limits are **ceilings, not targets** — prefer concise prose over
hitting a budget.

## Output headers

| Mode | Required header |
|------|-----------------|
| **PRD** | `Depth: Lite \| Standard \| Rigorous — <brief reason>` |
| **Review** | Same as PRD |
| **Validation** | `Mode: Validation — <brief reason>` only — **do not** emit a Depth line |

Depth still guides internal analysis for Validation (e.g., Rigorous for payment ideas) but stays out of
the user-visible header.

## Lite

**Use for:** clearly isolated, low-risk, reversible changes with few actors and minimal integrations.

**Target PRD body:** ≤1,500 words (~1 page; roughly 6–8 substantive sections plus compact mandatory
traceability/readiness material).

**Prefer sections:** Overview; Problem; Goals / Non-Goals; MVP; Success Metrics; Functional Requirements;
Key Failure / Edge Cases; Acceptance Criteria; Requirements Traceability; Risks; Build Readiness.
Consequential assumptions add a compact Assumption Register/subsection. Engineering sections remain
trigger-driven.

Use cases may fold into MVP or requirements. Keep metrics and traceability concise rather than omitting
them: material metrics still require baseline + target + timeframe + measurement source, and material
functional requirements still require `FR-* -> AC-* -> TR-*`. Avoid extensive NFRs and review appendices
unless materially triggered.

For Lite, consequential assumptions may be a short in-body register. Prefer a separate table when ≥3
consequential assumptions or a Risky assumption affects Build Readiness.

## Standard

**Default** for meaningful product work.

**Use for:** customer-facing features; multiple actors; meaningful state; integrations; business rules;
cross-team delivery; moderate operational impact.

**Target PRD body:** ≤5,000 words (~3–5 pages of requirements-focused content).

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

## Proportionate length check (Gate)

At Gate, if the PRD body is obviously over budget (e.g., Lite with long appendix chains, or Standard
with Rigorous-only sections untriggered), cut or demote non-material content before emitting. Never meet a
word budget by dropping a mandatory metric, material traceability edge, or triggered engineering-safety
section.
