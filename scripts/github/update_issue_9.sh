#!/usr/bin/env bash
# Update and close GitHub issue #9 (platform review backlog).
# Requires: gh CLI authenticated with issues:write on luckyrjain/software-builder
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BODY_FILE="${REPO_ROOT}/.github/issue-bodies/9-platform-backlog-closed.md"

if [[ ! -f "${BODY_FILE}" ]]; then
  echo "error: missing ${BODY_FILE}" >&2
  exit 1
fi

gh issue edit 9 --repo luckyrjain/software-builder --body-file "${BODY_FILE}"

gh issue comment 9 --repo luckyrjain/software-builder --body "Closing — platform review backlog is complete on \`main\` (PRs #29–#42).

**Shipped since last update:**
- #34 capabilities for all 22 skills
- #35–#39 composition contracts, write-authority, schema matching
- #36 GitHub Releases + compatibility matrix
- #37–#40 behavioral evals Tier 2/3
- #38–#41 P3 ADRs, glossary, install-all CI, risk_class, docs/history split
- #42 partial overlap with #20 (atomic writes, digest provenance, gatekeeper idempotency doc)

**Still deferred** (listed in issue body): repo topics, SETUP freshness metadata, live LLM golden refresh, full SKILL frontmatter schema.

Skill-behavior backlog remains in #20."

gh issue close 9 --repo luckyrjain/software-builder --reason completed
echo "ok: issue #9 updated and closed"
