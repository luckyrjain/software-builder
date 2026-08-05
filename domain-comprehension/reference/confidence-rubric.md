# Confidence rubric (domain comprehension)

**Extends** [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md).

## Principle

**Prefer UNKNOWN over speculation.** Every architectural conclusion must be traceable to executable
code or runtime evidence. Accuracy beats fluency.

Precedence on conflict: [evidence-precedence.md](evidence-precedence.md).

## Categorical bands (code analysis)

| Level | Criteria |
|-------|----------|
| **HIGH** | Full path traced in executable code, schema, test, or runtime trace |
| **MEDIUM** | 2+ independent code signals but path incomplete; or verified comment + schema |
| **LOW** | Single non-executable reference (comment, config key, unused enum) |
| **UNKNOWN** | No qualifying evidence, or hop leaves workspace |

## Evidence tier (what may support each band)

| Tier | Sources | Max confidence |
|------|---------|----------------|
| **Executable** | Source code, migrations, tests, OpenAPI/proto committed, runtime traces (Datadog), prod config in repo | HIGH |
| **Structural** | Knowledge graph edges verified in source; 2+ repos agree on contract | MEDIUM |
| **Annotated** | Code comments, committed ADRs with matching code, design docs in repo | MEDIUM |
| **Non-executable** | README, wiki, Confluence, Jira, issue threads, package name | LOW |
| **None** | Inference only | UNKNOWN |

### Forbidden HIGH from

- README, wiki, Confluence, ADR, architecture deck — unless **verified** in executable code in same engagement
- Single log line, TODO, package name, graph edge without source check
- Datadog edge without service name alias resolution

## Section confidence propagation

```
Section confidence = minimum(confidence of all evidence blocks in that section)
```

Record at end of each major `EXEC_SUMMARY.md` / `{map_file}` section:

```
Section confidence: MEDIUM (weakest: Q3 source of truth — single enum in BFF)
```

If one repo in a section is UNKNOWN, whole section caps at UNKNOWN unless split into subsections.

## Overall confidence (document level)

```
Overall confidence = minimum(
  five_questions.q1..q5.confidence,
  weakest major section confidence,
  overall_confidence in manifest.yaml
)
```

Display in `EXEC_SUMMARY.md` § Overall confidence:

| Question | Status | Confidence |
|----------|--------|------------|
| Q1 | … | HIGH |
| Q2 | … | MEDIUM |
| … | | |

**Overall:** MEDIUM *(weakest: Q3)*

Engineering leaders read this block first in P5.

## Evidence rules

1. **Schema beats DTO** — migration or CHECK constraint beats status string in one service
2. **Producer beats consumer** — topic/table author beats reader assumption
3. **Runtime confirms but does not replace** — P2b `CONFIRMED` raises hop confidence; `RUNTIME_ONLY` does not fix missing code
4. **Cross-repo claims** — HTTP client, shared migration, or queue config edge

## Display

```
Evidence:   ...
Conclusion: ...
Confidence: HIGH | MEDIUM | LOW | UNKNOWN
```

Never write the conclusion before the evidence.
