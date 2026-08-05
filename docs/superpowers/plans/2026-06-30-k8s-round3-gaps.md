# k8s-overprovisioning Round 3 Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 4 gaps from the Round 3 gap analysis for the k8s-overprovisioning-datadog skill: KEDA metric collection (P1-1), limit/request ratio analysis (P1-2), VPA+HPA conflict detection (P2-1), and APM confidence modifier (P3-2).

**Architecture:** Each gap is a targeted addition to one or two existing workflow or reference files — no new files are created. All changes are purely additive (new sections appended or inserted into existing ones) to avoid breaking existing logic.

**Tech Stack:** Markdown skill documents. No code to compile. Validation is by reading the modified file and checking the target section exists with correct content.

## Global Constraints

- All files are under `k8s-overprovisioning-datadog/`
- Never duplicate existing content — insert additions only
- New OBS_ IDs must follow the `OBS_<CATEGORY>_<SIGNAL>` naming convention from `reference/id-namespaces.md`
- Pressure tests go in `reference/pressure-tests.md` as new rows in the existing table
- All collection steps added to `collect-metrics.md` are under COLLECT phase (MCP calls only)

---

### Task 1: P1-1 — KEDA Metric Collection

**Files:**
- Modify: `k8s-overprovisioning-datadog/reference/observation-ids.md` (add `## KEDA` section)
- Modify: `k8s-overprovisioning-datadog/workflow/collect-metrics.md` (add `## KEDA workloads` section)
- Modify: `k8s-overprovisioning-datadog/workflow/replica-analysis.md` (expand the KEDA stub)
- Modify: `k8s-overprovisioning-datadog/reference/pressure-tests.md` (add 2 KEDA pressure test rows)

**Interfaces:**
- Produces: `OBS_KEDA_SCALER_ACTIVE`, `OBS_KEDA_METRIC_VALUE`, `OBS_KEDA_METRIC_TARGET`, `OBS_KEDA_SCALER_TYPE` in the observation registry
- Consumes: KEDA detection already stubbed in `replica-analysis.md` ("probe `keda.scaler.active` / `keda.scaler.metrics_value`")

- [ ] **Step 1: Add KEDA pressure test rows to `reference/pressure-tests.md`**

  The file uses a markdown table. Append these two rows to the existing table (before the closing blank line after the last row):

  ```markdown
  | KEDA ScaledObject detected; `keda.scaler.active` = true; `keda.scaler.metrics_value` = 12; target = 100 | Replica verdict uses external metric (not CPU %); no CPU-target recommendation emitted |
  | KEDA workload; `keda.scaler.active` missing from Datadog | `STOP_REASON: missing_keda_metrics`; defer replica verdict; note metric gap |
  ```

- [ ] **Step 2: Verify the rows are not already there**

  Run:
  ```bash
  grep -n "KEDA\|keda" /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/reference/pressure-tests.md
  ```
  Expected: no output (the file currently has no KEDA rows). If rows exist already, skip Step 3 for those rows.

- [ ] **Step 3: Add KEDA OBS_ IDs to `reference/observation-ids.md`**

  Read the current end of the file. After the VPA section (the last section currently), append:

  ```markdown

  ## KEDA (Kubernetes Event-Driven Autoscaling)

  | ID | Signal |
  |----|--------|
  | `OBS_KEDA_SCALER_ACTIVE` | Whether the KEDA scaler is currently active (true/false from `keda.scaler.active`) |
  | `OBS_KEDA_METRIC_VALUE` | Current external metric value being tracked by KEDA (`keda.scaler.metrics_value`) |
  | `OBS_KEDA_METRIC_TARGET` | Target threshold configured in the ScaledObject spec trigger |
  | `OBS_KEDA_SCALER_TYPE` | Trigger type (kafka, rabbitmq, prometheus, azure-queue, cron, etc.) from ScaledObject manifest |
  ```

