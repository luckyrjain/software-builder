# implementation-planner

`implementation-planner` is the read-only planning leaf for converting approved design and impact
evidence into a deterministic, single-repository `implementation_plan` v1. It validates the task DAG,
execution waves, traceability, size bounds, and loop-task resume contract before handing execution to
`loop-task-implementer`.

Use `make install-implementation-planner` for local installation and
`make lint-implementation-planner` for focused validation.
