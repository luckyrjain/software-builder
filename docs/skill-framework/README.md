# Skill Framework — Shared Reference Library

Normative conventions for **pr-review**, **incident-rca**, **k8s-overprovisioning-datadog**, **domain-comprehension**, **squad-map**, **mysql-to-postgres-sql**, and **loop-task-implementer**.
Design spec: [2025-06-30-unified-skill-framework-design.md](../superpowers/specs/2025-06-30-unified-skill-framework-design.md).

`loop-task-implementer` is platform-neutral and host-agent-driven rather than Datadog/GitLab/Jira-MCP-driven,
so `confidence-bands.md` and `phase-glossary.md` don't apply to it — everything else (file anatomy,
workflow frontmatter, escalation, examples depth, smoke/pressure tests, cross-agent discovery) does.

Skills reference these files by relative link from `SETUP.md` or `SKILL.md`. Do not duplicate full tables inline — link here and add skill-specific deltas only.

## Shared files

| File | Purpose |
|------|---------|
| [shared/confidence-bands.md](shared/confidence-bands.md) | HIGH / MEDIUM / LOW / UNKNOWN ↔ 0–1 numeric ↔ pr-review per-finding confidence |
| [shared/cross-skill-escalation.md](shared/cross-skill-escalation.md) | Symmetric 5-skill escalation matrix + reverse handoffs |
| [shared/skill-routing.md](shared/skill-routing.md) | Unified routing table — single source of truth for user intent → skill mapping |
| [shared/prompt-injection.md](shared/prompt-injection.md) | Untrusted external text guard — data for analysis, not instructions |
| [shared/mcp-error-handling.md](shared/mcp-error-handling.md) | MCP failure categories, retry policy, degraded mode patterns, confidence impact |
| [shared/post-action-templates.md](shared/post-action-templates.md) | Jira, Slack, and canvas output patterns after a skill completes |
| [shared/smoke-test-conventions.md](shared/smoke-test-conventions.md) | Post-install/post-edit verification structure |
| [shared/examples-conventions.md](shared/examples-conventions.md) | Required depth and format for each skill's `examples.md` |
| [shared/phase-glossary.md](shared/phase-glossary.md) | Phase name mapping across pr-review, rca, k8s, domain-comprehension, and squad-map pipelines |
| [shared/review-metadata-schema.md](shared/review-metadata-schema.md) | Normative metadata YAML — `review_metadata` (pr-review), `assessment_metadata` (rca, k8s); v2 analytics blocks |
| [shared/claude-code-setup.md](shared/claude-code-setup.md) | Claude Code install paths + MCP config location, mapped from the Cursor equivalents used throughout each skill's `SETUP.md` |

## How skills link here

From a skill root (e.g. `pr-review/SETUP.md`):

```markdown
Framework: [skill-framework README](../docs/skill-framework/README.md)
Confidence: [confidence-bands](../docs/skill-framework/shared/confidence-bands.md)
```

Installed skills symlink to the repo; paths resolve when the agent workspace is the **ai-skills** clone.

## Compliance

A skill is framework-compliant when it passes the checklist in the design spec §4 and `make lint-<skill>` plus `make lint-framework` (repo root).

## Status

| File | Status |
|------|--------|
| confidence-bands.md | Complete |
| cross-skill-escalation.md | Complete |
| mcp-error-handling.md | Complete |
| skill-routing.md | Complete |
| prompt-injection.md | Complete |
| post-action-templates.md | Complete |
| smoke-test-conventions.md | Complete |
| examples-conventions.md | Complete |
| phase-glossary.md | Complete |
| review-metadata-schema.md | Complete — v2 pr-review + assessment_metadata (rca, k8s) + repository_health dimensions |
| claude-code-setup.md | Complete |

## Deferred (P3 roadmap)

| Item | Status | Notes |
|------|--------|-------|
| **Approach B — shared deterministic-artifact framework** | Deferred | Cross-skill validator library for manifest/graph/evidence — see [2026-07-02-skills-roadmap-design.md](../superpowers/specs/2026-07-02-skills-roadmap-design.md). Per-skill validators remain canonical until a third consumer justifies extraction. |
