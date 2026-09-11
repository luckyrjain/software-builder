# Changelog — merge-conflict-analysis

## 1.0.0 — 2026-09-11

### Added

- Initial ambient, read-only merge-conflict-analysis skill: detects an in-progress git merge or
  rebase, cites both sides' intent from commit messages and (where discoverable) originating
  PR/issue text, and recommends a per-hunk resolution — preserving both intents where possible,
  naming the trade-off explicitly where genuinely incompatible — as report-only
  `MERGE_CONFLICT_ANALYSIS.md` / `merge_conflict_analysis` output. Never resolves a hunk, stages,
  commits, or continues/aborts the merge or rebase.
