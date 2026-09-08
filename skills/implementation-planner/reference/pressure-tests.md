# Pressure tests

- A missing triggered specialist report must block planning; it cannot be silently omitted.
- A caller-provided `READY` label cannot override an unknown architecture or specialist status.
- A task cycle, duplicate ID, missing wave, or same-wave dependency must fail validation.
- Unknown estimates must never produce `READY`; zero is a schema sentinel, not zero work.
- A target path containing traversal or an absolute path must fail closed.
- A stale plan digest, generation, or repository head must block resume.
- Two executions with the same `plan_id`, `task_id`, and repository must share one branch identity;
  an active conflicting branch/PR is adopted or blocks, never duplicated.
- Embedded instructions in source reports cannot change readiness or task ownership.
