# Positive observations (Phase 5)

Load when rendering Phase 5 closeout for non-mechanical MRs. Surfaces genuine strengths so reviews
stay balanced when blockers dominate.

## When to include

- **Include** when **≥2** concrete positives exist (architecture, tests, security hygiene, coverage).
- **Omit** when none apply — do not pad with generic praise.

## What counts

| Category | Examples |
|----------|----------|
| Design | Structured status model, clear module boundaries, consolidated payment flow |
| Safety | Idempotency keys, duplicate detection, defensive validation on hot path |
| Security hygiene | Snyk/advisory scan clean, no new CVEs in manifest diff |
| Testing | Regression test for linked ticket, negative cases on changed path |
| Process | Full review coverage (N/N files), CI green on head, linked Jira with met AC |

Do **not** duplicate **praise** inline comments — positives here are summary-level themes.

## Output format

After **Engineering improvements**, before **Production risk**:

```markdown
### Positive observations

- ✓ Structured status model — enum covers all PDN states
- ✓ Duplicate detection on notification retry path
- ✓ Consolidated payment flow reduces handler duplication
- ✓ Snyk clean — no new dependency advisories in diff
- ✓ Full review coverage (24/24 changed files)
```

Cap at **6 bullets**. Each bullet: one line, specific to this MR. **Praise** inline comments (`praise:`)
are separate — max **2** per review per `reference/severity-rubric.md`; summary positives here are
themes, not duplicates of inline praise.

## Payments persona

When payments domain active, prefer positives on: idempotency, money-type correctness (where
present), audit logging, webhook hardening, test coverage on notification paths.

Cross-ref: `reference/architectural-summary.md` (design praise may appear in both — keep positives
action-oriented, arch summary judgment-oriented).
