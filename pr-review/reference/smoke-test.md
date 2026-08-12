# Smoke test — expected minimal output

To verify the skill works after install or after edits, run it on a small open MR (< 10 files). **Also
run this after any edit to this skill (`SKILL.md`, a `workflow/` file, or a reference file) to catch regressions — not just
after a fresh install.** A correct minimal output should contain:

1. **Phase 0 announcement** — posting mode (`full` / `summary-only` / `general-only` / `chat-only`),
   provider, and host (`workflow/phase-0.md`).
2. **Size summary** — *"Reviewing owner/repo PR #N"* or *"Reviewing group/repo MR !N"* with a scope
   label (`workflow/phase-1.md`).
   If merge conflicts detected, early stop with conflict warning (no Phase 2 findings).
   Per-file size guard and monorepo downstream note when applicable.
3. **Phase 2 review findings** — findings table with **ID** (`PRR-SEC-001`, `PRR-DOC-002`, …), **Conf**, and **Evidence**
   columns **or** *"No actionable findings"* when the emitted count is zero (do not print an empty table
   header). Optional **Engineering improvements** section when repo maturity items apply (may include
   **Repository maturity (informational)** score line).
4. **Executive summary** — narrative + Files reviewed, change classification, Risk, Confidence,
   Recommendation + **Reason** (per deterministic recommendation matrix), review cost metrics,
   **Blocking Issues: None** (when clean) or Major concerns / Must fix (when blocking), Nice to have
   (P1/P2/P3), dimension scores, and pipeline/approval lines (`workflow/phase-5.md`,
   `reference/executive-summary.md`).
5. **`review_metadata` YAML footer** — includes `review_hash` (`scope`, `files`, `head`, `persona`),
   structured `findings[]` array (each entry: `id`, `severity`, `confidence`, `status`, `location`,
   `evidence`), `started`, `finished`, `tool_calls`, `files_fetched`, `diff_pages`, `commits_in_mr`,
   `estimated_effort_min`, `coverage_pct`, `change_classification` (`reference/review-metrics.md`).
6. **Phase 3 confirmation prompt** (or a skip note for `chat-only`; `workflow/posting.md`).

For GitHub discovery smoke coverage, populate or mock at least 31 open PRs with the current branch's
match after item 30. The CLI path must use `--limit 1000` and find that PR. A mocked response of exactly
1000 items must stop with a truncation warning rather than claim the branch has no PR or the list is exhaustive.

If any element is missing, check the selected provider capability: GitLab MCP for an MR; GitHub App/MCP
or `gh auth status --hostname <host>` for a PR. Also check repository resolution and whether the review
is closed/merged (the skill stops early by design).

## Script self-test

The position-mapping helpers have unit tests, including GitHub added-line source-kind and cross-file
integrity cases. From the installed skill directory (or a clone):

```bash
python3 -m pytest tests/                       # from inside pr-review/
python3 -m py_compile scripts/diff-to-positions.py
python3 -m py_compile scripts/github-comment-positions.py
```

From the **repo root** (software-builder clone), the same checks run via: `make lint-pr-review`.

All tests should pass and `py_compile` should print nothing (exit 0).

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md) (≥2 rows — e.g. revert MR standard
checklist, bot MR skipping human-commit hunks).
