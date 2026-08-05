#!/usr/bin/env bash
# Create stub artifact files for manifest --check-content lint fixture.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
paths=(
  domain-config.yaml
  DOMAIN_MAP.md
  UNKNOWNS.md
  KNOWN_OMISSIONS.md
  RUNBOOK.md
  PROGRESS.md
  SQUAD_MAP.md
  BOUNDED_CONTEXTS.md
  DATA_OWNERSHIP.md
  DEPENDENCY_GRAPH.md
  BUSINESS_FLOWS.md
  STATE_MACHINE.md
  API_CATALOG.md
  EVENT_CATALOG.md
  RISK_MAP.md
  DOMAIN_GLOSSARY.md
  ARCHITECTURE_DECISIONS.md
)
for f in "${paths[@]}"; do
  if [ ! -f "$DIR/$f" ]; then
    printf '# stub\n' >"$DIR/$f"
  fi
done
