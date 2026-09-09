# Cost Estimation

Extracted from `thresholds.md` for maintainability. Referenced by
[workflow/cost-analysis.md](workflow/cost-analysis.md) and [queries.md](queries.md).

## Priority for recommendations (R0 → R1 → R2)

R0. **Manifest mismatch** — reconcile repo vs running requests; all optimization recommendations **advisory only** until fixed.
R0. **When blocked (decision confidence < 0.50):** observe-first — instrument lag → validate partition distribution → account for sidecars → query CPU dist metrics (`kubernetes.pod.cpu.usage.dist`) → capture SLO baseline → keep requests → HPA Phase 1 observe → Phase 2 evaluate.
R0. Resolve stability blockers (throttle > 5%, OOM, high restarts).
R1. CPU request trims — when utilization < 30% **and** p95 supports trim (confidence ≥ 0.80).
R1. Memory request trims — when utilization < 50%.
R2. Replica / HPA changes — validate all consumer groups, partition assignment, PDB, HA, and node packing first.

Skip recommendations saving < 0.1 cores **and** < 128Mi unless the user requests a full audit.

## Monthly savings formulas

```
proposed_cpu_req  = ceil(p95_cores * 1.5, 50m) per pod × replicas
freed_cpu_cores   = current_cpu_req_total - proposed_cpu_req_total

proposed_mem_req  = peak_proxy_usage * 1.15, rounded to 64Mi/128Mi per pod × replicas  # peak proxy = worst-pod app-container max (not p95)
freed_giB         = current_mem_req_total - proposed_mem_req_total

freed_replica_cpu = per_pod_cpu_req × (current_replicas - proposed_replicas)
freed_replica_mem = per_pod_mem_giB × (current_replicas - proposed_replicas)
```

Monthly $ when rates are known:

```
monthly_savings_cpu  = freed_cpu_cores × $/core/mo
monthly_savings_mem  = freed_giB × $/GiB/mo
monthly_savings_total = sum of non-overlapping recommendation savings (see below)
```

Do not double-count: compute **total savings from the final proposed state** (trimmed per-pod requests × proposed replicas). If recommending both request trim and replica reduction, use one combined delta — not separate CPU-row $ plus replica-row $.

## Calibrating $/core and $/GiB

**Preferred (observed):** from Datadog CCM over **30d** (same window for cost and requests):

```
monthly_cpu_cost       = sum:aws.cost.amortized.cpu.allocated{scope}       # scalar, aggregator: sum, 30d
monthly_mem_cost       = sum:aws.cost.amortized.mem.allocated{scope}       # scalar, aggregator: sum, 30d
avg_cpu_requests_cores = sum:kubernetes.cpu.requests{scope}                  # scalar, aggregator: avg, 30d
avg_mem_requests_giB   = sum:kubernetes.memory.requests{scope} / 1_073_741_824   # scalar, aggregator: avg, 30d

$/core/mo = monthly_cpu_cost / avg_cpu_requests_cores
$/GiB/mo  = monthly_mem_cost / avg_mem_requests_giB
```

Do not multiply or divide by 730.

**CCM without container allocation:** `.cpu.allocated` / `.mem.allocated` absent while `aws.cost.amortized` exists → use **resource-only** or **estimated** fallback rates.

**Fallback (estimated — calibrate to your org):**

| Resource | Ballpark (EKS on-demand, us-east-1) | Notes |
|----------|-------------------------------------|-------|
| CPU | ~$35/core/mo | ~$0.048/vCPU-hour × 730h |
| Memory | ~$4/GiB/mo | ~$0.0053/GB-hour × 730h |

> ⚠️ **Pricing caveat:** these rates assume **on-demand** pricing. Orgs using Reserved Instances, Savings Plans, or Spot/Preemptible nodes typically pay 30–70% less — on-demand estimates may overstate savings by 2–3×. Always ask the user for their effective $/core rate before citing dollar figures; label all fallback-based estimates as **estimated (on-demand)**.

**Non-AWS clusters:** The rates above are AWS EKS us-east-1 approximations. For other providers:

| Resource | GCP GKE (us-central1, n2-standard, on-demand) | Azure AKS (East US, D-series, on-demand) |
|----------|-----------------------------------------------|------------------------------------------|
| CPU | ~$28–32/core/mo (estimate only) | ~$30–35/core/mo (estimate only) |
| Memory | ~$3.50–4.00/GiB/mo (estimate only) | ~$3.50–4.50/GiB/mo (estimate only) |

**Before applying any fallback rate:** ask the user to confirm their cloud provider, region, and node type (on-demand vs reserved vs spot). If the user can provide actual per-node costs from their billing console, use those instead. Label all fallback-based cost figures as **estimated (fallback rate — verify with your cloud billing)**.

Label fallback rates as **estimated**; ask the user or platform team for org-specific numbers.

## Cost basis labels

| Label | When to use |
|-------|-------------|
| **observed** | CCM metrics returned data for this deployment |
| **estimated** | Derived from cluster rates or fallback table |
| **resource-only** | CCM unavailable and no rates — show cores/GiB only |

## Real vs potential savings

| Capacity | Meaning |
|----------|---------|
| Reserved CPU/memory | Scheduler reservation — affects packing, not bill directly |
| Node count | Physical nodes required given packing + constraints |
| Cloud cost | Actual spend — requires CAS/node removal |

**Progression:** Reserved CPU → node count → cloud cost. Show all three; do not equate reserved-core reduction with $ savings.

Reducing **reserved** CPU/memory on pods does not reduce cloud spend unless worker nodes are removed (Cluster Autoscaler or manual node scale-down). Always note:

- **Resource savings** — cores/GiB freed from requests/limits
- **Potential $ savings** — only if CAS/node pool can shrink; label *"assumes nodes scale down"*
- If nodes stay fixed or packing unchanged, $ impact ≈ **$0** despite lower requests — describe as **likely no immediate node reduction**

## Node packing

Before claiming $ savings from replica or request reduction:

```text
deployment_cpu_req_total = replicas × per_pod_cpu_request
nodes_needed             = ceil(deployment_cpu_req_total / node_allocatable_cpu)
```

Compare current vs proposed `nodes_needed`. If unchanged, savings are **resource-only** until CAS removes nodes — **likely no immediate node reduction**. State: *"Actual savings depend on scheduler packing efficiency, other workloads, DaemonSets, pod affinity, PDBs, topology spread, and whether node utilization falls below Cluster Autoscaler removal thresholds."*

**Cluster Autoscaler activity:** check `sum:cluster_autoscaler.scaled_down_nodes_total{kube_cluster_name:<cluster>}` ([queries.md](queries.md#node-packing-cost-savings-sanity-check)). If CA is already actively removing nodes, the "no immediate node reduction" caveat may be too pessimistic — freed capacity may translate to real node removal sooner; reflect this when framing $ savings.

**Spot / preemptible nodes:** on spot/preemptible node pools, actual node occupancy fluctuates due to preemption — node-count math is noisier and effective per-node cost is lower. Validate against the on-demand pool separately if the deployment runs on a mixed pool, and label spot-based $ figures accordingly.

## Sidecar capacity planning

Injected sidecars (Istio, Datadog Agent, Vault Agent, Linkerd, FluentBit) consume node resources independently. When estimating node packing, sum app + sidecar CPU/memory requests per pod — documenting sidecars without including them in totals understates node pressure.
