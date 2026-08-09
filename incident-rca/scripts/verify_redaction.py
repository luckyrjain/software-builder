#!/usr/bin/env python3
"""Post-hoc redaction verifier — the automated half of reference/log-redaction.md's Phase 5
pre-render checklist item 2 ("no raw Authorization/Bearer/api_key/password/PEM block appears
outside [REDACTED] markers").

Why this exists rather than instrumenting every log source: KubeSense/Splunk logs go through
scripts/kubesense_logs.py, which already calls redact_secrets() itself — that path is covered by
code, not by this script. Datadog log aggregation, Jira ticket bodies, Slack/PagerDuty snippets,
and manual paste from an engineer all arrive as MCP tool results or human input directly into the
agent's context — there is no Python ingestion path for those to instrument. This script instead
scans whatever got written to disk (evidence.json, the RCA report, any file) for the same
secret-shaped patterns redact_secrets() would have masked, after the fact — one mechanism that
covers all five sources uniformly, including any future source not yet in that table.

Detection method: run redact_secrets() (imported directly, not a second copy of the regex list
that could drift) over the file and diff line-by-line against the original. redact_secrets() is
idempotent on already-clean/redacted text (verified in tests/test_kubesense_logs.py) — any line
that changes was carrying something it shouldn't have. Never reports the secret value itself, only
the line number, so this script's own output can't become a leak vector in CI logs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kubesense_logs import redact_secrets  # noqa: E402


def find_leaky_lines(text: str) -> list[int]:
    original_lines = text.splitlines()
    redacted_lines = redact_secrets(text).splitlines()
    return [i + 1 for i, (orig, red) in enumerate(zip(original_lines, redacted_lines)) if orig != red]


def verify_file(path: Path) -> list[int]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return find_leaky_lines(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", type=Path, help="Files to scan (evidence.json, RCA report, etc.)")
    args = parser.parse_args(argv)

    total_leaks = 0
    for path in args.paths:
        if not path.is_file():
            print(f"error: not a file: {path}", file=sys.stderr)
            return 1
        for line_no in verify_file(path):
            print(f"{path}:{line_no}: unredacted secret-shaped content")
            total_leaks += 1

    if total_leaks:
        print(f"\nverify-redaction: {total_leaks} line(s) with unredacted content — see log-redaction.md", file=sys.stderr)
        return 1
    print(f"verify-redaction: {len(args.paths)} file(s) clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
