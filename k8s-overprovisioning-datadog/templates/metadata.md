## Metadata

**Assessment Metadata appendix only** — hashes and fingerprint not for the Human Report.

| Field | Value |
|-------|-------|
| Generated | `<ISO8601>` |
| Service | `<name>` |
| Scope | `<tags>` |
| Window | utilization `7d`; cost `30d` |
| Metrics queried | N |
| Missing metrics | N — `<OBS_* list>` |
| Datadog org | `<site>` |
| Skill version | v3.0 |
| Schema version | 2 |
| Threshold version | 2026-06 |
| Analysis duration | `<seconds>` |

### AssessmentFingerprint

```text
service: <name>
window: 7d
threshold_version: 2026-06
threshold_hash: sha256:<hex of thresholds.md>
manifest_hash: sha256:<hex>
metric_query_hash: sha256:<hex>
    schema_version: 3
    skill_version: v3.0
```

Compute `threshold_hash` from [thresholds.md](../thresholds.md) file bytes during COLLECT.

### DecisionHistory

*Omit if no prior assessment.*

```text
Previous: KEEP_CONFIGURATION
Current: KEEP_CONFIGURATION
Changed: No
Review count: 4
```

When changed:

```text
Previous: KEEP_CONFIGURATION
Current: TRIM_RESOURCES
Changed: Yes
Change reason: OBS_DERIVED_CPU_UTIL_P95 dropped 92% → 48%
Review count: 5
```

### ChangedSinceLastAssessment

*Omit if fingerprint mismatch — note "not comparable". Reference `OBS_*` IDs only.*

| OBS_ID | Previous | Current | Direction |
|--------|----------|---------|-----------|
| OBS_CPU_P95_FLEET | 0.82 cores | 0.90 cores | ↑ |
| OBS_MEMORY_MAX_POD | 1.34 GiB | 1.34 GiB | = |
| ASSESSMENT_CONFIDENCE | 0.8 (High) | 0.9 (Very High) | ↑ |

Direction: `↑` `↓` `=` `new` `removed`

### Assessment confidence (default render)

```text
Assessment confidence: Very High (0.9)

Derived from:
• Evidence completeness
• Evidence quality
• Telemetry coverage
• Contradiction resolution
```

Do **not** emit `0.35 × …` weighted-sum arithmetic in default appendix output. When the Human Report already showed assessment confidence with Basis bullets, the appendix may abbreviate to band + numeric only. Store arithmetic in graph `assessment.assessment_confidence.arithmetic` for INV-07; formula reference: [confidence-formula.md](../reference/confidence-formula.md).
