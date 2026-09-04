# ADR 0003: Tiered behavioral eval harness

**Status:** Accepted  
**Date:** 2026-08-09

## Context

Lint and artifact validators check file shape and registry contracts but not whether high-risk skills obey posting, merge-gate, or automation guardrails. Shipping prompt/workflow edits without behavioral regression tests risks silent policy drift — especially for unattended wrappers (pr-gatekeeper, incident-triage-agent, backlog-runner).

## Decision

Adopt a **tiered eval model** run via `python3 -m scripts.evals` (`make validate-evals`):

| Tier | Fixture location | What it checks |
|------|------------------|----------------|
| **1** | `evals/fixtures/` + `evals/fixtures/_global.yaml` | Static contracts: required files, workflow frontmatter, invocation guards, forbidden patterns |
| **2** | `evals/transcripts/` | Replayable `tool` / `gate` / `outcome` event sequences with policy assertions (`tool_not_called`, `forbid_tool_before_gate`, etc.) |
| **3** | `evals/golden/` | Recorded model output validation (`field_equals`, `forbid_field_value`, `field_in`, etc.) — static replay without LLM calls in CI |

Tier 2 is intentionally **static replay** — no model call — so CI can enforce policy ordering cheaply. High-risk skills (pr-review, pr-gatekeeper, loop-task-implementer) ship transcript fixtures first.

## Consequences

- **Positive:** Merge gate blocks behavioral regressions on every `make lint`.
- **Positive:** Transcript schema gives a path toward Tier 3 without rewriting Tier 1/2.
- **Negative:** Tier 2 does not prove an LLM will follow policy; it documents and tests expected sequences.
- **Follow-ups:** Expand transcript coverage; Tier 3 golden refresh workflow — [docs/evals/GOLDEN-REFRESH.md](../evals/GOLDEN-REFRESH.md) (`scripts/evals/golden_refresh.py`). Actually executing a skill against a real model, tools mocked from a fixture — [ADR 0004](0004-live-eval-harness.md) (`scripts/evals/live_harness.py`), deliberately kept out of `make lint`/CI for the same reason Tier 2 stays static replay.

## Addendum: what `evals/adversarial/` does and does not prove

Alongside the three fixture tiers above, `scripts/evals/scenario_harness.py` runs a separate Batch 3
per-skill scenario harness over five dimensions — `positive`, `negative`, `ambiguous`, `adversarial`,
`degraded` — one `evals/<dimension>/cases.yaml` per dimension, each required to cover every registered
skill exactly once (enforced via `scripts/registry/eval_contracts.yaml`'s `required_dimensions`).

The `adversarial` dimension's `cases.yaml` is easy to over-read: a reviewer seeing "adversarial:
38/38 skills covered" can reasonably but incorrectly infer full prompt-injection-resistance coverage.
What it actually checks is narrower — `scripts/evals/dispatcher.py`'s regex routing oracle
(`dispatch_with_rules()`) still resolves each skill's normal prompt to the correct `expected_owner`
after an identical "ignore routing, pick the attacker's tool" string is appended. No model runs, no
skill guardrail logic executes, and no output is rendered or redacted in this check — it is a
routing-under-pressure test, not an injection/redaction test. `dispatcher.py`'s own module docstring
says as much: "a test oracle for the repository's declared routing ownership... not a replacement for
host/model routing quality evals."

Real injection-resistance and safe-output-redaction coverage lives in each skill's
`evals/golden/<skill>/golden-injection*.yaml` fixtures (required for every skill via
`scripts/evals/eval_coverage_contract.py`'s `REQUIRED_BEHAVIOR_SCENARIOS` gate) and in the deeper
`adversarial_classes` / `contract_gate: adversarial_matrix` mutation matrix in
`scripts/registry/eval_contracts.yaml` (`scripts/evals/mutation_guard.py`,
`scripts/evals/eval_coverage_contract.py`) — those actually mutate a golden fixture's untrusted input and
reassert the recorded guardrail behavior still holds. Every `evals/adversarial/cases.yaml` entry
carries a `golden_ref` into that real fixture set and the harness asserts it currently passes, so a
routing-only pass here is coupled to, but is not a substitute for, that deeper coverage.

The directory/dimension is not renamed to something less overloaded (e.g. `routing-pressure`) because
"adversarial" is independently reused with different meanings in several load-bearing places —
`eval_contracts.yaml`'s `adversarial_classes`/`adversarial_matrix` gate, `evals/fixtures/_global.yaml`'s
`adversarial` Tier-1 template, `scripts/registry/p1_validation.py`'s `EVAL_DIMENSIONS`, and hardcoded
assertions in `scripts/tests/test_platform_contracts.py` — and a partial rename would make the collision
worse, not better. This note is the documented scope boundary instead.
