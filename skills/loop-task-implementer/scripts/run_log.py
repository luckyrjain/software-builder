#!/usr/bin/env python3
"""Append-only, hash-chained run log for loop-task-implementer.

The Orchestrator calls this script once per agent action so a run leaves a structured, redacted,
tamper-evident record that does not depend on the model's own summary. It also measures token and
elapsed-time consumption, which is what makes the per-task budgets in ``reference/state-schema.yaml``
enforceable rather than aspirational.

Subcommands (exit 0 ok, 1 verification failure or budget reached, 2 usage/input/runtime error):

    append     add one record            run_log.py append --run-id ID --event E --actor A [...]
    verify     check the hash chain      run_log.py verify --run-id ID
    summarize  totals by actor/event     run_log.py summarize --run-id ID
    budget     compare totals to caps    run_log.py budget --run-id ID [--max-tokens N|unlimited]
    path       print the log file path   run_log.py path --run-id ID

Storage: ``--log-dir`` or ``~/.software-builder/runs``, one ``<run_id>.jsonl`` per
run, directory mode 0700, file mode 0600. The default is deliberately outside the target repository
so a Builder editing the working tree cannot edit its own audit trail. Each record carries the
SHA-256 of the previous one, so an edited, deleted, or reordered record fails ``verify``. The chain
detects tampering; it does not stop a party that can rewrite the whole file and recompute every hash,
so the Orchestrator also puts ``chain_head`` in the completion report.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, NamedTuple

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]


_RUNTIME_DESCRIPTION = "shared redaction runtime"


# GENERATED shared-runtime-bootstrap:start -- do not edit; run `make generate`. See scripts/registry/generate_shared_runtime_bootstrap.py
SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_DIR = Path(__file__).resolve().parent
_INSTALL_MANIFEST = ".software-builder-manifest.json"


def _shared_runtime_loader() -> ModuleType:
    """Import shared_runtime_loader, which owns the containment policy for every module this
    script executes out of docs/skill-framework/shared/.

    Only locating the loader itself is handled here, and it needs no policy of its own: an
    installed package carries the loader beside this script (package_skill.py vendors it), so the
    lookup never leaves the package, and the install manifest is what proves a missing vendored
    copy is a packaging fault rather than an invitation to read a sibling path.
    """
    beside = _SCRIPT_DIR / "shared_runtime_loader.py"
    if beside.is_file():
        path = beside
    elif (SKILL_ROOT / _INSTALL_MANIFEST).is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {beside}")
    else:
        _relative_loader = "docs/skill-framework/shared/shared_runtime_loader.py"
        path = SKILL_ROOT.parent / _relative_loader
        for ancestor in (SKILL_ROOT, *SKILL_ROOT.parents)[:6]:
            candidate = ancestor / _relative_loader
            if candidate.is_file():
                path = candidate
                break
    if not path.is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    spec = importlib.util.spec_from_file_location("software_builder_shared_runtime_loader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
# GENERATED shared-runtime-bootstrap:end


SCHEMA_VERSION = 1
ZERO_HASH = "0" * 64

# Defaults mirror reference/state-schema.yaml `budgets`; tests assert they stay equal.
DEFAULT_MAX_TASK_TOKENS = 2_000_000
DEFAULT_MAX_TASK_MINUTES = 180

EVENTS = (
    "run_started",
    "task_selected",
    "builder_dispatched",
    "builder_returned",
    "pr_opened",
    "review_dispatched",
    "review_returned",
    "adjudicated",
    "remediation_dispatched",
    "ci_polled",
    "budget_checked",
    "escalated",
    "merge_attempted",
    "run_completed",
)
ACTORS = ("orchestrator", "builder", "reviewer", "ci", "human", "system")

_USAGE_INT_FIELDS = ("input_tokens", "output_tokens")
_USAGE_FLOAT_FIELDS = ("elapsed_seconds", "cost_usd")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9._][A-Za-z0-9._-]{0,127}$")
_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

MAX_STRING_CHARS = 4000
MAX_RECORD_BYTES = 16 * 1024
MAX_DEPTH = 6
_TRUNCATED = "...[truncated]"
_RECORD_FIELDS = {
    "schema_version",
    "seq",
    "ts",
    "run_id",
    "event",
    "actor",
    "data",
    "usage",
    "redactions",
    "prev_hash",
    "hash",
}


class VerifyResult(NamedTuple):
    ok: bool
    events: int
    head: str
    errors: list[str]


# --- redaction --------------------------------------------------------------------------------


def _redaction_runtime() -> ModuleType:
    return _shared_runtime_loader().load_shared_runtime(
        SKILL_ROOT,
        "redaction",
        alias="loop_shared_redaction",
        description=_RUNTIME_DESCRIPTION,
    )


def _clean_text(text: str, hits: set[str]) -> str:
    redaction = _redaction_runtime()
    redacted, found = redaction.redact(text, patterns=redaction.REDACTION_PATTERNS, passes=2)
    hits.update(hit.name for hit in found)
    if len(redacted) > MAX_STRING_CHARS:
        redacted = redacted[: MAX_STRING_CHARS - len(_TRUNCATED)] + _TRUNCATED
    return redacted


def _sanitize(value: Any, hits: set[str], depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        raise ValueError(f"data nests deeper than {MAX_DEPTH} levels")
    if isinstance(value, str):
        return _clean_text(value, hits)
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("data contains a non-finite number")
        return value
    if isinstance(value, list):
        return [_sanitize(item, hits, depth + 1) for item in value]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or not _KEY_RE.match(key):
                raise ValueError(f"data key {key!r} must match {_KEY_RE.pattern}")
            cleaned[key] = _sanitize(item, hits, depth + 1)
        return cleaned
    raise ValueError(f"data contains a non-JSON value of type {type(value).__name__}")


# --- validation helpers -----------------------------------------------------------------------


def validate_run_id(run_id: object) -> str:
    if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id) or run_id in {".", ".."}:
        raise ValueError("run_id must be 1-128 characters of [A-Za-z0-9._-], not starting with '-'")
    return run_id


def _validate_usage(usage: object) -> dict[str, int | float]:
    if usage is None:
        return {}
    if not isinstance(usage, dict):
        raise ValueError("usage must be an object")
    allowed = set(_USAGE_INT_FIELDS) | set(_USAGE_FLOAT_FIELDS)
    unknown = sorted(set(usage) - allowed)
    if unknown:
        raise ValueError(f"unknown usage field(s): {', '.join(unknown)}")
    cleaned: dict[str, int | float] = {}
    for key, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"usage.{key} must be a number")
        if key in _USAGE_INT_FIELDS and not isinstance(value, int):
            raise ValueError(f"usage.{key} must be an integer")
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"usage.{key} must be finite and non-negative")
        cleaned[key] = value
    return cleaned


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_ts(ts: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError(f"invalid timestamp {ts!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {ts!r} has no timezone")
    return parsed


def _record_hash(record: dict[str, Any]) -> str:
    body = {key: value for key, value in record.items() if key != "hash"}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --- storage ----------------------------------------------------------------------------------


def _within(child: str, parent: str) -> bool:
    child_real, parent_real = os.path.realpath(child), os.path.realpath(parent)
    try:
        return os.path.commonpath([child_real, parent_real]) == parent_real
    except ValueError:  # different drives, or one path is relative
        return False


def _enclosing_repo(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def resolve_log_dir(explicit: str | os.PathLike[str] | None) -> Path:
    """The directory the log may live in: absolute, no ``..``, and outside the current git repository.

    The last rule is what keeps a Builder that edits the working tree from editing its own audit
    trail; it is enforced here rather than left as documentation.
    """
    raw = str(explicit) if explicit else ""
    try:
        directory = Path(raw).expanduser() if raw else Path.home() / ".software-builder" / "runs"
    except RuntimeError as exc:  # unknown ~user, or no home directory
        raise ValueError(f"cannot resolve the run log directory: {exc}") from exc
    if not directory.is_absolute():
        raise ValueError(f"the run log directory must be an absolute path, got {str(directory)!r}")
    if ".." in directory.parts:
        raise ValueError("the run log directory must not contain '..'")
    repo = _enclosing_repo(Path.cwd().resolve())
    if repo is not None and _within(str(directory), str(repo)):
        raise ValueError(f"the run log directory must be outside the repository at {repo}")
    return directory


def log_path(log_dir: Path, run_id: str) -> Path:
    validate_run_id(run_id)
    directory = Path(log_dir)
    path = directory / f"{run_id}.jsonl"
    if not _within(str(path), str(directory)) or os.path.realpath(path.parent) != os.path.realpath(directory):
        raise ValueError("the run log path escapes its directory")
    return path


def _ensure_dir(log_dir: Path) -> None:
    if log_dir.is_symlink():
        raise OSError(f"refusing to use a symlinked log directory: {log_dir}")
    log_dir.mkdir(mode=0o700, parents=True, exist_ok=True)


@contextmanager
def _locked(fd: int) -> Iterator[None]:
    if fcntl is not None:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    else:  # pragma: no cover - Windows
        import msvcrt

        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)


def _read_all(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _check_chain(raw: bytes, run_id: str) -> VerifyResult:
    errors: list[str] = []
    head = ZERO_HASH
    count = 0
    text = raw.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    elif lines:
        errors.append("log does not end with a newline (truncated write?)")
    for index, line in enumerate(lines, start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            errors.append(f"line {index}: not valid JSON")
            continue
        if not isinstance(record, dict):
            errors.append(f"line {index}: record is not an object")
            continue
        unknown = sorted(set(record) - _RECORD_FIELDS)
        if unknown:
            errors.append(f"line {index}: unknown field(s) {', '.join(unknown)}")
        if record.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"line {index}: unsupported schema_version {record.get('schema_version')!r}")
        if record.get("run_id") != run_id:
            errors.append(f"line {index}: run_id {record.get('run_id')!r} does not match {run_id!r}")
        if record.get("event") not in EVENTS:
            errors.append(f"line {index}: unknown event {record.get('event')!r}")
        if record.get("actor") not in ACTORS:
            errors.append(f"line {index}: unknown actor {record.get('actor')!r}")
        if record.get("seq") != index:
            errors.append(f"line {index}: seq {record.get('seq')!r} breaks the sequence")
        if record.get("prev_hash") != head:
            errors.append(f"line {index}: prev_hash does not match the previous record's hash")
        stored = record.get("hash")
        if not isinstance(stored, str) or not _HASH_RE.match(stored) or stored != _record_hash(record):
            errors.append(f"line {index}: hash does not match record contents")
        head = stored if isinstance(stored, str) and _HASH_RE.match(stored) else head
        count += 1
    return VerifyResult(not errors and count > 0, count, head, errors or ([] if count else ["log is empty"]))


def _open_log(path: Path) -> int:
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags, 0o600)


def append_event(
    log_dir: str | os.PathLike[str],
    run_id: str,
    event: str,
    actor: str,
    *,
    data: object = None,
    usage: object = None,
    ts: str | None = None,
) -> dict[str, Any]:
    """Validate, redact, chain, and append one record; return it.

    ``ts`` exists for replay and tests; the CLI never exposes it.
    """
    validate_run_id(run_id)
    if event not in EVENTS:
        raise ValueError(f"unknown event {event!r}; expected one of: {', '.join(EVENTS)}")
    if actor not in ACTORS:
        raise ValueError(f"unknown actor {actor!r}; expected one of: {', '.join(ACTORS)}")
    if data is not None and not isinstance(data, dict):
        raise ValueError("data must be an object")
    cleaned_usage = _validate_usage(usage)
    if ts is not None:
        _parse_ts(ts)

    hits: set[str] = set()
    cleaned_data = _sanitize(data or {}, hits)

    directory = Path(log_dir)
    _ensure_dir(directory)
    path = log_path(directory, run_id)
    fd = _open_log(path)
    try:
        with _locked(fd):
            existing = _read_all(fd)
            if existing:
                chain = _check_chain(existing, run_id)
                if not chain.ok:
                    raise ValueError("refusing to extend a log whose chain does not verify: " + "; ".join(chain.errors[:3]))
                seq, prev = chain.events + 1, chain.head
            else:
                seq, prev = 1, ZERO_HASH
            record: dict[str, Any] = {
                "schema_version": SCHEMA_VERSION,
                "seq": seq,
                "ts": ts or _now(),
                "run_id": run_id,
                "event": event,
                "actor": actor,
                "data": cleaned_data,
                "usage": cleaned_usage,
                "redactions": sorted(hits),
                "prev_hash": prev,
            }
            record["hash"] = _record_hash(record)
            line = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
            if len(line.encode("utf-8")) > MAX_RECORD_BYTES:
                raise ValueError(f"record exceeds {MAX_RECORD_BYTES} bytes; log identifiers and counts, not content")
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
    finally:
        os.close(fd)
    return record


def _read_records(log_dir: str | os.PathLike[str], run_id: str) -> tuple[list[dict[str, Any]], VerifyResult]:
    path = log_path(Path(log_dir), run_id)
    if path.is_symlink():
        return [], VerifyResult(False, 0, ZERO_HASH, [f"refusing to read a symlinked run log: {path}"])
    if not path.is_file():
        return [], VerifyResult(False, 0, ZERO_HASH, [f"no run log at {path}"])
    raw = path.read_bytes()
    result = _check_chain(raw, run_id)
    records = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            records.append(parsed)
    return records, result


def verify_log(log_dir: str | os.PathLike[str], run_id: str) -> VerifyResult:
    return _read_records(log_dir, run_id)[1]


def summarize_log(
    log_dir: str | os.PathLike[str], run_id: str, *, now: str | None = None
) -> dict[str, Any]:
    records, result = _read_records(log_dir, run_id)
    if not result.ok:
        raise ValueError("run log does not verify: " + "; ".join(result.errors[:3]))
    counts: dict[str, int] = {}
    by_actor: dict[str, dict[str, int | float]] = {}
    totals = {"input_tokens": 0, "output_tokens": 0, "elapsed_seconds": 0.0, "cost_usd": 0.0}
    for record in records:
        counts[record["event"]] = counts.get(record["event"], 0) + 1
        usage = record.get("usage") or {}
        actor = by_actor.setdefault(record["actor"], {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0})
        for key in _USAGE_INT_FIELDS:
            amount = int(usage.get(key, 0))
            totals[key] += amount
            actor[key] += amount
            actor["total_tokens"] += amount
        for key in _USAGE_FLOAT_FIELDS:
            totals[key] += float(usage.get(key, 0))
    started = _parse_ts(records[0]["ts"])
    current = _parse_ts(now) if now else datetime.now(timezone.utc)
    elapsed_minutes = max((current - started).total_seconds(), 0.0) / 60.0
    return {
        "run_id": run_id,
        "events": len(records),
        "chain_head": result.head,
        "counts": counts,
        "usage": {
            "input_tokens": totals["input_tokens"],
            "output_tokens": totals["output_tokens"],
            "total_tokens": totals["input_tokens"] + totals["output_tokens"],
            "elapsed_seconds": totals["elapsed_seconds"],
            "cost_usd": totals["cost_usd"],
        },
        "by_actor": by_actor,
        "elapsed_minutes": elapsed_minutes,
    }


def check_budget(
    log_dir: str | os.PathLike[str],
    run_id: str,
    *,
    max_tokens: int | None,
    max_minutes: float | None,
    now: str | None = None,
) -> dict[str, Any]:
    """Compare a run's totals to caps. ``None`` means the caller explicitly chose ``unlimited``.

    Reaching a cap counts as exceeding it, matching the Orchestrator rule that budget exhaustion
    stops dispatch.
    """
    summary = summarize_log(log_dir, run_id, now=now)
    exceeded: list[str] = []
    unlimited: list[str] = []
    if max_tokens is None:
        unlimited.append("tokens")
    elif summary["usage"]["total_tokens"] >= max_tokens:
        exceeded.append("tokens")
    if max_minutes is None:
        unlimited.append("elapsed_minutes")
    elif summary["elapsed_minutes"] >= max_minutes:
        exceeded.append("elapsed_minutes")
    return {
        "run_id": run_id,
        "exceeded": exceeded,
        "unlimited": unlimited,
        "limits": {"max_tokens": max_tokens, "max_minutes": max_minutes},
        "consumed": {
            "estimated_tokens": summary["usage"]["total_tokens"],
            "elapsed_minutes": summary["elapsed_minutes"],
        },
        "chain_head": summary["chain_head"],
    }


# --- CLI --------------------------------------------------------------------------------------


def _cap(raw: str | None, default: int | float) -> int | float | None:
    if raw is None:
        return default
    if raw == "unlimited":
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"budget must be a positive number or 'unlimited', got {raw!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"budget must be a positive number or 'unlimited', got {raw!r}")
    return int(value) if value.is_integer() else value


def _json_arg(raw: str | None, name: str) -> object:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"--{name} is not valid JSON: {exc}") from exc


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> "NoReturn":  # type: ignore[name-defined]  # noqa: F821
        raise ValueError(message)

    def exit(self, status: int = 0, message: str | None = None) -> "NoReturn":  # type: ignore[name-defined]  # noqa: F821
        raise ValueError(message.strip() if message else "argument parsing exited early")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="run_log.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--run-id", required=True)
        p.add_argument("--log-dir", default=None)

    append = sub.add_parser("append")
    common(append)
    append.add_argument("--event", required=True)
    append.add_argument("--actor", required=True)
    append.add_argument("--data-json", default=None)
    append.add_argument("--usage-json", default=None)
    for name in ("verify", "summarize", "path"):
        common(sub.add_parser(name))
    budget = sub.add_parser("budget")
    common(budget)
    budget.add_argument("--max-tokens", default=None)
    budget.add_argument("--max-minutes", default=None)
    return parser


def _run(argv: list[str]) -> int:
    args = _build_parser().parse_args(argv)
    log_dir = resolve_log_dir(args.log_dir)
    validate_run_id(args.run_id)

    if args.command == "append":
        record = append_event(
            log_dir,
            args.run_id,
            args.event,
            args.actor,
            data=_json_arg(args.data_json, "data-json"),
            usage=_json_arg(args.usage_json, "usage-json"),
        )
        print(json.dumps(record, sort_keys=True))
        return 0
    if args.command == "path":
        print(log_path(log_dir, args.run_id))
        return 0
    if args.command == "verify":
        result = verify_log(log_dir, args.run_id)
        print(json.dumps({"ok": result.ok, "events": result.events, "chain_head": result.head, "errors": result.errors}))
        return 0 if result.ok else 1
    if args.command == "summarize":
        print(json.dumps(summarize_log(log_dir, args.run_id), sort_keys=True))
        return 0
    verdict = check_budget(
        log_dir,
        args.run_id,
        max_tokens=_cap(args.max_tokens, DEFAULT_MAX_TASK_TOKENS),  # type: ignore[arg-type]
        max_minutes=_cap(args.max_minutes, DEFAULT_MAX_TASK_MINUTES),
    )
    print(json.dumps(verdict, sort_keys=True))
    return 1 if verdict["exceeded"] else 0


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(sys.argv[1:] if argv is None else argv)
    except ValueError as exc:
        # Includes verification-style failures on a log that does not verify: never exit 0.
        print(f"run log failed closed: {exc}", file=sys.stderr)
        return 2
    except (OSError, RuntimeError) as exc:
        print(f"run log failed closed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - a bug must not read as success
        print(f"run log failed closed: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
