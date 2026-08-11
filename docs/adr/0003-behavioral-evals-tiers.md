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
