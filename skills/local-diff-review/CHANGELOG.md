# Changelog — local-diff-review

## 1.0.0 — 2026-09-09

### Added

- Initial ambient, read-only local-diff-review skill: reviews changes since a fixed point against this
  repo's documented Standards and against a supplied Spec (issue/ticket text), emitting report-only
  `LOCAL_DIFF_REVIEW.md` / `local_diff_review` output with independent Standards and Spec findings lists.
  Never writes source, tests, configuration, or posts a comment anywhere.
