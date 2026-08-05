# Decision IDs (`DEC_`)

| ID | Dimension |
|----|-----------|
| `DEC_CPU_REQUEST` | CPU requests |
| `DEC_MEMORY_REQUEST` | Memory requests |
| `DEC_REPLICAS` | Replica count |
| `DEC_HPA` | HPA configuration |
| `DEC_STABILITY` | Restarts / crashloop |

Status: `ALLOW` | `BLOCKED` | `DEFER`

Structured rationale per decision — required for `BLOCKED` and `DEFER`:

```text
Reasons: ✓ OBS_CPU_P95_FLEET ✓ OBS_KAFKA_LAG_MAX ✓ ASSUME_HPA_INTENTIONAL
Explanation: <one sentence>
```

`Reasons` lists observation/assumption IDs only (automation-friendly). `Explanation` is human text.
