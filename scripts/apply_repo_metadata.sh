#!/usr/bin/env bash
# Apply .github/repo-metadata.yaml to the GitHub repository via gh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/scripts/apply_repo_metadata.py" --root "$ROOT" "$@"
