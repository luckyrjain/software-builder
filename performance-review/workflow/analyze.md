---
workflow_version: 1.0
phase: analyze
produces:
  - complexity_findings
  - db_behavior_findings
  - n_plus_1_findings
  - cache_findings
  - memory_findings
  - concurrency_findings
  - connection_pool_findings
  - fanout_findings
  - evidence_gaps
consumes:
  - reviewed_content
  - profiling_excerpts
  - scope_hint
---

# Analyze — evaluate the eight performance focus areas

Run every check below against `reviewed_content`, corroborated by `profiling_excerpts` when supplied.
Each check produces zero or more findings, or an explicit evidence-gap record when it cannot be
completed — never a silent skip.

## 1. Algorithmic complexity

Identify Big-O hotspots: nested loops over the same or related collections, repeated linear scans
inside a loop, sorting inside a loop, recursive calls without memoization on overlapping subproblems.
Flag complexity that is asymptotically worse than necessary for the operation, and weight severity by
realistic input size (a fixed small collection is a lower-severity finding than one that scales with
user/tenant/record count).

## 2. DB behavior

Read every database access in `reviewed_content`: missing `LIMIT`/pagination on unbounded result sets,
`SELECT *` where only a few columns are used, queries run inside a request path that could be batched,
transactions held open across slow external calls. Distinct from N+1 below — this is about individual
query shape and access pattern, not repetition count.

## 3. N+1

Identify any loop, comprehension, or per-item callback that issues one database (or downstream
network) call per iteration, where a single batched call would suffice. This is the single most common
finding this skill exists to catch — check explicitly for it even when nothing else in DB behavior
looks wrong.

## 4. Cache

Evaluate any caching layer present: correctness (is the cache key derived from everything that affects
the cached value, or can two different results collide on one key), invalidation (is the cache
invalidated on every code path that changes the underlying data, including error/partial-failure
paths), and hit-rate assumptions (does the code assume a warm cache without a documented fallback for
a cold/evicted one).

## 5. Memory

Look for allocation patterns that scale with input size unnecessarily (building a full in-memory copy
of a large collection when streaming would do), unbounded growth (a cache, buffer, or accumulator with
no eviction/cap), and retained references that prevent garbage collection (long-lived closures or
listeners holding onto large objects).

## 6. Concurrency

Check for races (unsynchronized shared mutable state across goroutines/threads/async tasks) and
contention (a lock held longer than necessary, serializing what should be parallel work). Note when
this check cannot be completed from static text alone — runtime interleaving often cannot be proven
from a code read; record the gap explicitly rather than asserting a false-confident "no races found."

## 7. Connection pools

Assess pool sizing against realistic concurrent load implied by the reviewed content or
`profiling_excerpts`: a pool sized well below expected concurrency, connections not released on early
returns/exceptions, or a pool shared across workloads with very different latency profiles (a slow
report query sharing a pool with fast transactional queries).

## 8. Downstream fanout

Identify call amplification: one inbound request triggering an unbounded or linearly-scaling number of
outbound calls to other services, especially without a concurrency cap (issuing all of them at once
rather than bounded-parallel or batched).

## Evidence gaps

Any of the eight checks above that cannot be completed — no `profiling_excerpts` to corroborate a
runtime-only concern (real cache hit-rate, actual lock contention under load), or `reviewed_content`
too sparse (prose description, not actual code/query text) to evaluate a given area — is recorded as
an explicit evidence gap for that area, never silently skipped and never folded into a "None found"
result (which asserts the area was checked and was clean). This feeds Report's evidence-gap handling
and verdict derivation directly.
