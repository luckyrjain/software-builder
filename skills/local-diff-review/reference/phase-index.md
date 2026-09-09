# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|-----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `diff_scope`, `spec_context` |
| **Standards** | [workflow/standards.md](../workflow/standards.md) | `standards_findings` |
| **Spec** | [workflow/spec.md](../workflow/spec.md) | `spec_findings` |
| **Report** | [workflow/report.md](../workflow/report.md) | `LOCAL_DIFF_REVIEW.md`, `local_diff_review` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|-------------------|----------|
| Diff against a fixed point with Standards/Spec review | Inputs → Standards → Spec → Report |
| No `diff_scope` named | Inputs HARD STOP — ask; no Standards phase |
| `spec_context` supplied | Spec evaluates the diff against it; findings table populated |
| No `spec_context` supplied | Spec marked not applicable with a stated reason; no fabricated findings |
| A Standards finding is security-sensitive | Report offers `security-review` escalation |
| Caller wants this diff reviewed once it's a real PR/MR | Report offers `pr-review` escalation |
| Scope becomes a full existing-codebase audit or architecture-wide verdict | Offer the one applicable escalation; do not invoke it |
