# Setup — change-impact-analyzer

## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | 2026-08-24 |
| **Review cadence** | Quarterly — or when pinned SCM/host capability contracts change |
| **External services** | None — reads supplied design/change content and optional repository or exact-head SCM evidence only |

See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) for the shared contract.

This skill is ambiently invocable and requires no package-specific installation. It uses read-only
repository access when available and optional exact-head SCM change retrieval for remote PR/MR
analysis.

Shared conventions: [skill framework](../docs/skill-framework/README.md),
[setup freshness](../docs/skill-framework/shared/setup-freshness.md),
[routing](../docs/skill-framework/shared/skill-routing.md), and
[cross-skill escalation](../docs/skill-framework/shared/cross-skill-escalation.md).

Required capability: `host.report.write`. Optional capabilities are `host.repository.read` and
`host.scm.change.read`; absence produces explicit degraded coverage.
