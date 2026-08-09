#!/usr/bin/env bash
# Apply .github/repo-metadata.yaml to the current GitHub repository via gh.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
META="$ROOT/.github/repo-metadata.yaml"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh CLI required" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 required" >&2
  exit 1
fi
if [[ ! -f "$META" ]]; then
  echo "error: missing $META" >&2
  exit 1
fi

mapfile -t _META_LINES < <(python3 - "$META" <<'PY'
import sys
from pathlib import Path

import yaml

meta = yaml.safe_load(Path(sys.argv[1]).read_text(encoding="utf-8"))
description = str(meta.get("description", "")).strip()
topics = meta.get("topics") or []
if not description:
    raise SystemExit("description is required in repo-metadata.yaml")
if not isinstance(topics, list) or not topics:
    raise SystemExit("topics must be a non-empty list")
print(description.replace("\n", " "))
for topic in topics:
    print(topic)
PY
)

DESCRIPTION="${_META_LINES[0]}"
TOPICS=("${_META_LINES[@]:1}")

echo "Applying repository description and ${#TOPICS[@]} topics..."
ARGS=(repo edit --description "$DESCRIPTION")
for topic in "${TOPICS[@]}"; do
  ARGS+=(--add-topic "$topic")
done
gh "${ARGS[@]}"

echo "ok — verify with: gh repo view --json description,repositoryTopics"