- [ ] **Step 4: Add KEDA collection steps to `workflow/collect-metrics.md`**

  Read the current end of the file. After the `## Sidecar containers` section (the last section), append:

  ```markdown

  ## KEDA workloads

  When `replica-analysis.md` detects `keda.scaler.active` is present or the manifest contains a
  `ScaledObject` resource for this deployment:

  1. **From manifest** (git MCP or user-provided `ScaledObject` YAML):
     - Read `spec.triggers[].type` → `OBS_KEDA_SCALER_TYPE`
     - Read the trigger threshold field (e.g. `spec.triggers[].metadata.lagThreshold` for Kafka,
       `targetAverageValue` for Prometheus) → `OBS_KEDA_METRIC_TARGET`
     - Read `spec.minReplicaCount` and `spec.maxReplicaCount` — treat as the effective HPA bounds.

  2. **From Datadog:**
     - `keda.scaler.active{kube_deployment:<name>}` — record as `OBS_KEDA_SCALER_ACTIVE` (boolean).
     - `keda.scaler.metrics_value{kube_deployment:<name>}` (7d avg and max) — record as
       `OBS_KEDA_METRIC_VALUE`.

  3. **If both Datadog signals are unavailable:** set `OBS_KEDA_SCALER_ACTIVE` and
     `OBS_KEDA_METRIC_VALUE` to `missing`. Emit `STOP_REASON: missing_keda_metrics` in
     `replica-analysis` — defer replica verdict.

  4. **CPU metrics still collected** but are not used for the replica scaling verdict on KEDA
     workloads. CPU data informs per-pod request sizing only.
  ```

- [ ] **Step 5: Expand the KEDA stub in `workflow/replica-analysis.md`**

  The current KEDA section reads:
  ```
  ## KEDA

  If `hpa_*` null, probe `keda.scaler.active` / `keda.scaler.metrics_value` before "fixed replicas". Evaluate external metric — not CPU target %.
  ```

  Replace it with:

  ```markdown
  ## KEDA

  If `hpa_*` null or `OBS_KEDA_SCALER_ACTIVE` is set, this is a KEDA-managed workload. Follow the
  KEDA path — do **not** use CPU target % for the replica verdict.

  ### Collection
  Load `OBS_KEDA_SCALER_TYPE`, `OBS_KEDA_METRIC_VALUE`, and `OBS_KEDA_METRIC_TARGET` from COLLECT
  (see `collect-metrics.md` § KEDA workloads). If either value is `missing` →
  `STOP_REASON: missing_keda_metrics`; defer replica verdict.

  ### Evaluation

  | Condition | Verdict |
  |-----------|---------|
  | `OBS_KEDA_METRIC_VALUE` consistently < `OBS_KEDA_METRIC_TARGET × 0.3` (7d avg) AND replicas > `spec.minReplicaCount` | **Candidates for `spec.minReplicaCount` reduction** — KEDA is keeping replicas alive for a metric that rarely triggers |
  | `OBS_KEDA_METRIC_VALUE` near zero for the entire 7d window | Strong signal: minimum replica floor may be too high |
  | `OBS_KEDA_METRIC_VALUE` frequently >= `OBS_KEDA_METRIC_TARGET` | Under-scaled or target too low — do not reduce |
  | KEDA scaler type is `kafka` | Cross-check with `OBS_KAFKA_LAG_*` (see HPA metric suitability table) |

  ### Guardrails
  - Never recommend cutting below `spec.minReplicaCount`.
  - Never recommend setting a CPU HPA target on a KEDA workload — use the external metric.
  - If VPA is also present on this deployment, check for VPA+HPA conflict per `reason.md`.
  ```

- [ ] **Step 6: Verify additions are present**

  ```bash
  grep -n "OBS_KEDA\|KEDA workloads\|missing_keda_metrics" \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/reference/observation-ids.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/replica-analysis.md
  ```
  Expected: hits in all three files.

