# Observation IDs (`OBS_`)

Globally stable. Prefix **required**. Registry: [id-namespaces.md](id-namespaces.md).

## Dual-source companion IDs

Keep the normal `OBS_<SIGNAL>` ID for the value selected by routing policy. When another source also
provides that signal, retain it as `OBS_<SIGNAL>_ALT_<SOURCE>` and create the exactly matching
`EVID_<SIGNAL>_ALT_<SOURCE>` row. Normalize `<SOURCE>` to an uppercase slug such as
`KUBERNETES_MCP`, `DATADOG`, `GITLAB`, `GITHUB`, or `USER_PROVIDED`.

For material disagreement, add both IDs to an Unresolved contradiction, emit
`STOP_REASON: conflicting_signals`, and prohibit READY cut recommendations. Never overwrite one value
or attach two evidence rows to the same observation.

## CPU

| ID | Signal |
|----|--------|
| `OBS_CPU_USAGE_AVG` | App-container avg CPU (cores) |
| `OBS_CPU_USAGE_CURRENT` | Point-in-time app-container CPU from live cluster metrics |
| `OBS_CPU_REQUEST` | CPU request per pod |
| `OBS_CPU_LIMIT` | CPU limit per pod |
| `OBS_CPU_P95_FLEET` | Fleet p95 from `.dist` |
| `OBS_CPU_MAX_POD` | Worst-pod app-container max |
| `OBS_CPU_THROTTLE_RATE` | Throttle % (7d avg) |
| `OBS_DERIVED_CPU_UTIL_AVG` | OBS_CPU_USAGE_AVG ÷ OBS_CPU_REQUEST |
| `OBS_DERIVED_CPU_UTIL_P95` | OBS_CPU_P95_FLEET ÷ OBS_CPU_REQUEST |
| `OBS_DERIVED_CPU_UTIL_MAX` | OBS_CPU_MAX_POD ÷ OBS_CPU_REQUEST |

## Memory

| ID | Signal |
|----|--------|
| `OBS_MEMORY_USAGE_AVG` | App-container avg memory |
| `OBS_MEMORY_REQUEST` | Memory request per pod |
| `OBS_MEMORY_LIMIT` | Memory limit per pod |
| `OBS_MEMORY_MAX_POD` | Worst-pod peak proxy |
| `OBS_MEMORY_OOM_COUNT` | OOM kills (7d) |
| `OBS_DERIVED_MEMORY_UTIL_AVG` | OBS_MEMORY_USAGE_AVG ÷ OBS_MEMORY_REQUEST |
| `OBS_DERIVED_MEMORY_UTIL_MAX` | OBS_MEMORY_MAX_POD ÷ OBS_MEMORY_REQUEST |

## Replicas / HPA / Kafka

| ID | Signal |
|----|--------|
| `OBS_REPLICA_COUNT` | Ready replicas |
| `OBS_HPA_MIN` | HPA minReplicas |
| `OBS_HPA_MAX` | HPA maxReplicas |
| `OBS_HPA_DESIRED_AVG` | HPA desired (7d avg) |
| `OBS_KAFKA_PARTITION_COUNT` | Partition count |
| `OBS_KAFKA_LAG_MAX_<group>` | Lag max per consumer group |
| `OBS_KAFKA_LAG_AVG_<group>` | Lag avg per consumer group |
| `OBS_KAFKA_CONSUME_RATE_<group>` | Consume msg/s |
| `OBS_HTTP_RPS` | HTTP request rate |

## Manifest / infra

| ID | Signal |
|----|--------|
| `OBS_MANIFEST_CPU_REQUEST` | Repo CPU request |
| `OBS_MANIFEST_MEMORY_REQUEST` | Repo memory request |
| `OBS_RUNNING_CPU_REQUEST` | Running CPU request |
| `OBS_RUNNING_MEMORY_REQUEST` | Running memory request |
| `OBS_PDB_STATUS` | PodDisruptionBudget |
| `OBS_RESTART_MAX_POD` | Max restarts per pod (7d) |
| `OBS_RESTART_TOTAL` | Total restarts (7d) |
| `OBS_CAS_SCALE_DOWN` | CAS scale-down activity |

## VPA (Vertical Pod Autoscaler)

| ID | Signal |
|----|--------|
| `OBS_VPA_TARGET_CPU` | VPA recommended CPU target (from `status.recommendation`) |
| `OBS_VPA_TARGET_MEM` | VPA recommended memory target (from `status.recommendation`) |

## KEDA (Kubernetes Event-Driven Autoscaling)

| ID | Signal |
|----|--------|
| `OBS_KEDA_SCALER_ACTIVE` | Whether the KEDA scaler is currently active (true/false from `keda.scaler.active`) |
| `OBS_KEDA_METRIC_VALUE` | Current external metric value being tracked by KEDA (`keda.scaler.metrics_value`) |
| `OBS_KEDA_METRIC_TARGET` | Target threshold configured in the ScaledObject spec trigger |
| `OBS_KEDA_SCALER_TYPE` | Trigger type (kafka, rabbitmq, prometheus, azure-queue, cron, etc.) from ScaledObject manifest |

## APM (Application Performance Monitoring)

Optional signals — collect when Datadog APM is configured for the service.

| ID | Signal |
|----|--------|
| `OBS_APM_LATENCY_P99` | Application p99 latency (ms) over the 7d analysis window (avg) |
| `OBS_APM_LATENCY_P99_TREND` | Direction of p99 latency: `stable` / `rising` / `falling` (linear regression over 7d) |
| `OBS_APM_ERROR_RATE` | Application-level error rate (%) over the 7d analysis window |

Missing signals: register `OBS_*` with state `missing` in Observations — do not omit the ID.
