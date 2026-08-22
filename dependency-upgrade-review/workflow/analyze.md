---
workflow_version: 1.0
phase: analyze
produces:
  - breaking_changes
  - cve_findings
  - api_differences
  - transitive_impact
  - rollout_risk
consumes:
  - dependency_name
  - current_version
  - target_version
  - changelog_text
  - manifest_excerpt
---

# Analyze — evaluate the upgrade across five checks

Run all five checks below over `dependency_name`, `current_version`, `target_version`, and the optional
`changelog_text`/`manifest_excerpt`. Every check that cannot be completed is recorded as an explicit gap
here, not silently skipped — Report turns an unrecorded gap into a fabricated "None found," which is
exactly what the Unknown state exists to prevent.

## 1. Breaking changes

Diff behavior between `current_version` and `target_version`: removed/renamed APIs, changed defaults,
changed return types or error behavior, dropped support (runtime version, config format, deprecated
flag). Prefer `changelog_text` when supplied — cite the specific entry. Without it, reason from the
version delta alone (a major-version bump under semver implies breaking changes are likely even absent
changelog text; a patch bump implies they are unlikely) and record the check as an Unknown gap rather
than asserting "no breaking changes" from silence.

## 2. CVEs

Identify CVEs affecting `current_version`, `target_version`, or both. For each: which version(s) it
affects, the version it's fixed in (if known), and severity. A CVE affecting only `current_version` and
already fixed in `target_version` is not a blocker — it's a reason to upgrade, and is recorded as such. A
CVE affecting `target_version` with no fix available yet is a proven blocker. If advisory data isn't
reachable, record the gap explicitly rather than reporting "no CVEs found."

## 3. API differences

For every breaking change identified in check 1 that has a concrete before/after API shape, record it:
symbol/signature before, symbol/signature after, and the caller-side code change required. This is the
actionable subset of check 1 — a breaking change with no caller-visible API shape (e.g. a changed
internal default) still belongs in check 1 but may have nothing to add here.

## 4. Transitive dependency impact

Using `manifest_excerpt` when supplied: does the version bump force a transitive dependency to a new
version or range, does that new pin conflict with another declared dependency's constraint, and does it
introduce a new transitive CVE that wasn't present before. Without `manifest_excerpt`, this check cannot
be run against the caller's actual pins — record it as an explicit Unknown gap, do not assume no
conflict.

## 5. Rollout risk

Assess whether the upgrade can be staged (feature flag, canary, phased rollout across services) and
whether it's reversible (a clean downgrade path exists, or the change is one-way — e.g. a data/schema
migration bundled with the dependency). State the blast radius if the upgrade turns out to be wrong and
can't be trivially reversed.

Every gap recorded in checks 1–5 feeds Report's `Blocked — insufficient info` handling — an evidence gap
is never silently folded into a clean pass or a fail.
