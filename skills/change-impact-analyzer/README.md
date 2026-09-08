# Change Impact Analyzer

Read-only, bounded analysis of a proposed design or exact PR/MR change. The package identifies
changed classes, impacted repositories/services/contracts/data/dependencies, evidence gaps, tests,
operational impacts, and specialist-review triggers.

Start with [SKILL.md](SKILL.md), then follow the [phase index](reference/phase-index.md).

## Contract

The canonical output is `change_impact_report` v1. Coverage is `COMPLETE`, `PARTIAL`, or `UNKNOWN`;
missing repository or exact SCM evidence is recorded, never guessed. Generic correctness review is
owned by `pr-review`; deployment blast radius and rollback risk are owned by `deployment-risk-review`.
