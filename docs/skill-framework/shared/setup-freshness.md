# SETUP.md freshness contract

Every skill's `SETUP.md` documents **who maintains integration instructions** and **when they were last
verified** against real external services (MCP servers, CLIs, webhooks).

## Required section

Each `*/SETUP.md` must include a `## Freshness` table immediately after the document title:

```markdown
## Freshness

| Field | Value |
|-------|-------|
| **Owner** | software-builder maintainers |
| **Last reviewed** | YYYY-MM-DD |
| **Review cadence** | Quarterly — or when pinned MCP package versions change |
| **External services** | <comma-separated list, or `None (local tooling only)`> |
```

Normative values for **External services** are listed in
[`scripts/registry/setup_freshness.yaml`](../../../scripts/registry/setup_freshness.yaml) per skill.

## When to bump **Last reviewed**

- After changing pinned MCP package versions in any `SETUP.md`
- After verifying install steps against a real GitLab/Datadog/Kubernetes/Jira integration
- During quarterly hygiene — even if no content changed, confirm pins still resolve

## CI enforcement

`make lint-framework` runs `python3 scripts/validate_setup_freshness.py` — missing sections, stale dates
(>120 days without review), or mismatched external-services text fail lint.
