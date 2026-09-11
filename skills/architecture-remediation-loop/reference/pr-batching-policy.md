# PR-batching policy (normative)

The one piece of genuinely new logic in Remediate. loop-task-implementer implements one `implementation_task`
per invocation and opens its own PR; this skill decides **which candidates share a task**, so unrelated
concerns don't land in one opaque PR and small cohesive cleanups don't each demand their own review cycle.

**Candidate ≠ implementation_task ≠ PR.** A candidate is the unit of disposition. An `implementation_task`
(and therefore, by loop-task-implementer's own contract, one PR) is the unit this policy assigns.

## 1. Provisional classification

Classify every accepted row when it leaves Disposition:

| Class | Signal |
|-------|--------|
| **Large / high-risk** | Public interface or API change, dependency-direction change, security-sensitive behavior, concurrency/transaction-boundary change, schema/migration, broad blast radius, or the candidate's `module_design_spec` itself spans more than one module |
| **Medium** | A bounded module-internal change with real but contained review surface |
| **Small / low-risk** | Localized cleanup, naming, dead-code removal, a single seam tightening — no caller-visible contract change |

Reclassify once `module-design` or loop-task-implementer's own scoping reveals the true size — never force
an escalated candidate to stay in its original batch.

## 2. Dedicated-PR rule

Every **large/high-risk** candidate gets its own `implementation_task` (and therefore its own PR). Never
merge a large/high-risk candidate into a batch merely to reduce PR count.

## 3. Grouping rule

Group **small** and **cohesive medium** candidates that share the same module, package, subsystem,
architectural seam, root cause, or dependency boundary **and** can be described by one concise
architectural objective — the `implementation_task` description for a batch must read as one story, not a
list of unrelated fixes. If it can't, split the batch.

Never group only to cut PR count: two independent concerns (e.g. an auth cleanup and an unrelated build-
tooling fix) never share a batch even if both are small.

## 4. Escalation / de-escalation

- **Escalate** a candidate out of its batch into its own dedicated task if implementation reveals expanded
  scope, a hidden contract change, a migration requirement, or materially higher review complexity than
  the provisional classification assumed.
- **De-escalate** a candidate that turns out to be a small, localized change with no isolation benefit into
  a related batch — but only before that batch's loop-task-implementer invocation starts, never mid-task.
- Each loop-task-implementer dispatch for a batch increments that batch's `batch_attempt_count` (see
  [reference/candidate-ledger.md § Schema](candidate-ledger.md#schema)). A second consecutive `ESCALATED`
  outcome for the same batch trips `REPEATED_BATCH_ESCALATION` — see
  [SKILL.md § Circuit breakers](../SKILL.md#circuit-breakers); never dispatch the same batch a third time.

## 5. Sizing target

Optimize for the smallest number of batches that preserves cohesion, reviewability, and per-batch
rollback/bisect safety — not for one PR per candidate, and not for one PR for the whole cycle.

## 6. Inter-batch dependencies

Two batches dispatched in the same cycle share the same starting base branch — neither sees the other's
unmerged code. If a candidate in batch B structurally depends on code only introduced by a candidate in
batch A (e.g. B's fix assumes an interface A is introducing), dispatching both in parallel would build B
against code that doesn't exist yet, the same failure mode backlog-runner's own
[reference/queue-policy.md § 2 rule 4](../../backlog-runner/reference/queue-policy.md#2-queue-pull-and-ordering)
documents for cross-ticket dependencies.

Default: **sequence, don't stack.** A batch with a declared dependency on another batch is not dispatched
until the dependency batch is merge-confirmed (workflow/converge.md § 1) — it stays `PENDING` this cycle,
same as any other deferred candidate. Real cross-batch dependencies are expected to be uncommon (most
candidates from one bounded `review_scope` are independent); when one is identified during batching or
design, record it explicitly as `depends_on_batch` (the dependency's `batch_id`) on the dependent
candidate's own ledger row — see
[reference/candidate-ledger.md § Schema](candidate-ledger.md#schema) — never as an implicit ordering
assumption that doesn't survive a session boundary.
