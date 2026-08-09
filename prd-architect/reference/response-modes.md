# Response modes

Infer mode from the user's request. When ambiguous, prefer the mode that avoids unnecessary full-PRD work
when the user is clearly evaluating an idea.

## PRD Mode

**Use when:** the user wants an idea, proposal, or workflow converted into a PRD.

**Output:** Final PRD + Build Readiness.

Begin with: `Depth: <depth> — <brief reason>`

## Validation Mode

**Use when** the user primarily asks:

- Should we build this?
- Is this worth building?
- Challenge this idea
- What is wrong with this idea?
- Build vs buy?
- What alternatives exist?

**Use when** evaluating an idea **without** an authoritative existing PRD.

**Output:**

1. Problem Assessment
2. Premise Verdict
3. Key Assumptions
4. Alternatives
5. Material Risks
6. Recommendation
7. Evidence Needed Next

**Do not** produce a full PRD unless requested.

If the user supplies an existing PRD and asks what the gaps are, use **Review Mode** instead.

Begin with: `Mode: Validation — <brief reason>`

## Review Mode

**Use when** an existing PRD or product specification is supplied and the user asks to: review;
challenge; improve; find gaps; assess readiness; complete it.

**Default:** produce a **repaired PRD** rather than merely a critique.

**Output:** Repaired PRD + Material Changes + Build Readiness.

If the user explicitly requests **critique only** (`critique_only: true` or "review only, don't rewrite"):
output findings, gap analysis, and readiness — **do not** rewrite the PRD.

Begin with: `Depth: <depth> — <brief reason>`

Preserve sound terminology and requirements from the source PRD.
