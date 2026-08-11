# ADR 0004: Mock-tool execution harness, kept out of CI

**Status:** Accepted
**Date:** 2026-08-11

## Context

ADR 0003's tiered eval harness is entirely static — Tier 1 checks file shape, Tier 2 replays a
hand-authored `tool`/`gate`/`outcome` event list, Tier 3 replays a hand-captured output dict. None of
them ever execute a skill; Tier 2's own "Consequences" already name this gap explicitly: "Tier 2 does
not prove an LLM will follow policy; it documents and tests expected sequences." `docs/evals/
GOLDEN-REFRESH.md`'s "Live LLM automation (optional, out of CI)" section anticipated closing this gap
with a maintainer-triggered, non-CI pipeline, but that pipeline didn't exist as code until now.

Closing the gap means actually running a skill — which means a real model call, since skills in this
repo are markdown instructions for an agent, not deterministic Python. That is in direct tension with
this repo's `make lint` gate: `Makefile`'s `validate-evals` is a required part of every `make lint`
run, and `make lint` has to stay deterministic, fast, and free, or it stops being trustworthy as a
merge gate.

## Decision

Build the capability (`scripts/evals/live_harness.py` + `scripts/evals/live_run.py`, documented in
[docs/evals/LIVE-HARNESS.md](../evals/LIVE-HARNESS.md)) as a **maintainer-invoked tool that `make
lint` never calls**:

- The harness drives a real agentic tool-use loop (a skill's `SKILL.md` as system prompt, a scenario
  prompt as the opening turn) against the real Anthropic API, answering every tool call from a
  fixture (`evals/live/<skill>/<case>.yaml`'s `mock_tools`) instead of a live MCP server — this is the
  "mock-tool execution" half.
- Two harness-provided tools, `record_gate_decision` and `record_outcome`, make the model's gate
  decisions and final result explicit and structured, so the captured event list is directly
  loadable by the *existing* Tier-2 engine with no changes to `transcript.py` — new capability, no
  new format.
- `live_run.py --score-golden` runs the live-captured output through the *existing* Tier-3 assertion
  engine (`scripts/evals/golden.py`'s public `GoldenCase`/`run_golden_case`, not a reimplementation)
  and reports pass/fail — this is the "live model scoring" half.
- Nothing above is wired into `scripts/evals/__main__.py`'s `run_all()` or `Makefile`'s
  `validate-evals`/`lint` targets. A new workflow, `.github/workflows/live-eval.yml`, exists so a
  maintainer can trigger a run from the Actions UI, but it is `workflow_dispatch`-only and is not
  added to the `main` ruleset's required status checks — a genuine parallel to `dependency-review.yml`
  etc. staying unrequired on their first runs, except here it's permanent by design, not "for now."
- The harness's own control-flow correctness (tool routing, event capture, turn-limit handling,
  reserved-name collisions) *is* covered by `make lint`'s deterministic pytest suite
  (`scripts/tests/test_live_harness.py`, `scripts/tests/test_live_run.py`) via a scripted `ModelClient`
  stub — no network call, so this stays true to Tier 1-3's own testing discipline even though the
  feature it tests is explicitly excluded from running live in CI.

## Consequences

- **Positive:** Closes the gap ADR 0003 named without touching Tier 1-3's speed or determinism —
  `make lint`'s wall-clock time and cost are unaffected by this ADR.
- **Positive:** Reuses Tier 2's event schema and Tier 3's assertion engine directly, so a fixture
  captured live and a fixture hand-authored by a human are interchangeable inputs to the same
  replay/scoring code — no parallel format to maintain.
- **Negative:** A live run is not reproducible turn-for-turn (model sampling variance), so it can
  never be a required check without accepting flaky CI — this is the same reasoning `docs/evals/
  GOLDEN-REFRESH.md` already gives for not auto-refreshing goldens on model variance.
- **Negative:** Costs real tokens per run and requires `ANTHROPIC_API_KEY` to be available wherever
  it's invoked — acceptable for a manually-triggered maintainer tool, not for a per-PR gate.
- **Follow-ups:** If a specific skill's behavioral drift becomes a repeated real incident (not a
  hypothetical), consider promoting `live-eval.yml` to a scheduled (not required) weekly run for that
  skill only, following `scorecard.yml`'s existing "scheduled but not required" precedent — do not
  make it a required check without first observing several weeks of stable, non-flaky runs.
