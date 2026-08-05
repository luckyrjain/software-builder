## DecisionObjects

**Decision Graph appendix only** — decision graph with IDs. Human Report uses [human-report.md](human-report.md#optimizationdecision).

Reference `OBS_*` / `ASSUME_*` by ID — **do not repeat values**.

| DEC_ID | Status | Reasons | Explanation |
|--------|--------|---------|-------------|
| DEC_CPU_REQUEST | BLOCKED | ✓ OBS_CPU_P95_FLEET ✓ OBS_CPU_THROTTLE_RATE ✓ ASSUME_P95_REPRESENTATIVE | Fleet p95 exceeds sizing threshold. |
| DEC_MEMORY_REQUEST | ALLOW | ✓ OBS_MEMORY_MAX_POD ✓ OBS_MEMORY_REQUEST | — |
| DEC_REPLICAS | DEFER | ✓ OBS_KAFKA_LAG_MAX_* ✗ OBS_PDB_STATUS | Lag coverage incomplete. |

`Reasons`: `✓` = supporting present; `✗` = missing/blocking. IDs only — automation parses this line.

Blocking observation: listed with `✗` in Reasons or in Missing column if used.

| DEC_ID | Blocking | Missing | STOP_REASON | Next |
|--------|----------|---------|-------------|------|
| DEC_CPU_REQUEST | OBS_CPU_P95_FLEET | — | — | REC_CPU_KEEP |
| DEC_REPLICAS | OBS_KAFKA_LAG_MAX_* | OBS_PDB_STATUS | missing_kafka_lag | REC_PARTITION_VALIDATE |

### WhyThisMatters

*One paragraph per BLOCKED/DEFER `DEC_*`. Reference decision ID — no observation values.*

#### DEC_CPU_REQUEST

Average CPU is not the sizing metric for burst-driven Kafka workloads (`DEC_CPU_REQUEST` blocked by
`OBS_CPU_P95_FLEET`). See `Observations` for values.

#### DEC_REPLICAS

Lag and partition evidence incomplete (`DEC_REPLICAS`). Cutting replicas risks undetected lag spikes.
