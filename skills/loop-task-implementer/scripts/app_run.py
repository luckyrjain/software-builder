#!/usr/bin/env python3
"""app-run/UI verification tier for the Builder (gap-backlog B7).

Implements, as directly as possible, the converged (revision 3) design's Data model / State
machines / Failure strategy sections —
``docs/superpowers/specs/2026-10-01-b7-app-run-ui-verification-design.md``.

This module is deliberately self-contained and has **no parameter through which a repository path
could be supplied to :func:`resolve_app_run_policy`**. That is not an oversight: the design's own
round-2 -> round-3 correction is the single most important finding in this change — the
`app_run` policy (a shell command the Builder will execute) must be sourced the *identical* way
`allowed_actions`/`autonomous_merge_authorized` already are in ``workflow/orchestrator.md`` §1:
external to the repository under review, supplied by the caller invoking this skill, **never**
from any file read from the repository, committed or not. :func:`resolve_app_run_policy` takes
only the already-resolved policy value as its argument — it has no code path that reads a
repository, a working directory, or any file at all, so it cannot regress that rule even if
called incorrectly elsewhere.

Two residuals are intentionally **not** closed here (see the design's Open Questions 3 and 5, and
Failure strategy): (a) a ``start_command`` that itself daemonizes/double-forks can escape the
tracked process group and survive teardown — this module's post-kill liveness recheck only
confirms the *tracked* process group is clear, and explicitly cannot detect an escapee; (b)
nothing here validates or restricts what ``start_command`` does once running (local mutation,
network exfiltration) — out of scope, matching the architecture review's Condition 3 reasoning.

Outcomes are reported through a single ``app_run: <message>`` string (see :meth:`AppRunOutcome.render`),
the same advisory channel ``regression_gate.command`` already established — never a new run-log event.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

# --- repo-root import bootstrap (mirrors the sys.path convention already used by sibling skill
# scripts -- e.g. convention_capture.py, this skill's own sibling script, for `scripts.task_lease`;
# also k8s-overprovisioning-datadog/scripts/validate_decision_graph.py,
# migration-program-manager/scripts/aggregate_migration_status.py -- for locating a repository-root
# module from inside skills/<name>/scripts/). Not the yaml-safety GENERATED bootstrap (that one is
# specific to scripts/yaml_safety.py's load_unique_yaml_file file-reading variant, machine-managed
# by `make generate` for a fixed skill list that doesn't include this one); this script parses a
# caller-supplied YAML *string* value, not a file path, so it wants load_unique_yaml instead.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[2]
if (_REPO_ROOT / "skills.yaml").is_file() and str(_REPO_ROOT) not in sys.path:
    sys.path.append(str(_REPO_ROOT))

try:
    from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_yaml
except ImportError:  # pragma: no cover - only reachable outside a source checkout of this repo
    YAML_SAFETY_ERRORS = ()  # type: ignore[assignment]  # never read: load_unique_yaml is None guards all uses
    load_unique_yaml = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALLOWED_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
DEFAULT_READINESS_TIMEOUT_SECONDS = 30
HARD_CAP_READINESS_TIMEOUT_SECONDS = 120
DEFAULT_TEARDOWN_GRACE_SECONDS = 5.0
DEFAULT_READINESS_POLL_INTERVAL_SECONDS = 1.0
SCREENSHOT_FILENAME = "app_run_screenshot.png"


# ---------------------------------------------------------------------------
# Policy data model
# ---------------------------------------------------------------------------


@dataclass
class ProcessPolicy:
    """`app_run.process` — required if `app_run.process` is non-null (Data model)."""

    start_command: str
    readiness_url: str
    port: int
    readiness_timeout_seconds: int = DEFAULT_READINESS_TIMEOUT_SECONDS
    # Not part of the externally-documented schema's required shape; an optional escape hatch for
    # the one case the design calls out explicitly: "if a stack genuinely needs shell features...
    # shell=True is permitted for this ONE field only, and no OTHER task-derived field may ever be
    # concatenated into that same shell string." Defaults False (argv-first via shlex.split).
    shell: bool = False


@dataclass
class AppRunPolicy:
    """`implementation_task.app_run` — mirrors the two-capability split structurally."""

    process: ProcessPolicy | None
    screenshot: bool = False


def resolve_app_run_policy(raw: Any) -> AppRunPolicy | None:
    """Validate and normalize an already caller-supplied `app_run` policy value.

    **This function never reads a repository, a file on disk, or the current working
    directory.** Its only input is `raw`. Whatever `raw` is must already have been sourced by the
    Orchestrator's policy-discovery step (`workflow/orchestrator.md` §1) from the external,
    caller-supplied channel — the identical sourcing rule already used for `allowed_actions`/
    `autonomous_merge_authorized` — never from prose inside any file read from the repository
    under review, committed or not. Because this function has no parameter through which a
    repository path could be supplied, it cannot regress that rule no matter how it is called.

    Returns `None` (meaning the `SKIPPED` outcome) for an absent, malformed, or structurally
    incomplete policy — fail-closed, matching the design's Failure strategy table exactly:
    a YAML-parse failure, `port` declared with no `start_command`, and `screenshot: true` with
    `process: null` are all treated identically to policy-absent. Never partially proceeds on an
    incomplete shape.
    """
    if raw is None:
        return None

    data: Any = raw
    if isinstance(raw, (str, bytes)):
        if load_unique_yaml is None:  # pragma: no cover - PyYAML always present in this repo's environment
            return None
        try:
            data = load_unique_yaml(raw)
        except YAML_SAFETY_ERRORS:
            return None

    if not isinstance(data, dict):
        return None

    screenshot = data.get("screenshot", False)
    if not isinstance(screenshot, bool):
        return None

    process_raw = data.get("process")
    if process_raw is None:
        if screenshot:
            # Schema-invariant violation: `screenshot` has no effect without a running `process`.
            # Treated as malformed per the design's Failure strategy table, not silently accepted.
            return None
        return AppRunPolicy(process=None, screenshot=False)

    if not isinstance(process_raw, dict):
        return None

    start_command = process_raw.get("start_command")
    readiness_url = process_raw.get("readiness_url")
    port = process_raw.get("port")
    timeout = process_raw.get("readiness_timeout_seconds", DEFAULT_READINESS_TIMEOUT_SECONDS)
    shell = process_raw.get("shell", False)

    if not isinstance(start_command, str) or not start_command.strip():
        return None  # covers "port declared with no start_command"
    if not isinstance(readiness_url, str) or not readiness_url.strip():
        return None
    if not isinstance(port, int) or isinstance(port, bool) or not (1 <= port <= 65535):
        return None
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        return None
    if not isinstance(shell, bool):
        return None

    timeout = min(timeout, HARD_CAP_READINESS_TIMEOUT_SECONDS)

    return AppRunPolicy(
        process=ProcessPolicy(
            start_command=start_command,
            readiness_url=readiness_url,
            port=port,
            readiness_timeout_seconds=timeout,
            shell=shell,
        ),
        screenshot=screenshot,
    )


# ---------------------------------------------------------------------------
# readiness_url host/userinfo validation (the single most security-sensitive function here)
# ---------------------------------------------------------------------------


def validate_readiness_url(url: str) -> bool:
    """Return True only for a `readiness_url` this skill is allowed to start a process for.

    Real URL parsing only (`urllib.parse.urlsplit`), never substring/prefix matching — the direct
    fix for the SSRF-allowlist-bypass class the design's adversarial review rounds found:

    - `http://127.0.0.1.evil.com` — a naive suffix/substring check on "127.0.0.1" would accept
      this; a real parsed-hostname exact-match check correctly rejects it.
    - `http://evil.com@localhost/` — the parsed *hostname* is `localhost` (would pass a naive
      hostname-only check), but the authority carries userinfo (`evil.com@`) and must be rejected
      regardless of host match.
    - A no-scheme bare input (`127.0.0.1:3000` typed without a scheme) parses to an empty scheme
      and an empty hostname — rejected outright, never specially handled.
    - `http://[::1]:3000/` parses `.hostname` to the unbracketed, normalized `::1` — accepted,
      matching the design's round-3 wording fix (never compare against the literal `[::1]`).
    - `file://localhost/<any path>` or `ftp://localhost/...` — hostname/userinfo alone pass (the
      hostname is `localhost`), but a non-`http`/`https` scheme reaches handlers
      (`FileHandler`/`FTPHandler`/`DataHandler`) this function must never authorize for a readiness
      probe — rejected on scheme alone, independent of the hostname check.
    """
    if not isinstance(url, str) or not url:
        return False
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    if not parsed.scheme:
        return False
    if parsed.scheme.lower() not in ("http", "https"):
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    try:
        hostname = parsed.hostname
    except ValueError:
        return False
    if not hostname:
        return False
    return hostname.lower() in _ALLOWED_LOCAL_HOSTNAMES


# ---------------------------------------------------------------------------
# Redirect-disabled HTTP probe (readiness poll + smoke test)
# ---------------------------------------------------------------------------


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Disables redirect-following entirely: a 3xx becomes an HTTPError, never a followed hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


# Built from an explicit, minimal handler set via `OpenerDirector.add_handler` directly — never
# `urllib.request.build_opener(...)`, even when passed specific handler classes. `build_opener`
# only *skips* a default handler class when a passed-in handler is that class or a **subclass** of
# it; `HTTPHandler`/`HTTPSHandler` are not subclasses of `FileHandler`/`FTPHandler`/`DataHandler`,
# so passing them to `build_opener` does not exclude those from its full default chain — it still
# installs every one of them alongside whatever was passed in. Constructing the opener by hand,
# adding only the handlers this probe actually needs, is the only way to guarantee
# `FileHandler`/`FTPHandler`/`DataHandler` are never installed. `validate_readiness_url`'s scheme
# check is the primary defense against a `file://`/`ftp://` URL ever reaching this opener; this is
# the defense-in-depth layer — even if such a URL reached `probe_url` through some other path,
# there is no handler installed here that is able to act on it.
_NO_REDIRECT_OPENER = urllib.request.OpenerDirector()
for _handler_cls in (
    urllib.request.UnknownHandler,
    urllib.request.HTTPHandler,
    urllib.request.HTTPDefaultErrorHandler,
    _NoRedirectHandler,
    urllib.request.HTTPErrorProcessor,
    urllib.request.HTTPSHandler,
):
    _NO_REDIRECT_OPENER.add_handler(_handler_cls())
del _handler_cls


@dataclass
class ProbeResult:
    ok: bool
    status: int | None
    error: str | None = None


def probe_url(url: str, *, method: str = "GET", timeout: float = 2.0) -> ProbeResult:
    """GET/HEAD `url` with redirect-following disabled entirely.

    A 3xx response is treated as a non-2xx result and is never followed — this closes the
    SSRF-via-redirect gap identified in round 1 without adding a second host-check layer for the
    `Location` header.

    Reports connection failure, and any unexpected response shape (e.g. a non-http(s) handler
    response with no numeric status), as `ProbeResult(ok=False, ...)` — this function's documented
    contract is to report failure without ever raising, so a malformed/unexpected response object
    is handled defensively rather than left to crash on an unguarded status comparison.
    """
    request = urllib.request.Request(url, method=method)
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout) as response:
            status = getattr(response, "status", None)
            if status is None:
                getcode = getattr(response, "getcode", None)
                status = getcode() if callable(getcode) else None
            if not isinstance(status, int):
                return ProbeResult(ok=False, status=None, error="response had no numeric status")
            return ProbeResult(ok=200 <= status < 300, status=status)
    except urllib.error.HTTPError as exc:
        # Includes blocked redirects (3xx) as well as genuine 4xx/5xx — all non-2xx.
        return ProbeResult(ok=False, status=exc.code)
    except urllib.error.URLError as exc:
        return ProbeResult(ok=False, status=None, error=str(exc.reason))
    except OSError as exc:
        return ProbeResult(ok=False, status=None, error=str(exc))
    except Exception as exc:  # defensive: never let an unexpected response shape escape uncaught
        return ProbeResult(ok=False, status=None, error=str(exc))


# ---------------------------------------------------------------------------
# Port pre-check (step 3 of the numbered check order)
# ---------------------------------------------------------------------------


def port_is_free(port: int, host: str = "127.0.0.1", *, timeout: float = 0.3) -> bool:
    """Best-effort check: is anything already listening on `(host, port)`?

    A real TOCTOU race against a concurrent peer dispatch exists and is a disclosed, accepted
    residual (design's Open Question 4) — this check narrows the window, it does not close it.
    Never kills or hijacks whatever is already using the port; a positive result (occupied) must
    fail closed (`REJECTED`), never attempt to free the port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        return result != 0  # non-zero => connection failed => nothing listening => free


# ---------------------------------------------------------------------------
# Process start (step 4 — only after steps 1-3 all pass)
# ---------------------------------------------------------------------------


def start_process(start_command: str, *, shell: bool = False) -> subprocess.Popen:
    """Start `start_command` in its own process group.

    `start_new_session=True` is POSIX `setsid` equivalent — the child's PGID is set equal to its
    own PID synchronously, before `Popen()` returns, so tracking `proc.pid` as the PGID is not
    racy. Invoked via `shlex.split` + argv by default; `shell=True` is permitted only when the
    policy explicitly asks for it (the one named exception in the design), and no other
    task-derived field is ever concatenated into that same shell string by this function.
    """
    if shell:
        return subprocess.Popen(
            start_command,
            shell=True,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
    args = shlex.split(start_command)
    return subprocess.Popen(
        args,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def posix_process_group_capability_available() -> bool:
    """Best-effort auto-detection of the POSIX process-group primitives this module needs.

    A host without `os.setsid`/`os.killpg` (e.g. non-POSIX) gets the same capability-absent
    degraded path as any other missing capability (design's Components table, round 3). Callers
    (e.g. a test simulating a non-POSIX host) may ignore this and pass `capability_available`
    explicitly to :func:`run_app_run` instead.
    """
    return os.name == "posix" and hasattr(os, "killpg") and hasattr(os, "setsid")


# ---------------------------------------------------------------------------
# Readiness poll (liveness-aware)
# ---------------------------------------------------------------------------


@dataclass
class ReadinessResult:
    status: str  # "ready" | "exited_early" | "timed_out"
    exit_code: int | None = None


def poll_readiness(
    proc: subprocess.Popen,
    readiness_url: str,
    *,
    timeout_seconds: int,
    interval: float = DEFAULT_READINESS_POLL_INTERVAL_SECONDS,
) -> ReadinessResult:
    """Fixed-interval poll, up to `timeout_seconds`, checking BOTH readiness and liveness.

    Each tick checks process liveness (`proc.poll()`) FIRST: a process that crashed on boot fails
    fast with `EXITED_EARLY` (carrying its exit code) rather than polling a dead URL for the full
    timeout — the design's round-1 SRE fix. Only after confirming the process is still alive does
    this probe the readiness URL.
    """
    deadline = time.monotonic() + timeout_seconds
    while True:
        exit_code = proc.poll()
        if exit_code is not None:
            return ReadinessResult(status="exited_early", exit_code=exit_code)

        result = probe_url(readiness_url, method="GET")
        if result.ok:
            return ReadinessResult(status="ready")

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return ReadinessResult(status="timed_out")
        time.sleep(min(interval, remaining))


# ---------------------------------------------------------------------------
# Teardown (mandatory, every exit path)
# ---------------------------------------------------------------------------


@dataclass
class TeardownResult:
    confirmed_dead: bool
    escalated_to_sigkill: bool


def _process_group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # The group exists but we lack permission to signal it -- treat as still alive rather
        # than silently claiming success.
        return True


def teardown_process_group(
    proc: subprocess.Popen,
    *,
    grace_seconds: float = DEFAULT_TEARDOWN_GRACE_SECONDS,
) -> TeardownResult:
    """SIGTERM the tracked process group, wait `grace_seconds`, escalate to SIGKILL, recheck.

    Idempotent — tearing down an already-dead group is a no-op, never an error. This closes the
    common case (a direct child process, and any of its own direct forks that stayed in the same
    process group). It does **not** detect or kill a `start_command` that itself
    daemonizes/double-forks (calls `setsid` again internally) and so escapes the tracked group
    entirely — that is a named, disclosed, unclosed residual (design Open Question 5), not a bug
    in this function. When the tracked group still shows a live member after the SIGKILL
    escalation, `confirmed_dead` is False so the caller can report "teardown incomplete" rather
    than silently claiming success.
    """
    pgid = proc.pid
    escalated = False

    if _process_group_alive(pgid):
        try:
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass

        deadline = time.monotonic() + grace_seconds
        while time.monotonic() < deadline and _process_group_alive(pgid):
            time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))

        if _process_group_alive(pgid):
            escalated = True
            try:
                os.killpg(pgid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            kill_deadline = time.monotonic() + 2.0
            while time.monotonic() < kill_deadline and _process_group_alive(pgid):
                time.sleep(0.05)

    # Reap our own tracked child so a lingering zombie entry can't masquerade as "still alive" on
    # a later liveness check.
    try:
        proc.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        pass
    except Exception:  # pragma: no cover - defensive, e.g. already reaped
        pass

    return TeardownResult(
        confirmed_dead=not _process_group_alive(pgid),
        escalated_to_sigkill=escalated,
    )


# ---------------------------------------------------------------------------
# Screenshot path (outside the git worktree's tracked tree)
# ---------------------------------------------------------------------------


def resolve_screenshot_path(output_dir: Path | str, repo_root: Path | str | None = None) -> Path:
    """Return a path for the screenshot artifact, guaranteed not to be picked up by `git add`/
    `git status` for the worktree at `repo_root` (when given).

    If `output_dir` lives outside `repo_root` entirely (the common, recommended case — a sibling
    scratch directory), nothing further is needed. If `output_dir` happens to live inside the
    tracked worktree tree, a `.gitignore` entry scoped to just the screenshot filename is
    written/updated so an operator-error `git add -A` in Commit-and-publish cannot sweep it in.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = output_dir / SCREENSHOT_FILENAME

    if repo_root is not None:
        repo_root_resolved = Path(repo_root).resolve()
        try:
            output_dir.resolve().relative_to(repo_root_resolved)
            inside_repo = True
        except ValueError:
            inside_repo = False

        if inside_repo:
            gitignore_path = output_dir / ".gitignore"
            existing = gitignore_path.read_text(encoding="utf-8") if gitignore_path.exists() else ""
            if SCREENSHOT_FILENAME not in existing.splitlines():
                with gitignore_path.open("a", encoding="utf-8") as handle:
                    if existing and not existing.endswith("\n"):
                        handle.write("\n")
                    handle.write(f"{SCREENSHOT_FILENAME}\n")

    return screenshot_path


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------


@dataclass
class AppRunOutcome:
    status: str
    message: str
    screenshot_path: Path | None = None

    def render(self) -> str:
        """The single `app_run: <outcome>` string for the Builder's completion notes /
        `advisory_checks` — the same reporting channel `regression_gate.command` already
        established. Never a new run-log event."""
        return f"app_run: {self.message}"


def _run_lifecycle(
    proc: subprocess.Popen,
    process_policy: ProcessPolicy,
    *,
    want_screenshot: bool,
    screenshot_capability_available: bool,
    screenshot_fn: Callable[[Path | None], Path | None] | None,
    output_dir: Path | None,
    readiness_interval: float,
) -> AppRunOutcome:
    readiness = poll_readiness(
        proc,
        process_policy.readiness_url,
        timeout_seconds=process_policy.readiness_timeout_seconds,
        interval=readiness_interval,
    )
    if readiness.status == "exited_early":
        return AppRunOutcome(
            status="exited_early",
            message=f"process exited with code {readiness.exit_code} before becoming ready",
        )
    if readiness.status == "timed_out":
        return AppRunOutcome(
            status="timed_out",
            message=(
                "NEEDS_EVIDENCE — process never became ready within "
                f"{process_policy.readiness_timeout_seconds}s"
            ),
        )

    # Smoke test: an intentional, narrow re-confirmation after the Builder's own change lands —
    # reuses the same readiness_url, not a second independently-meaningful check.
    smoke = probe_url(process_policy.readiness_url, method="GET")
    if smoke.ok:
        status, message = "smoke_pass", "ready, smoke test passed"
    else:
        detail = smoke.status if smoke.status is not None else smoke.error
        status, message = "smoke_fail", f"smoke test failed (status {detail})"

    screenshot_path: Path | None = None
    if want_screenshot:
        if screenshot_capability_available and screenshot_fn is not None:
            try:
                screenshot_path = screenshot_fn(output_dir)
            except Exception as exc:  # defensive -- never let a screenshot failure mask the result
                message += f"; screenshot skipped — capture failed ({exc})"
            else:
                if screenshot_path is not None:
                    message += f"; screenshot saved at {screenshot_path}"
                else:
                    message += "; screenshot skipped — capability not available on this host"
        else:
            message += "; screenshot skipped — capability not available on this host"

    return AppRunOutcome(status=status, message=message, screenshot_path=screenshot_path)


def run_app_run(
    policy_raw: Any,
    *,
    capability_available: bool,
    screenshot_capability_available: bool = False,
    screenshot_fn: Callable[[Path | None], Path | None] | None = None,
    output_dir: Path | str | None = None,
    port_checker: Callable[[int], bool] | None = None,
    readiness_interval: float = DEFAULT_READINESS_POLL_INTERVAL_SECONDS,
    teardown_grace_seconds: float = DEFAULT_TEARDOWN_GRACE_SECONDS,
) -> AppRunOutcome:
    """Run the full `app_run` process lifecycle for one Builder dispatch.

    Explicit numbered check order (design's State machines section) — no process is ever started
    before steps 1-3 all pass:

    1. Capability-presence check -> `SKIPPED` if the whole process-tier capability is unavailable.
    2. `readiness_url` host/userinfo validation (after resolving/validating the policy itself)
       -> `REJECTED` if it fails.
    3. Port pre-start availability check -> `REJECTED` if occupied.
    4. Only then, process start.

    Teardown always runs (even if an exception is raised evaluating readiness/smoke/screenshot),
    covering every exit path.
    """
    output_dir_path = Path(output_dir) if output_dir is not None else None

    # (1) capability-presence check
    if not capability_available:
        return AppRunOutcome(status="skipped", message="skipped — capability not available on this host")

    policy = resolve_app_run_policy(policy_raw)
    if policy is None or policy.process is None:
        return AppRunOutcome(status="skipped", message="skipped — policy malformed or incomplete")

    process_policy = policy.process

    # (2) readiness_url host/userinfo validation
    if not validate_readiness_url(process_policy.readiness_url):
        return AppRunOutcome(status="rejected", message="rejected — readiness_url is not local")

    # (3) port pre-start availability check
    checker = port_checker or port_is_free
    if not checker(process_policy.port):
        return AppRunOutcome(
            status="rejected",
            message=f"port {process_policy.port} already in use, skipped",
        )

    # (4) process start — only after 1-3 all pass
    proc = start_process(process_policy.start_command, shell=process_policy.shell)

    outcome: AppRunOutcome
    try:
        outcome = _run_lifecycle(
            proc,
            process_policy,
            want_screenshot=policy.screenshot,
            screenshot_capability_available=screenshot_capability_available,
            screenshot_fn=screenshot_fn,
            output_dir=output_dir_path,
            readiness_interval=readiness_interval,
        )
    except Exception as exc:  # defensive: teardown (finally) must still run
        outcome = AppRunOutcome(status="error", message=f"unexpected error during app_run: {exc}")
    finally:
        teardown = teardown_process_group(proc, grace_seconds=teardown_grace_seconds)

    if not teardown.confirmed_dead:
        outcome = AppRunOutcome(
            status=outcome.status,
            message=(
                f"{outcome.message}; teardown incomplete — process group {proc.pid} still has a "
                "live member"
            ),
            screenshot_path=outcome.screenshot_path,
        )

    return outcome


# ---------------------------------------------------------------------------
# Minimal CLI (optional convenience — not required by any lint/test target)
# ---------------------------------------------------------------------------


def _load_policy_arg(raw_value: str) -> Any:
    try:
        return json.loads(raw_value)
    except (json.JSONDecodeError, TypeError):
        return raw_value  # hand the raw text to resolve_app_run_policy's YAML path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-file", required=True, help="Path to a JSON/YAML app_run policy file")
    parser.add_argument("--output-dir", default=".", help="Directory for the screenshot artifact, if any")
    parser.add_argument(
        "--capability-available",
        choices=("true", "false"),
        default="auto",
        help="Override POSIX process-group capability detection (default: auto-detect)",
    )
    args = parser.parse_args(argv)

    policy_text = Path(args.policy_file).read_text(encoding="utf-8")
    policy_raw = _load_policy_arg(policy_text)

    if args.capability_available == "auto":
        capability_available = posix_process_group_capability_available()
    else:
        capability_available = args.capability_available == "true"

    outcome = run_app_run(
        policy_raw,
        capability_available=capability_available,
        output_dir=args.output_dir,
    )
    print(outcome.render())
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