- [ ] **Step 7: Commit**

  ```bash
  git add \
    k8s-overprovisioning-datadog/reference/observation-ids.md \
    k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    k8s-overprovisioning-datadog/workflow/replica-analysis.md \
    k8s-overprovisioning-datadog/reference/pressure-tests.md
  git commit -m "feat(k8s): P1-1 — KEDA metric collection, OBS IDs, and replica evaluation path"
  ```

---

### Task 2: P1-2 — Limit/Request Ratio Analysis

**Files:**
- Modify: `k8s-overprovisioning-datadog/workflow/collect-metrics.md` (add limit metric queries)
- Modify: `k8s-overprovisioning-datadog/workflow/cpu-analysis.md` (add limit/request ratio section)
- Modify: `k8s-overprovisioning-datadog/workflow/memory-analysis.md` (add limit/request ratio section)
- Modify: `k8s-overprovisioning-datadog/reference/pressure-tests.md` (add 2 limit ratio pressure test rows)

**Interfaces:**
- Produces: `OBS_CPU_LIMIT` and `OBS_MEMORY_LIMIT` populated from live metrics (these IDs already exist in `observation-ids.md` but are currently never queried)
- Consumes: thresholds from `thresholds.md` §CPU limits and §Memory limits ratio (both tables already exist)

- [ ] **Step 1: Add pressure test rows for limit/request ratio**

  Append to `reference/pressure-tests.md` table:

  ```markdown
  | CPU limit = 500m, CPU request = 480m (limit ≈ request), CPU usage avg 40% | Flag tight CPU limits — any burst will throttle; do not recommend CPU request trim |
  | Memory limit = 512Mi, memory request = 500Mi; OOM kill count = 3 (7d) | Memory limit too tight; block memory trim; recommend raising both limit and request |
  ```

- [ ] **Step 2: Add limit metric collection to `workflow/collect-metrics.md`**

  After the `## KEDA workloads` section added in Task 1 (or after `## Sidecar containers` if Task 1 is not yet done), append:

  ```markdown

  ## Resource limits collection

  Always query per-pod CPU and memory **limits** alongside requests. Limits determine OOM and throttle
  boundaries — analyzing requests alone misses burst-headroom risk.

  **CPU limit:**
  ```text
  avg:kubernetes.cpu.limits{kube_deployment:<name>,env:<env>,kube_container_name:<app>} by {pod_name}
  ```
  Record as `OBS_CPU_LIMIT`. If unavailable (metric absent), derive from manifest
  `resources.limits.cpu` and record with state `manifest_only`.

  **Memory limit:**
  ```text
  avg:kubernetes.memory.limits{kube_deployment:<name>,env:<env>,kube_container_name:<app>} by {pod_name}
  ```
  Record as `OBS_MEMORY_LIMIT`. If unavailable, derive from manifest `resources.limits.memory`.

  Cross-check: `OBS_CPU_LIMIT / OBS_CPU_REQUEST` and `OBS_MEMORY_LIMIT / OBS_MEMORY_REQUEST` are
  the burst-headroom ratios used in `cpu-analysis.md` and `memory-analysis.md`.
  ```

- [ ] **Step 3: Add limit/request ratio section to `workflow/cpu-analysis.md`**

  After the `## Trends` section (the last section), append:

  ```markdown

  ## Limit/request ratio

  After collecting `OBS_CPU_LIMIT` and `OBS_CPU_REQUEST`, compute the ratio and evaluate using
  [thresholds.md](../thresholds.md#cpu-limits):

  | Ratio | Label | Action |
  |-------|-------|--------|
  | `OBS_CPU_LIMIT / OBS_CPU_REQUEST > 4×` | Limit likely too high | Note in observations; scheduling visibility reduced |
  | `2–4×` | Acceptable headroom | No action |
  | `< 2×` | Tight limits | **Do not trim CPU requests** — any burst will immediately throttle at the limit |
  | `OBS_CPU_LIMIT ≈ OBS_CPU_REQUEST` (< 1.1×) | Near-zero burst headroom | Block CPU request trim; recommend raising limit first |

  Emit `DEC_CPU_REQUEST` as BLOCKED with reason `tight_cpu_limits` when ratio < 1.5× regardless
  of utilization — a seemingly over-provisioned request against a tight limit creates a silent throttle
  trap on any load spike.
  ```

