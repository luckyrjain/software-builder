#!/usr/bin/env python3
"""Prepare and reconcile idempotent GitHub review-comment writes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

MARKER_VERSION = "v1"
HEX_SHA = re.compile(r"^[0-9a-fA-F]{7,64}$")
SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._:-]{1,160}$")


def _body_sha256(body: str) -> str:
    """Hash exactly the sanitized UTF-8 body, excluding the marker."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _prepared_body(body: str, *, head_sha: str, comment_kind: str, identity: str) -> dict[str, str]:
    if not HEX_SHA.fullmatch(head_sha):
        raise ValueError("head_sha must be 7-64 hexadecimal characters")
    if comment_kind not in {"inline", "summary"}:
        raise ValueError("comment_kind must be inline or summary")
    if not SAFE_TOKEN.fullmatch(identity):
        raise ValueError("identity must be a non-empty safe token")
    digest = _body_sha256(body)
    marker = (
        f"<!-- cursor-pr-review-write:{MARKER_VERSION} head={head_sha} "
        f"kind={comment_kind} identity={identity} body_sha256={digest} -->"
    )
    return {"body_sha256": digest, "marker": marker, "post_body": f"{marker}\n{body}"}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "reconcile"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--body-stdin", action="store_true", required=True)
        sub.add_argument("--head-sha", required=True)
        sub.add_argument("--comment-kind", choices=("inline", "summary"), required=True)
        sub.add_argument("--identity", required=True)
        if command == "reconcile":
            sub.add_argument("--readback-file", type=Path, required=True)
            sub.add_argument("--ambiguous-attempt", type=int, choices=(1, 2), required=True)
    return parser


def _load_readback(path: Path) -> tuple[bool, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("complete"), bool):
        raise ValueError("readback must contain boolean complete")
    comments = data.get("comments")
    if not isinstance(comments, list):
        raise ValueError("readback comments must be a list")
    bodies: list[str] = []
    for comment in comments:
        if not isinstance(comment, dict) or not isinstance(comment.get("body"), str):
            raise ValueError("each readback comment must contain a string body")
        bodies.append(comment["body"])
    return data["complete"], bodies


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        prepared = _prepared_body(
            sys.stdin.read(),
            head_sha=args.head_sha,
            comment_kind=args.comment_kind,
            identity=args.identity,
        )
        if args.command == "prepare":
            result: dict[str, object] = prepared
        else:
            complete, bodies = _load_readback(args.readback_file)
            if prepared["post_body"] in bodies:
                result = {"outcome": "accepted", "retry": False}
            elif complete and args.ambiguous_attempt == 1:
                result = {"outcome": "absent", "retry": True}
            else:
                result = {"outcome": "ambiguous", "retry": False}
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": "invalid_recovery_input", "detail": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
