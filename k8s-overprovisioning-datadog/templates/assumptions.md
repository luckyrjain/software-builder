## Assumptions

| ID | Assumption | If violated | Affected |
|----|------------|-------------|----------|
| `ASSUME_HPA_INTENTIONAL` | Fixed HPA is intentional (warm JVMs, SLAs) | Accidental overscale | REPLICA_*, HPA_* |
| `ASSUME_LAG_OPERATIONAL` | Kafka lag is operational, not incident | Lag spike in window | REPLICA_REDUCE |
| `ASSUME_PARTITIONS_STABLE` | Partition count stable | Recent rebalance | REPLICA_*, HPA_* |
| `ASSUME_P95_REPRESENTATIVE` | Fleet p95 represents production traffic | Peak window differs | CPU_REDUCE_REQUEST |
| `ASSUME_NO_DEPLOY` | No major deploy in observation window | Deploy in window | All optimization recs |

Add rows as needed. Reference assumption IDs in recommendation `Depends on`.
