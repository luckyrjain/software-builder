# Risk Map

## Top smells (max 10, ranked)

| Rank | Smell | Severity | Business impact | Evidence | Recommended remediation |
|------|-------|----------|-----------------|---------|-------------------------|

## Architectural smells (full inventory)

| Smell | Location | Severity | Evidence | Confidence | Mitigation hint |
|-------|----------|----------|----------|------------|-----------------|

## Change impact (context rollup)

| Context | Impacted services (n) | Impacted events (n) | Impacted APIs (n) | Runtime consumers (n) | Confidence |
|---------|----------------------:|--------------------:|------------------:|------------------------:|------------|

## Change risk

| Repo / context | Risk | Fan-out | Runtime critical? | Test signal | Owner clarity | Evidence |
|----------------|------|---------|-------------------|-------------|---------------|----------|

## Merge Conflicts (ADD_REPO mode)

| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Confidence | Status |
|----------|-----------------|-----------|----------------------|----------------------|-----------------|------------|--------|

`Status` values: `open` (blocked, awaiting resolution) \| `resolved` (note which claim won and why, in a
follow-up row or by editing in place) \| `accepted-both` (user explicitly chose to keep both, e.g.
legitimate dual-write).
