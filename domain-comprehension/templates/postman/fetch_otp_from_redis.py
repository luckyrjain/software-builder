#!/usr/bin/env python3
"""Fetch an OTP value from Redis for manual/Postman testing.

Never hardcodes a Redis key pattern or credentials — pass this service's exact
key pattern via --key-pattern (see this engagement's {map_file} section Per-Repo
Deep Dives -> Auth & Gateway for the real pattern, e.g. 'otp:{identifier}').

Connection config comes from env vars only:
  REDIS_HOST, REDIS_PORT (default 6379), REDIS_DB (default 0), REDIS_PASSWORD (optional)
"""

from __future__ import annotations

import argparse
import os
import sys


def build_key(key_pattern: str, identifier: str) -> str:
    if "{identifier}" not in key_pattern:
        raise ValueError("--key-pattern must contain the literal placeholder '{identifier}'")
    try:
        return key_pattern.format(identifier=identifier)
    except (KeyError, IndexError, ValueError) as exc:
        raise ValueError(f"--key-pattern is malformed: {exc}") from exc


def fetch_otp(key: str) -> str | None:
    import redis  # imported lazily so --help works without the redis package installed

    client = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=int(os.environ.get("REDIS_DB", "0")),
        password=os.environ.get("REDIS_PASSWORD") or None,
        decode_responses=True,
    )
    return client.get(key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--key-pattern",
        required=True,
        help="Redis key pattern with an '{identifier}' placeholder, e.g. 'otp:{identifier}'",
    )
    parser.add_argument(
        "--identifier", required=True, help="Phone number / user id / whatever this service keys OTPs by"
    )
    args = parser.parse_args(argv)

    try:
        key = build_key(args.key_pattern, args.identifier)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    value = fetch_otp(key)
    if value is None:
        print(f"no value at key {key!r} (not sent yet, or already expired)", file=sys.stderr)
        return 1

    print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
