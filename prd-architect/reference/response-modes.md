# Response modes

Infer mode from the user's request. When ambiguous, prefer the mode that avoids unnecessary full-PRD work
when the user is clearly evaluating an idea.

## PRD Mode

**Use when:** the user wants an idea, proposal, or workflow converted into a PRD.

**Output (normal path):** Final PRD + Build Readiness.

Begin with: `Depth: <depth> — <brief reason>`

### Fundamentally flawed premise (PRD Mode exception)

If Validate assigns **Fundamentally flawed**, **stop normal PRD generation**. Emit a **Validation-style**
7-section response plus:

**Build Readiness: Not Ready**

Do **not** produce a full PRD unless the user **explicitly** requested a PRD despite the flawed premise
(e.g., "write the PRD anyway" / "document the proposal even if flawed").

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

### Routing (check first)

| User intent | Output |
|---|---|
| **Critique only** — `critique_only: true`, "review only", "don't rewrite", "findings only" | Findings + Gap Analysis + Build Readiness. **No** repaired PRD body. |
| **Improve / fix / make implementation-ready** (default) | Repaired PRD + Material Changes + Build Readiness |

Default when intent is ambiguous: ask once whether the user wants a **repaired PRD** or **critique only**.

Begin with: `Depth: <depth> — <brief reason>` (both sub-paths).

Preserve sound terminology and requirements from the source PRD.
