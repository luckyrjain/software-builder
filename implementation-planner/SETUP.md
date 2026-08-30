# Setup — implementation-planner

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-26 |
| **Review cadence** | Quarterly — or when plan schema, loop-task, or repository capability contracts change |
| **External services** | None — reads supplied design/review artifacts and optional repository evidence only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

This skill is ambiently invocable and requires no package-specific installation. It uses read-only
repository access to ground target paths, verification, and conservative execution-size estimates.

Shared conventions: [skill framework](../docs/skill-framework/README.md),
[setup freshness](../docs/skill-framework/shared/setup-freshness.md),
[routing](../docs/skill-framework/shared/skill-routing.md), and
[cross-skill escalation](../docs/skill-framework/shared/cross-skill-escalation.md).

Required capabilities: `host.report.write` and `host.repository.read`.
