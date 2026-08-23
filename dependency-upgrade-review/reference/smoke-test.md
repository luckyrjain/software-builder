# Smoke test — expected minimal output

Run after install and after any skill edit. Use a real dependency bump with a known changelog (e.g. a
library with a documented major-version migration guide) and a small manifest/lockfile excerpt pinning at
least one transitive package, so both the changelog-backed checks and the transitive-dependency check
exercise real evidence, not just the missing-input fallback.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `Review upgrading <dependency_name> from <current_version> to <target_version>` with `changelog_text`
> and a `manifest_excerpt` pinning one transitive dependency attached.

## A correct minimal output contains

1. **Scope announcement** — dependency name, current version, target version, and which optional inputs
   (`changelog_text`, `manifest_excerpt`) were supplied, before analysis starts.
2. **Core findings** — Breaking changes, CVEs, API differences, and Transitive dependencies tables, each
   populated or carrying an explicit "None found" row — never an empty or omitted section.
3. **Rollout risk** — one paragraph naming staged-rollout feasibility and reversibility.
4. **`DEPENDENCY_UPGRADE_REPORT.md`** — per [report-format.md](report-format.md), with the bold verdict
   line first.
5. **Confirmation / next step** — a cross-skill handoff offer if a CVE looks exploitable in this
   codebase's usage, or if the upgrade is part of a larger MR under review.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| No `changelog_text` supplied | Breaking-changes and API-differences checks recorded as "Unknown — no changelog supplied," verdict pulled to `Blocked — insufficient info` unless a proven blocker is found elsewhere |
| No `manifest_excerpt` supplied | Transitive-dependencies check recorded as "Unknown — no manifest/lockfile excerpt supplied," same verdict-pull rule applies |
| `dependency_name`, `current_version`, or `target_version` missing | Inputs phase HARD STOPs and asks — no Analyze or Report phase runs |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
