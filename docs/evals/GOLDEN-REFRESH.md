# Tier-3 golden output refresh (maintainer workflow)

Tier-3 evals replay **static** `recorded_output` fixtures in CI — no live LLM calls. When a skill's
expected structured output changes intentionally, refresh the golden file explicitly.

## When to refresh

- After a deliberate behavior change that updates structured fields checked by golden assertions
- When adding a new Tier-3 case (copy an existing fixture, capture output, assert)

Do **not** refresh goldens to paper over flaky live-model variance — tighten assertions or keep Tier-2
transcript fixtures instead.

## Steps

1. Run the skill in a real session (Cursor/Claude) against a scenario matching the fixture description.
2. Save the structured output object (the fields your assertions target) to a JSON file, e.g.
   `/tmp/golden-pr-review-chat-only.json`.
3. Dry-run the refresh:

```bash
python3 -m scripts.evals.golden_refresh \
  --fixture evals/golden/pr-review/chat-only-not-posted.yaml \
  --recorded-output /tmp/golden-pr-review-chat-only.json \
  --dry-run
```

4. Write and verify:

```bash
python3 -m scripts.evals.golden_refresh \
  --fixture evals/golden/pr-review/chat-only-not-posted.yaml \
  --recorded-output /tmp/golden-pr-review-chat-only.json \
  --verify
```

5. Run the full Tier-3 suite:

```bash
python3 -m scripts.evals --tier 3
```

## Fixture metadata

Refreshes stamp `refresh_meta.last_refreshed_at` (UTC) and `refresh_meta.refresh_note` in the YAML file.
CI ignores `refresh_meta` — it is provenance for maintainers only.

## Live LLM automation (optional, out of CI)

This repository does not run live model calls in `make lint`/CI. `scripts/evals/live_run.py` (see
[LIVE-HARNESS.md](LIVE-HARNESS.md), [ADR 0004](../adr/0004-live-eval-harness.md)) does the three steps
this section used to only describe in prose:

1. Invokes a skill with a pinned prompt/fixture input (`--live-case`), tools mocked from that fixture
2. Captures structured output to JSON (`--recorded-output-out`)
3. Feeds that JSON to `golden_refresh.py --verify` (or scores it in place with `--score-golden`,
   without writing anything back to disk)

`.github/workflows/live-eval.yml` wires an optional, `workflow_dispatch`-only trigger for it. Keep
that pipeline outside `make lint` so CI stays deterministic.
