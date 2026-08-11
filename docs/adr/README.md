# Architecture Decision Records

Lightweight ADRs for platform-level choices in **software-builder**. Each record captures context, decision, and consequences so future changes start from documented intent rather than archaeology.

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-skills-registry.md) | Canonical `skills.yaml` registry | Accepted |
| [0002](0002-self-contained-skill-packages.md) | Self-contained skill install packages | Accepted |
| [0003](0003-behavioral-evals-tiers.md) | Tiered behavioral eval harness | Accepted |
| [0004](0004-live-eval-harness.md) | Mock-tool execution harness, kept out of CI | Accepted |

When a platform decision materially changes install, registry, or eval behavior, add a new numbered ADR and link it from [CHANGELOG.md](../../CHANGELOG.md).
