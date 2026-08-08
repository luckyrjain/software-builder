#!/usr/bin/env bash
set -euo pipefail

# Cloud Agent bootstrap for software-builder.
# Matches .github/workflows/lint.yml: Python 3.12, shellcheck, ripgrep, hash-pinned deps.

if ! command -v shellcheck >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq shellcheck
fi

# The default Cursor image may ship redis via websockify; CI does not, and
# domain-comprehension lint expects redis to be absent.
if python3 -c "import redis" 2>/dev/null; then
  sudo python3 -m pip uninstall -y redis
fi

python3 -m pip install --user --break-system-packages --require-hashes -r requirements.lock
make setup-hooks
