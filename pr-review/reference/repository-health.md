# Repository health dimensions

Normative rubric for `repository_health.dimensions` in the Phase 5 `review_metadata` YAML footer.
Shared schema: [review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md) §6.

## When to score

Emit dimension scores only when the agent has **observable repo context** (clone path, CI API, `make lint`
run, or user-provided repo state). Do not invent scores from MR diff alone.

| Situation | `repository_health` emission |
|-----------|------------------------------|
| No repo context | `{ schema_version: 2 }` only |
| Repo cloned / CI queried | Full `dimensions` object |
| Dimension not applicable | `null` for that key (e.g. `observability` on a CLI tool) |

Prose mirror (optional): **Repository maturity (informational)** line in Engineering improvements when
that section is non-empty — see [review-metrics.md](review-metrics.md) §Repository maturity.

## Dimensions (1–10 scale)

| Dimension | 10 | 7 | 5 | 0 / null |
|-----------|----|---|----|----------|
| **CI** | Green pipeline on head | CI configured, not run on head | Partial / flaky CI | No CI config |
| **Documentation** | README + runbooks + skill refs aligned | Minor drift | Missing key docs | No docs |
| **Validation** | `make lint` + tests pass on head | Lint configured, tests not run | Lint failing | No lint/tests |
| **Automation** | Hooks + anchor lint + pressure tests | Partial automation | Manual-only workflows | None |
| **Observability** | APM + dashboards + SLOs | Partial telemetry | Minimal metrics | **null** when N/A |

### CI

- Query pipeline status on MR head SHA when GitLab/Jenkins MCP available.
- Score 8 when CI exists but was not executed on head (common on draft MRs).

### Documentation

- Check README, CHANGELOG, runbooks/, and skill `SETUP.md` presence.
- Penalize when Engineering improvements lists doc gaps.

### Validation

- Prefer observed `make lint` exit code when repo is cloned.
- Map pr-review's historical "Lint" dimension here (renamed in v2 schema).

### Automation

- Pre-commit hooks, Makefile lint targets, `reference/pressure-tests.md` rows present.
- Partial when only Makefile exists without hooks.

### Observability

- Score when service repo has Datadog/monitors, OpenTelemetry, or SLO definitions.
- Use `null` for libraries, infra-only repos, or when not assessable from MR scope.

## Footer shape

```yaml
repository_health:
  schema_version: 2
  repo: payments-service
  dimensions:
    ci: 8
    documentation: 9
    validation: 10
    automation: 7
    observability: null
  composite: 8.5
```

`composite` = mean of non-null dimension scores, one decimal. Omit when all dimensions null.

## Derivation workflow (Phase 5)

1. If Engineering improvements section is **empty** and no repo was inspected → stub only.
2. If Engineering improvements is **non-empty** → derive scores from listed items + observed state.
3. Mirror optional prose line: `CI: 8/10 | Documentation: 9/10 | …`
4. Never inflate scores when CI/lint was not executed — use 8/5 per table above.
