# dependency-upgrade-review

Review a proposed dependency or framework version bump for breaking changes, CVEs affecting the current
or target version, API differences the codebase's callers must absorb, transitive dependency impact, and
rollout risk — then deliver a single go/no-go verdict.

## When to use

- "Review this dependency upgrade — breaking changes, CVEs, rollout risk"
- "Should we bump `<library>` from `<v1>` to `<v2>`?"
- "What breaks if we upgrade `<framework>` `<v1>`→`<v2>`?"
- A transitive dependency conflict or new transitive CVE check for a planned bump

## Install

```bash
make install-dependency-upgrade-review
```

Details: [SETUP.md](SETUP.md).

## Pipeline

```
Inputs → Analyze → Report
```

Agent instructions: [SKILL.md](SKILL.md).
