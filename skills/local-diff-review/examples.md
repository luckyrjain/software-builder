# Examples — local-diff-review

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `local-diff-review` ambiently whenever a diff against a fixed point (commit, branch, tag, or
merge-base) needs Standards and Spec review before becoming a PR/MR. It is read-only and report-only:
inspect the diff, emit findings, and never write source, tests, configuration, or post a comment.

| # | Caller sends | Resolves to | Notes |
|---|-----------------|---------------|-------|
| 1 | "Review my branch against main — does it match the naming convention in CONTRIBUTING.md?" | Inputs → Standards → Spec → Report: Standards findings for naming violations | Happy path |
| 2 | "Check this diff against the ticket: we need to add retry logic to the payment service and update the docs." | Inputs → Standards → Spec → Report: Spec findings for each ticket requirement | Spec path |
| 3 | "Diff since main, but I have no issue text yet — just check conventions." | Inputs → Standards → Spec → Report: Standards findings; Spec marked "not applicable" | No spec path |
| 4 | "Review my uncommitted changes." | HARD STOP — ask for a `diff_scope` (commit, branch, tag, or merge-base) | Boundary rule |
| 5 | "I found a potential security issue in this diff — should I be worried?" | Inputs → Standards → Spec → Report: if a Standards finding is marked security-sensitive, offers `security-review` | Escalation |
| 6 | "Review my PR #42 to see if it matches the ticket." | Wrong scope — this diff is already a live PR/MR; use `pr-review` instead | Wrong-skill row |
| 7 | "This diff has a security-sensitive Standards finding." | Report offers `security-review` escalation; caller decides whether to hand off | Escalation |
| 8 | "Audit the entire codebase against our conventions — we've drifted." | Wrong scope — offer `codebase-architecture-review` for a full audit | Wrong-skill row |

## Example: Standards violation surfaces naming conflict

**Evidence:** The diff changes a file `old_handler.py` to `newHandler.py`. `CONTRIBUTING.md` requires
snake_case for Python filenames. The current branch breaks this rule.

**Result:**

```
## Standards findings

| Severity | Finding | Rule source | Diff location |
|----------|---------|--------------|-----------------|
| blocking | Filename violates snake_case convention for Python files | `CONTRIBUTING.md:42` | `file rename: old_handler.py → newHandler.py` |
```

A violation is named with a concrete rule and diff location — no style preferences, only documented
conventions.

## Example: Spec requirements evaluated against diff

**Evidence:** The ticket states "Add retry logic to payment service with exponential backoff." The diff
shows the retry logic added but no backoff implementation. Tests are added for the retry mechanism.

**Result:**

```
## Spec findings

| Requirement | Satisfied by | Contradicted by | Status |
|-------------|---------------|-------------------|--------|
| Add retry logic to payment service | `payment_service.py:L45-60` | none | satisfied |
| Use exponential backoff | none | `payment_service.py:L55` (uses fixed delay) | contradicted |
| Add tests | `test_payment_service.py:L1-30` | none | satisfied |
```

Each requirement is evaluated separately; one can be satisfied while another is contradicted.

## Example: No spec_context, Spec marked not applicable

**Evidence:** The caller asks for Standards review of a diff against `main` but provides no issue text.

**Result:**

```
## Spec findings

Not applicable — no spec_context given.
```

Silence on spec_context does not infer an implicit spec; it explicitly states "not applicable."

## Degraded path: Diff resolves but has no violations

**Evidence:** The diff is a small bug fix that follows all documented conventions. No issue text was
supplied.

**Result:**

```
## Standards findings

No Standards findings.

## Spec findings

Not applicable — no spec_context given.

## Recommendation

This diff adheres to the documented conventions. No Standards violations found. Spec findings are not
applicable — no issue text was supplied for comparison.
```

Both axes proceed normally; missing findings or missing spec_context are stated explicitly.

## Example: Security-sensitive finding offers escalation

**Evidence:** The diff adds a hardcoded API key in a configuration file. This violates a security
standard documented in `CLAUDE.md`.

**Result:**

The Standards finding is marked `security_sensitive: true`. The Report section offers:

```
**Escalation offered:** This diff contains a security-sensitive Standards finding (hardcoded API key).
Consider `/security-review` for a full security audit.
```

The caller decides whether to pursue the escalation; it is never invoked automatically.

## Example: Caller asks for a PR comment or PR review

**Evidence:** The caller says "Post this review as a PR comment" or "Review my PR #42."

**Result:** Rejected — `local-diff-review` is report-only. The findings are emitted in
`LOCAL_DIFF_REVIEW.md` / `local_diff_review`; the report is never posted anywhere. For a live PR/MR,
the caller uses `pr-review` instead.
