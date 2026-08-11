# Mock-tool execution harness (maintainer workflow, out of CI)

`scripts/evals/live_harness.py` + `scripts/evals/live_run.py` actually **run** a skill: the skill's
own `SKILL.md` becomes the system prompt for a real agentic tool-use call against the live Anthropic
API, every tool call the model makes is answered from a fixture instead of a real MCP server, and the
resulting `tool`/`gate`/`outcome` event sequence and final structured output are captured for scoring
or fixture refresh.

This is different from every existing eval tier (ADR 0003), which is static: Tier 1 checks file
shape, Tier 2 replays a hand-authored event list, Tier 3 replays a hand-captured output dict. None of
them ever execute a skill. This harness is the first thing in this repo that does — see
[ADR 0004](../adr/0004-live-eval-harness.md) for why it stays out of `make lint`/CI regardless.

## When to use it

- Sanity-check that a skill's actual tool-call sequence still matches a Tier-2 transcript's
  hand-authored expectations, driven by a real model instead of a human's best guess.
- Capture a fresh `recorded_output` for [Tier-3 golden refresh](GOLDEN-REFRESH.md) from a real run
  instead of a manual Cursor/Claude session transcript.
- Score a live model run directly against an existing golden fixture's assertions — "did the model
  actually produce this?" — without writing anything back to disk.

## Requirements

- `ANTHROPIC_API_KEY` in your environment (never read from a committed file). Real API calls cost
  real tokens — this is a maintainer tool, not something to run per-commit.
- A **live case** fixture (`evals/live/<skill>/<case_id>.yaml`) describing the scenario and the mock
  tool responses. See `evals/live/squad-map/single-repo-clean-map.yaml` for the shape:

  | Field | Required | Meaning |
  |-------|----------|---------|
  | `skill`, `case_id`, `description` | yes | same meaning as every other eval tier |
  | `scenario_prompt` | yes | the opening user turn |
  | `tool_defs` | no | Anthropic tool-schema list (`name`, `description`, `input_schema`) the model may call |
  | `mock_tools` | yes | mapping of tool name → canned response, or a list of responses consumed in call order (call N+1 past the list's length is a harness error, not a silent repeat) |
  | `max_turns` | no (default 12) | turn budget before the harness gives up |
  | `transcript_assertions` | no | seeds a brand-new Tier-2 fixture's `assertions` when `--write-transcript` targets a file that doesn't exist yet |

The harness always adds two tools of its own — `record_gate_decision(name, decision, reason)` and
`record_outcome(status, output)` — and instructs the model (via a note appended to the system prompt)
to call them explicitly. This is what makes the captured transcript directly loadable by the existing
Tier-2 engine (`scripts/evals/transcript.py`) with zero changes to that module: the event schema
(`type: tool|gate|outcome`) is identical whether a human wrote it or the harness captured it live.

## Usage

```bash
export ANTHROPIC_API_KEY=sk-...

# Live model scoring: run live, score the captured output against an existing golden fixture's
# assertions, write nothing to disk.
python3 -m scripts.evals.live_run \
  --live-case evals/live/squad-map/single-repo-clean-map.yaml \
  --score-golden evals/golden/squad-map/some-case.yaml

# Refresh (or bootstrap) a Tier-2 transcript fixture from a real run.
python3 -m scripts.evals.live_run \
  --live-case evals/live/squad-map/single-repo-clean-map.yaml \
  --write-transcript evals/transcripts/squad-map/single-repo-clean-map.yaml

# Just capture recorded_output and feed it into the existing golden_refresh.py flow.
python3 -m scripts.evals.live_run \
  --live-case evals/live/squad-map/single-repo-clean-map.yaml \
  --recorded-output-out /tmp/out.json
python3 -m scripts.evals.golden_refresh \
  --fixture evals/golden/squad-map/some-case.yaml \
  --recorded-output /tmp/out.json \
  --verify
```

`--write-transcript` only ever replaces the `events` key on an existing fixture (description and
assertions are left as the maintainer wrote them, same refresh-in-place pattern as
`golden_refresh.py`); it only writes `description`/`assertions` from scratch when the target file
doesn't exist yet, and then only from the live case's own `transcript_assertions`.

## What this does not do

- It does not run in GitHub Actions on every push or PR. `.github/workflows/live-eval.yml` exists but
  is `workflow_dispatch`-only and is not a required status check — a maintainer triggers it by hand.
- It does not replace Tier 2/3's static replay in `make lint`. Those stay exactly as fast and
  deterministic as before; this harness produces the fixtures they replay, it doesn't run in their
  place.
- It does not validate that a live case's `tool_defs`/`mock_tools` match a skill's *real* MCP tool
  surface — that's on the fixture author. A live case with plausible-but-wrong tool names will still
  run (the model will call whatever tools it's offered); it just won't be testing the skill against
  its actual production tool integration. Treat a new live case as a draft until you've confirmed its
  tool names against the skill's own setup docs.
