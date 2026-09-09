---
workflow_version: 1.0
phase: standards
produces:
  - standards_findings
consumes:
  - diff_scope
---

# Standards — evaluate the diff against this repo's own conventions

Find every governing convention document: the user-level and repo-root `CLAUDE.md`/`AGENTS.md`, any
`CLAUDE.md`/`CLAUDE.local.md` in a directory that is an ancestor of a changed file, `CONTRIBUTING.md`,
and linter/formatter configuration actually enforced in CI. Read each one that exists.

For every finding, quote the exact rule and the exact line of the diff that breaks it — no style
preferences, no "spirit of the doc" inferences. If no governing document applies to a changed file,
record that explicitly rather than inventing a rule.

Classify each finding's severity (blocking / worth fixing / minor) and cite the rule source
(`file:line` of the convention doc) alongside the diff line it applies to.

If a finding is security-sensitive (secrets, injection, auth/authz, unsafe deserialization), mark it
`security_sensitive: true` so the Report phase surfaces the `security-review` escalation.
