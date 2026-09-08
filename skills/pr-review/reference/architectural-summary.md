# Architectural Summary (Phase 5)

Load when rendering the end-of-review **Architectural summary** (Phase 5 and summary note). Informed by
§10 readability, §16 Architecture Lens findings (if any), and holistic judgment — not a second pass over
every line.

## When to include

- **Include** for MRs with production logic, structural change, API/schema, or §16 triggered.
- **Omit** for mechanical-only diffs (lockfile, generated, typo-in-comment) — no section needed.
- **Brief** for tiny bugfixes (<10 lines, single file): one-row table is enough.

## Rating scale (use exactly these labels)

| Rating | Meaning |
|--------|---------|
| **Excellent** | Exemplar design — improves the codebase; others should copy this pattern |
| **Good** | Solid structure; at most minor/arch findings already listed |
| **Acceptable** | Ships safely; some debt or smell worth tracking but not blocking |
| **Needs Work** | Material structural issues — address soon (often aligns with arch Medium findings) |
| **Major Concerns** | Serious design problems — rethink before merge (aligns with arch High / coupling / leakage) |

## Dimensions

| Dimension | Assess |
|-----------|--------|
| **Overall design** | Holistic judgment — boundaries, cohesion, fit with repo patterns. **Not** the max of sub-ratings; synthesize them + findings. |
| **Maintainability** | Ease of future change — coupling, duplication, clear modules, test seams |
| **Complexity** | Cognitive load — nesting, indirection, accidental vs essential complexity |
| **Readability** | Names, structure, follow local conventions; can a new teammate follow this? |
| **Future cost** | Debt compounding — flags without sunset, tight coupling, missing abstractions, migration/rollback risk |

**Overall design** should be **Major Concerns** if any dimension is **Major Concerns** or open arch **High**
findings remain. **Excellent** only when no material arch findings and sub-ratings are Good or better.

## Balanced assessment

When the MR includes structural improvements, **≥1 dimension Notes cell must state a positive** —
do not list concerns only. Examples:

- Transactional boundary migration — cleaner unit-of-work
- Consistent event/status model across PDN flow
- Cleaner domain separation (scheduler vs notification vs gateway)
- Feature-flag strategy for rollout

Mirror themes from `reference/positive-observations.md` at **design** level (not duplicate bullet list).

If no structural positives exist, say so briefly in **Overall design** Notes — do not invent praise.

## Output format

```markdown
### Architectural summary

| Dimension | Rating | Notes |
|-----------|--------|-------|
| **Overall design** | Good | … |
| Maintainability | Acceptable | … |
| Complexity | Good | … |
| Readability | Good | … |
| Future cost | Needs Work | … |
```

One short **Notes** cell per row (≤1 sentence) — cite evidence or point to arch findings; no essay.