- [ ] **Step 4: Add limit/request ratio section to `workflow/memory-analysis.md`**

  After the `## Trends` section (the last section), append:

  ```markdown

  ## Limit/request ratio

  After collecting `OBS_MEMORY_LIMIT` and `OBS_MEMORY_REQUEST`, compute the ratio and evaluate using
  [thresholds.md](../thresholds.md#memory-request-utilization):

  | Pattern | Risk | Action |
  |---------|------|--------|
  | `OBS_MEMORY_LIMIT ≈ OBS_MEMORY_REQUEST` (ratio < 1.1×) | High OOM risk on any burst | **Block memory request trim**; recommend raising limit first |
  | `OBS_MEMORY_LIMIT ≥ 2× OBS_MEMORY_REQUEST` | Safe headroom | Trim requests toward `peak_proxy × 1.15` |
  | Peak usage > `OBS_MEMORY_REQUEST` but < `OBS_MEMORY_LIMIT` | Running on limit buffer | Bump request toward peak proxy before any trim |
  | Peak usage > `OBS_MEMORY_LIMIT` | OOM inevitable | Increase both; `STOP_REASON: oom_kills` |

  Include `OBS_MEMORY_LIMIT / OBS_MEMORY_REQUEST` ratio in the Human Report whenever recommending
  a memory request change.
  ```

- [ ] **Step 5: Verify additions**

  ```bash
  grep -n "Resource limits collection\|Limit/request ratio\|tight_cpu_limits\|OBS_CPU_LIMIT\|OBS_MEMORY_LIMIT" \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/cpu-analysis.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/memory-analysis.md
  ```
  Expected: hits in all three files.

- [ ] **Step 6: Commit**

  ```bash
  git add \
    k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    k8s-overprovisioning-datadog/workflow/cpu-analysis.md \
    k8s-overprovisioning-datadog/workflow/memory-analysis.md \
    k8s-overprovisioning-datadog/reference/pressure-tests.md
  git commit -m "feat(k8s): P1-2 — limit/request ratio collection and analysis for CPU and memory"
  ```

---

### Task 3: P2-1 — VPA+HPA Coexistence Conflict Detection

**Files:**
- Modify: `k8s-overprovisioning-datadog/workflow/collect-metrics.md` (note HPA metric source type when VPA is present)
- Modify: `k8s-overprovisioning-datadog/workflow/reason.md` (add conflict detection in VPA alignment section)
- Modify: `k8s-overprovisioning-datadog/reference/pressure-tests.md` (add VPA+HPA conflict pressure test row)

**Interfaces:**
- Produces: `STOP_REASON: vpa_hpa_conflict_cpu` or `vpa_hpa_conflict_memory` when both target the same dimension
- Consumes: `OBS_VPA_TARGET_CPU` / `OBS_VPA_TARGET_MEM` (from existing VPA collection), HPA `targetAverageUtilization` dimension from manifest

- [ ] **Step 1: Add VPA+HPA conflict pressure test row**

  Append to `reference/pressure-tests.md` table:

  ```markdown
  | VPA present on CPU + HPA using `targetAverageUtilization` (CPU %); agent proposes a VPA-based CPU cut | `STOP_REASON: vpa_hpa_conflict_cpu`; block VPA cut recommendation; explain oscillation risk |
  ```

