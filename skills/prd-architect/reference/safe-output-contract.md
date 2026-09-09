# Safe output contract

Gate renders untrusted excerpts through the deterministic reference implementation in
[scripts/prd_safe_output.py](../scripts/prd_safe_output.py). The normalizer redacts plausible
secrets, email addresses, and phone numbers; neutralizes Markdown headings, tables, blockquotes,
lists, code fences, links, images, autolinks, reference links, inline emphasis, strong emphasis, and
strikethrough; and collapses source newlines into one inert paragraph. Gate then appends
exactly one skill-authored `## Build Readiness` section after all untrusted content.

The implementation is an executable contract for output-boundary behavior and regression tests. It
does not replace Gate's semantic review or readiness decision.