- [ ] **Step 2: Add HPA metric source collection note to `workflow/collect-metrics.md`**

  In the existing `## VPA recommendations (positive signal)` section, after the last row of the VPA state table, add:

  ```markdown

  **HPA dimension check (when VPA present):** When `OBS_VPA_TARGET_CPU` or `OBS_VPA_TARGET_MEM` is
  populated, also read the HPA `spec.metrics[]` from the manifest:
  - If HPA has a `type: Resource` metric targeting `cpu` → record `hpa_targets_cpu: true`
  - If HPA has a `type: Resource` metric targeting `memory` → record `hpa_targets_memory: true`
  - If HPA uses only `type: External` or `type: Object` → no conflict (KEDA or custom metric path)

  Pass `hpa_targets_cpu` and `hpa_targets_memory` to REASON for conflict detection.
  ```

- [ ] **Step 3: Add VPA+HPA conflict detection to `workflow/reason.md`**

  In the existing `## VPA alignment` section, after the last bullet point (the one about VPA target below proposed cut), add:

  ```markdown

  ## VPA + HPA coexistence conflict

  Before emitting any VPA-based cut recommendation, check for controller conflict:

  ```
  IF OBS_VPA_TARGET_CPU is set AND hpa_targets_cpu == true:
    → STOP_REASON: vpa_hpa_conflict_cpu
    → Block ALL cut recommendations on the CPU dimension
    → Explanation: "VPA is adjusting CPU requests while HPA is scaling replicas on CPU
      utilization. When VPA raises CPU requests, HPA sees lower utilization and scales
      replicas down; when VPA lowers requests, HPA sees higher utilization and scales up.
      This creates oscillation. Disable CPU-dimension VPA or switch HPA to a custom/external
      metric before any sizing change."

  IF OBS_VPA_TARGET_MEM is set AND hpa_targets_memory == true:
    → STOP_REASON: vpa_hpa_conflict_memory
    → Block ALL cut recommendations on the memory dimension
    → Explanation: same pattern — VPA memory adjustments fight HPA memory-based scaling.
  ```

  When VPA targets a dimension that HPA does **not** target (e.g. VPA on memory, HPA on CPU only):
  no conflict — VPA recommendation on memory is safe to use.
  ```

- [ ] **Step 4: Verify additions**

  ```bash
  grep -n "vpa_hpa_conflict\|HPA dimension check\|coexistence" \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/reason.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/reference/pressure-tests.md
  ```
  Expected: hits in all three files.

- [ ] **Step 5: Commit**

  ```bash
  git add \
    k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    k8s-overprovisioning-datadog/workflow/reason.md \
    k8s-overprovisioning-datadog/reference/pressure-tests.md
  git commit -m "feat(k8s): P2-1 — VPA+HPA coexistence conflict detection"
  ```

---

### Task 4: P3-2 — APM Confidence Modifier

**Files:**
- Modify: `k8s-overprovisioning-datadog/reference/observation-ids.md` (add `## APM` section)
- Modify: `k8s-overprovisioning-datadog/workflow/collect-metrics.md` (add optional APM signal collection)
- Modify: `k8s-overprovisioning-datadog/workflow/confidence.md` (add APM-based confidence modifier)
- Modify: `k8s-overprovisioning-datadog/reference/pressure-tests.md` (add APM pressure test row)

**Interfaces:**
- Produces: `OBS_APM_LATENCY_P99`, `OBS_APM_ERROR_RATE` in observation registry
- Consumes: `OBS_DERIVED_CPU_UTIL_P95` (already produced) for the joint condition

- [ ] **Step 1: Add APM pressure test row**

  Append to `reference/pressure-tests.md` table:

  ```markdown
  | CPU p95 = 25% of request (low); APM p99 latency trending up 40% over 7d | Lower CPU cut confidence by 0.15; note "latency rising despite low CPU — possible non-CPU bottleneck"; do not emit cut recommendation at high confidence |
  ```

- [ ] **Step 2: Add APM OBS_ IDs to `reference/observation-ids.md`**

  After the KEDA section added in Task 1 (or after the VPA section if Task 1 is not done), append:

  ```markdown

  ## APM (Application Performance Monitoring)

  Optional signals — collect when Datadog APM is configured for the service.

  | ID | Signal |
  |----|--------|
  | `OBS_APM_LATENCY_P99` | Application p99 latency (ms) over the 7d analysis window (avg) |
  | `OBS_APM_LATENCY_P99_TREND` | Direction of p99 latency: `stable` / `rising` / `falling` (linear regression over 7d) |
  | `OBS_APM_ERROR_RATE` | Application-level error rate (%) over the 7d analysis window |
  ```

- [ ] **Step 3: Add optional APM collection to `workflow/collect-metrics.md`**

  After the `## Resource limits collection` section added in Task 2 (or after `## KEDA workloads` if Task 2 is not done), append:

  ```markdown

  ## APM signals (optional — confidence modifier)

  When Datadog APM is available (`get_datadog_metric_context` or `search_datadog_metrics` responds
  for the service), collect latency and error rate to guard against false-positive cut recommendations.

  1. **Discover the latency metric:** run `search_datadog_metrics: "<service> p99 latency"` — metric
     names vary by framework (e.g. `trace.servlet.request.duration.p99`,
     `trace.http.request.duration.p99`). Select the p99 variant for the service.
  2. **Query p99 over 7d:** use `get_datadog_metric` with rollup `1h`. Record `OBS_APM_LATENCY_P99`
     (7d avg) and derive `OBS_APM_LATENCY_P99_TREND`:
     - Fit a linear trend over the 7d hourly series.
     - `rising` = positive slope where the last 24h avg > first 24h avg by > 15%.
     - `falling` or `stable` otherwise.
  3. **Error rate (optional):** discover the error rate metric; record `OBS_APM_ERROR_RATE`.
  4. **If APM metrics are unavailable:** set `OBS_APM_LATENCY_P99` to `missing` — proceed without
     the modifier. Do not block the assessment.
  ```

- [ ] **Step 4: Add APM confidence modifier to `workflow/confidence.md`**

  After the `## Assessment severity` section (the last section), append:

  ```markdown

  ## APM latency modifier (RECOMMENDATION_CONFIDENCE only)

  Apply **before** finalizing per-`REC_*` confidence scores, when APM signals were collected:

  ```
  IF OBS_APM_LATENCY_P99_TREND == "rising"
  AND OBS_DERIVED_CPU_UTIL_P95 < 50%  (CPU looks healthy)
  → Subtract 0.15 from RECOMMENDATION_CONFIDENCE for any CPU cut recommendation
  → Add note to DEC rationale:
    "APM p99 latency is trending upward despite low CPU utilization. The bottleneck may be
    non-CPU (connection pool, DB saturation, thread limit, GC pressure). Confidence in CPU
    cut reduced — investigate APM before trimming."
  ```

  This modifier does NOT apply to:
  - Keep/hold recommendations (only cut recommendations are affected)
  - Memory or replica recommendations (CPU-specific bottleneck signal)
  - When `OBS_APM_LATENCY_P99_TREND` is `missing` (absent metrics cannot lower confidence)
  ```

- [ ] **Step 5: Verify additions**

  ```bash
  grep -n "OBS_APM\|APM signals\|APM latency modifier\|APM confidence" \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/reference/observation-ids.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/workflow/confidence.md \
    /Users/luckyjain/Projects/ai-skills/k8s-overprovisioning-datadog/reference/pressure-tests.md
  ```
  Expected: hits in all four files.

- [ ] **Step 6: Commit**

  ```bash
  git add \
    k8s-overprovisioning-datadog/reference/observation-ids.md \
    k8s-overprovisioning-datadog/workflow/collect-metrics.md \
    k8s-overprovisioning-datadog/workflow/confidence.md \
    k8s-overprovisioning-datadog/reference/pressure-tests.md
  git commit -m "feat(k8s): P3-2 — APM latency confidence modifier for CPU cut recommendations"
  ```
