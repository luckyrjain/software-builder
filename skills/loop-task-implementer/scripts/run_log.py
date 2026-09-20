#!/usr/bin/env python3
"""Append-only, redacted, hash-chained run log for loop-task-implementer.

The Orchestrator calls this script once per agent action so a run leaves a structured, redacted,
tamper-evident record that does not depend on the model's own summary. It also measures token and
active-time consumption for the current task, which is what makes the per-task budgets in
``reference/state-schema.yaml`` enforceable rather than aspirational.

Subcommands (see ``reference/run-log.md`` for the full contract):

    append     add one record            run_log.py append --run-id ID --event E --actor A [...]
    verify     check the whole chain     run_log.py verify --run-id ID
    summarize  run-level totals          run_log.py summarize --run-id ID
    budget     compare the current task's usage to its caps
                                         run_log.py budget --run-id ID [--max-tokens N|unlimited] ...
    run-id     derive a resumable id     run_log.py run-id      (JSON array of strings on stdin)

Exit codes: 0 ok; 1 integrity failure (chain broken, head mismatch, forged/out-of-order record);
2 bad input or the script could not run; 3 (``budget`` only) a cap is reached.

Storage: ``--log-dir`` (absolute) or ``<home>/.software-builder/runs``, one ``<run_id>.jsonl`` per run,
directory mode 0700, file mode 0600. The directory must not be inside a git repository, so a Builder
editing its working tree does not sit next to its own audit trail.

Threat model, stated plainly: the hash chain detects accidental corruption and casual edits, and
``--expect-head`` (the head hash from the previous receipt, held by the Orchestrator outside any file)
detects tail truncation, a wiped log, and appends by anyone else. It does NOT stop a process running as
the same OS user from rewriting the whole file, because that process can also run this script. Isolation
of the Builder from the log directory is what defends against that, not this file.

POSIX only (Linux, macOS): it needs ``flock`` and ``pread``, and refuses to run elsewhere rather than run unlocked.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import importlib.util
import json
import math
import os
import re
import stat
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import ModuleType
from typing import Any, Iterator, NamedTuple

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - not POSIX
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
# A log is written and read in the version of its first record. Adding an optional field or an event is
# a compatible change for readers of this version; anything else needs a new version listed here, with a
# reader for the old one kept, so archived and in-flight logs stay verifiable.
SUPPORTED_SCHEMA_VERSIONS = (1,)
ZERO_HASH = "0" * 64

# Defaults mirror reference/state-schema.yaml `budgets`; tests assert they stay equal.
DEFAULT_MAX_TASK_TOKENS = 2_000_000
DEFAULT_MAX_TASK_MINUTES = 180
# Time between two records counts at most this much, so a pause (a human decision, a resume the next
# day) does not consume the task's time budget. Matches the Orchestrator's per-session wait cap.
MAX_GAP_MINUTES = 30.0
CLOCK_SKEW_SECONDS = 300.0
FORGED_CLOCK_SECONDS = 86400.0  # a last record this far ahead is not clock skew
LOCK_TIMEOUT_SECONDS = 30.0
_LOCK_POLL_SECONDS = 0.05

EXIT_OK, EXIT_INTEGRITY, EXIT_ERROR, EXIT_BUDGET = 0, 1, 2, 3

EVENTS = (
    "run_started",
    "run_resumed",
    "task_selected",
    "builder_dispatched",
    "builder_returned",
    "pr_opened",
    "review_dispatched",
    "review_returned",
    "adjudicated",
    "remediation_dispatched",
    "remediation_returned",
    "orchestrator_usage",
    "ci_polled",
    "budget_checked",
    "escalated",
    "merge_attempted",
    "run_completed",
)
ACTORS = ("orchestrator", "builder", "reviewer", "ci", "human", "system")
OUTCOMES = ("COMPLETE", "ESCALATED", "HUMAN_ACTION_REQUIRED", "ABANDONED")

_USAGE_INT_FIELDS = ("input_tokens", "output_tokens", "total_tokens")
# Events whose record is where a session's token usage is supposed to appear.
PAUSE_EVENTS = ("run_completed",)
SESSION_RETURNS = ("builder_returned", "review_returned", "remediation_returned")
USAGE_EVENTS = ("builder_returned", "review_returned", "remediation_returned", "orchestrator_usage")
REASON_CODES = (
    "DIRTY_REVIEW_LIMIT", "FIX_ATTEMPT_LIMIT", "CONTESTED_TWICE", "SIZE_HARD_STOP", "FINGERPRINT_ALTERNATION",
    "SCOPE_EXCEEDED", "MISSING_DECISION", "THIRD_PARTY_CHANGE", "CI_UNDIAGNOSABLE", "SESSION_TIMEOUT",
    "TOKEN_BUDGET", "TIME_BUDGET", "OTHER",
)
_USAGE_FLOAT_FIELDS = ("elapsed_seconds", "cost_usd")
_USAGE_MAX = {
    "input_tokens": 10**10, "output_tokens": 10**10, "total_tokens": 10**10, "elapsed_seconds": 10**7, "cost_usd": 10**6,
}
_RUN_ID_RE = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]{0,127}")
_KEY_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_HASH_RE = re.compile(r"[0-9a-f]{64}")
_HEAD_RE = re.compile(r"[0-9a-f]{16,64}")  # a full head, or its first 16+ characters
_SENSITIVE_MARKER = "[REDACTED]"
# A key is judged by its WORDS (split on separators and camelCase), not by substrings: `passed`, `bypass`,
# `compass` and `max_tokens` are not secrets, `password`, `apiKey` and `DB_SECRET` are.
_STRONG_KEY_WORDS = frozenset(
    "password passwords passwd pwd pw passcode passphrase passphrases secret secrets apikey apikeys credential "
    "credentials creds authorization cookie cookies privatekey privatekeys jwt bearer accesskey accesskeys secretkey "
    "secretkeys sessionid sessionids dsn".split()
)
_WEAK_KEY_WORDS = frozenset({"token", "auth"})  # a text value is masked; a number under them is a count
_KEY_WORD_PAIRS = frozenset(
    {
        (a, b)
        for a in ("api", "private", "access", "secret", "signing", "master", "ssh", "encryption", "hmac", "auth")
        for b in ("key", "keys")
    }
    | {("session", "id"), ("session", "ids"), ("client", "secret"), ("client", "secrets"), ("database", "url")}
)
_PASS_PREFIXES = frozenset("db user admin root ssh smtp mysql redis ftp".split())


def _is_pass_key(words: list[str]) -> bool:
    """`pass`, `db_pass`, `prod_db_pass`, `dbpass`: a password, unlike `review_pass` or `pass_number`, which count."""
    joined = "".join(words)
    return joined == "pass" or (len(words) >= 2 and words[-1] == "pass" and words[-2] in _PASS_PREFIXES) or (
        joined.endswith("pass") and joined[:-4] in _PASS_PREFIXES
    )

_KEY_STEMS = ("password", "passwd", "passphrase", "credential", "apikey", "privatekey", "secretkey", "accesskey", "sessionkey", "keybase",
              "sshkey", "signingkey", "hmackey", "encryptionkey", "masterkey")
_CREDENTIAL_WORDS = (
    r"(?:(?:secret|token|passw(?:or)?d)(?:s|keys?|keybase|accesskey|values?|strings?|hash(?:es)?|salt)?|(?<![A-Za-z0-9])pass|(?:db|user|admin|root|ssh|smtp|mysql|redis|ftp)pass|pwd|passphrases?|api[_-]?keys?|(?:ssh|signing|hmac|encryption|master|private|access|app|license|subscription|functions|account)[_-]?keys?|cookies?|connect\.sid|passcode|psk|(?<![A-Za-z0-9])pw|(?<=[?&])sig|credentials?|creds|"
    r"sess(?:ion)?[_-]?(?:ids?|keys?)|signature|auth(?:orization)?)(?-i:(?![a-z]|[A-Z](?![a-z])))"
)
_CAMEL_RE = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+")

MAX_REDACT_INPUT_CHARS = 8000  # bound the regex work; a longer string is refused, never half-redacted
MAX_STRING_CHARS = 4000
MAX_RECORD_BYTES = 16 * 1024
MAX_DEPTH = 6
MAX_STDIN_BYTES = 64 * 1024
TAIL_WINDOW = 64 * 1024  # a record is capped at 16 KiB, so the last line always fits
_TRUNCATED = "...[truncated]"
_RECORD_FIELDS = frozenset(
    {"schema_version", "seq", "ts", "run_id", "event", "actor", "data", "usage", "redactions", "prev_hash", "hash"}
)


class IntegrityError(ValueError):
    """The log (or what the caller expected of it) is not what it should be: exit 1, not 2."""


class NoLogError(ValueError):
    """There is no usable log for this run id."""


class VerifyResult(NamedTuple):
    ok: bool
    events: int
    head: str
    errors: list[str]
    last_event: str | None = None
    recoverable: bool = False  # the only problem is a torn final line that the next append repairs
    unanchored_resumes: int = 0  # `run_resumed` records that continued without a held head
    ahead_by: int = 0  # diagnostic: the log is intact and holds this many records after the head that was supplied


class _Tail(NamedTuple):
    seq: int
    head: str
    ts: datetime | None
    completed: bool
    truncate_to: int | None  # drop an unparseable partial final line back to this size
    add_newline: bool  # the final line is a complete, valid record that only lacks its newline
    last: dict[str, Any] | None = None  # the last complete record, if any


# --- redaction --------------------------------------------------------------------------------

_REDACTION: ModuleType | None = None
_PATTERNS: tuple[Any, ...] | None = None


def _redaction_runtime() -> ModuleType:
    global _REDACTION
    if _REDACTION is None:
        _REDACTION = _shared_runtime_loader().load_shared_runtime(
            SKILL_ROOT,
            "redaction",
            alias="loop_shared_redaction",
            description=_RUNTIME_DESCRIPTION,
        )
    return _REDACTION


def _patterns(redaction: ModuleType) -> tuple[Any, ...]:
    """The shared log profile (which keeps email-shaped cloud identities readable, per redaction.py's
    own rationale) plus token families it does not cover yet. Worth upstreaming to redaction.py; kept
    local so this change does not alter what incident-rca and prd-architect redact."""
    global _PATTERNS
    if _PATTERNS is None:

        def token(name: str, regex: str, category: str = "token") -> Any:
            return redaction.RedactionPattern(
                name=name, pattern=re.compile(regex), replacement="{marker}", category=category
            )

        extras = (
            token("github_token_any", r"gh[pousr]_[A-Za-z0-9]{36}"),
            token("gitlab_pat", r"glpat-[A-Za-z0-9_-]{20,}"),
            token("slack_token", r"xox[abprs]-[A-Za-z0-9-]{10,}"),
            token("npm_token", r"npm_[A-Za-z0-9]{36}"),
            token("google_api_key", r"AIza[A-Za-z0-9_-]{35}"),
            token("stripe_live_key", r"[sr]k_live_[A-Za-z0-9]{16,}"),
            token("aws_key_id_any", r"(?<![A-Z0-9])(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{16}(?![A-Z0-9])"),
            redaction.RedactionPattern(
                name="url_userinfo",
                pattern=re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)(?:[^\s/@:]*:[^\s/]+|[^\s/@:]{20,})@"),
                replacement=r"\1{marker}@",
                category="secret",
            ),
            token("huggingface_token", r"hf_[A-Za-z0-9]{30,}"),
            token("digitalocean_token", r"dop_v1_[a-f0-9]{40,}"),
            token("sentry_token", r"sntrys_[A-Za-z0-9+/=_-]{30,}"),
            redaction.RedactionPattern(
                name="authorization_scheme",
                pattern=re.compile(r"(?i)(authorization\s*[:=]\s*[A-Za-z][A-Za-z0-9_-]*\s+)[A-Za-z0-9._~+/=-]{8,}"),
                replacement=r"\1{marker}",
                category="token",
            ),
            redaction.RedactionPattern(
                name="cli_user_flag",
                pattern=re.compile(r"(?i)(\s-(?:u[ =]?|-user[ =]))[^\s:]+:\S+"),
                replacement=r"\1{marker}",
                category="secret",
            ),
            token("azure_account_key", r"AccountKey=[A-Za-z0-9+/=]{20,}", "secret"),
            token("twilio_key", r"SK[0-9a-f]{32}"),
            token("databricks_pat", r"dapi[0-9a-f]{32}"),
            token("atlassian_token", r"ATATT[A-Za-z0-9_=-]{20,}"),
            token("sendgrid_key", r"SG\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}"),
            token("shopify_token", r"shp(?:at|ca|pa)_[0-9a-f]{32}"),
            token("pypi_token", r"pypi-[A-Za-z0-9_-]{30,}"),
            token("stripe_webhook_secret", r"whsec_[A-Za-z0-9]{24,}"),
            token("groq_key", r"gsk_[A-Za-z0-9]{40,}"),
            token("xai_key", r"xai-[A-Za-z0-9]{40,}"),
            token("perplexity_key", r"pplx-[A-Za-z0-9]{30,}"),
            token("vault_token", r"hvs\.[A-Za-z0-9_-]{20,}"),
            token("docker_pat", r"dckr_pat_[A-Za-z0-9_-]{20,}"),
            token("google_oauth_token", r"ya29\.[A-Za-z0-9_-]{20,}"),
            token("slack_webhook", r"https://hooks\.slack\.com/services/[A-Za-z0-9/]{20,}"),
            token("discord_webhook", r"discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_-]{20,}"),
            token("azure_sas_signature", r"SharedAccessSignature\s+[^\s]{20,}", "secret"),
            token("pem_private_key_open", r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*", "secret"),
            redaction.RedactionPattern(
                name="secretish_kv",
                pattern=re.compile(
                    r"(?i)\b(?P<key>[A-Za-z0-9_.-]{0,64}" + _CREDENTIAL_WORDS + r"[A-Za-z0-9_.-]{0,64})"
                    r"(?P<sep>\s*[:=]\s*)[\"']?(?!unlimited\b)"
                    r"(?P<value>[^\s\"',;&?]{8,})"
                ),
                replacement=lambda m, marker: (
                    f"{m.group('key')}{m.group('sep')}{marker}" if _secret_shaped(m.group("value"), m.group("key")) else None
                ),
                category="secret",
            ),
            redaction.RedactionPattern(
                name="secretish_json",
                pattern=re.compile(
                    r'(?i)(?P<head>(?<!\\)\\*["\'](?P<key>[A-Za-z0-9_.-]{0,64}' + _CREDENTIAL_WORDS + r'[A-Za-z0-9_.-]{0,64})\\*["\']\s*:\s*\\*(?P<q>["\']))'
                    r'(?P<value>(?:(?!(?P=q))[^\\]){8,})(?P<tail>\\*(?P=q))'
                ),
                replacement=lambda m, marker: (
                    f"{m.group('head')}{marker}{m.group('tail')}" if _secret_shaped(m.group("value"), m.group("key")) else None
                ),
                category="secret",
            ),
            redaction.RedactionPattern(
                name="secretish_name_value",
                pattern=re.compile(
                    r'(?i)(?P<head>["\']?name["\']?[ \t]*[:=][ \t]*["\']?[A-Za-z0-9_.-]{0,64}' + _CREDENTIAL_WORDS
                    + r'[A-Za-z0-9_.-]{0,64}["\']?[\s,]*["\']?value["\']?[ \t]*[:=][ \t]*(?P<q>["\']?))'
                    r'(?P<value>(?(q)[^"\'\r\n]{6,}|[^\s"\',}]{6,}))'
                ),
                replacement=lambda m, marker: f"{m.group('head')}{marker}",
                category="secret",
            ),
            redaction.RedactionPattern(
                name="secretish_xml",
                pattern=re.compile(r"(?i)(<[A-Za-z0-9_.-]{0,64}" + _CREDENTIAL_WORDS + r"[A-Za-z0-9_.-]{0,64}>)([^<\s]{6,})(</)"),
                replacement=r"\1{marker}\3",
                category="secret",
            ),
            redaction.RedactionPattern(
                name="secretish_spaced",
                pattern=re.compile(
                    r"(?i)(\b(?:aws_)?(?:secret_access_key|session_token)\s+|\b_auth(?:token)?\s+|\blogin\s+\S+\s+password\s+)\S{8,}"
                ),
                replacement=r"\1{marker}",
                category="secret",
            ),
            redaction.RedactionPattern(
                name="secretish_flag",
                pattern=re.compile(
                    r"(?i)((?<![A-Za-z0-9])--?[a-z0-9_-]{0,40}(?:password|passwd|pwd|pw|(?<![a-z])pass|(?:db|user|admin|root|ssh|smtp|mysql|redis|ftp)pass|cookies?|passphrase|token|secret|api[_-]?key|secret[_-]?access[_-]?key|secret[_-]?key"
                    r"|access[_-]?key|private[_-]?key|session[_-]?(?:id|key)|keybase|jwt|credentials?|auth"
                    r"|(?:encryption|signing|master|hmac|auth|account)[_-]?key|authkey|secret[_-]?(?:string|id|value)|storepass|keypass|passcode|psk)[ =])[^\s]{6,}"
                ),
                replacement=r"\1{marker}",
                category="secret",
            ),
            redaction.RedactionPattern(
                name="cookie_header",
                pattern=re.compile(r"(?i)\b((?:set-)?cookie\s*:\s*)[^\r\n]+"),
                replacement=r"\1{marker}",
                category="secret",
            ),
        )
        # Ours run first: the shared `Bearer <chars>=*` pattern would otherwise eat an `api_token=` (or
        # `AccountKey=`) prefix and leave the value behind.
        _PATTERNS = (
            *extras,
            *redaction.LOG_PATTERNS,
            *(p for p in redaction.DOCUMENT_PATTERNS if p.name != "email"),  # generic key=value credentials
        )
    return _PATTERNS


def _clean_text(text: str, hits: set[str]) -> str:
    if len(text) > MAX_REDACT_INPUT_CHARS:
        # Cutting before redacting can leave half a secret; identifiers and counts are short, so refuse.
        raise ValueError(f"a string longer than {MAX_REDACT_INPUT_CHARS} characters; log identifiers and counts, not content")
    redaction = _redaction_runtime()
    redacted, found = redaction.redact(
        text, patterns=_patterns(redaction), marker=redaction.DEFAULT_MARKER, passes=1
    )
    hits.update(hit.name for hit in found)
    # A later shared pattern can re-match the marker one of ours just wrote and leave its closing bracket behind.
    redacted = re.sub(re.escape(redaction.DEFAULT_MARKER) + r"\]+", redaction.DEFAULT_MARKER, redacted)
    if len(redacted) > MAX_STRING_CHARS:
        redacted = redacted[: MAX_STRING_CHARS - len(_TRUNCATED)] + _TRUNCATED
    return redacted


def _sanitize(value: Any, hits: set[str], depth: int = 0, key: str | None = None) -> Any:
    if depth > MAX_DEPTH:
        raise ValueError(f"data nests deeper than {MAX_DEPTH} levels")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("data contains a non-finite number")
    if value is None or isinstance(value, bool):
        return value
    strength = _key_strength(key) if key is not None else 0
    if (
        key is not None and isinstance(value, str) and re.search(r"(?i)tokens$", key)
        and re.fullmatch(r"[A-Za-z0-9+/_=.~-]{12,}", value) and _secret_shaped(value, key)
    ):
        strength = 1  # `tokens` is usually a count, but a random-looking string under it is a credential
    counted = isinstance(value, (int, float)) and _is_count_key(key or "")
    if (strength == 2 and not counted) or (strength == 1 and not isinstance(value, (int, float))):
        hits.add("sensitive_key")
        return _SENSITIVE_MARKER  # whatever shape the value has, its key says it is a secret
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return _clean_text(value, hits)
    if isinstance(value, list):
        return [_sanitize(item, hits, depth + 1, key=key if key and re.search(r"(?i)tokens$", key) else None) for item in value]
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for name, item in value.items():
            if not isinstance(name, str) or not _KEY_RE.fullmatch(name):
                raise ValueError(f"data key {_short(name)} must match {_KEY_RE.pattern}")
            scratch: set[str] = set()
            if _clean_text(name, scratch) != name:
                raise ValueError("a data key looks like a secret; keys must be plain field names")
            cleaned[name] = _sanitize(item, hits, depth + 1, key=name)
        return cleaned
    raise ValueError(f"data contains a non-JSON value of type {type(value).__name__}")


# --- validation helpers -----------------------------------------------------------------------


def _short(value: object) -> str:
    """Describe a value that came from a file or a caller without quoting it. Untrusted text that reaches
    the model is an injection channel, and even a 60-character excerpt is enough for one, so a string is
    reduced to its length and a short digest (enough to tell two apart); a number or bool is safe to show."""
    if isinstance(value, str):
        return f"<text len={len(value)} sha={hashlib.sha256(value.encode('utf-8', 'replace')).hexdigest()[:8]}>"
    if isinstance(value, (bool, int, float)) or value is None:
        return repr(value)[:24]
    return f"<{type(value).__name__}>"


def _is_count_key(key: str) -> bool:
    words = [word.lower() for word in _CAMEL_RE.findall(key)]
    return bool(words) and words[-1] in {
        "count", "total", "limit", "size", "found", "detected", "rotated", "scanned", "leaked", "used", "issued", "expired",
        "length", "min", "max", "age",
    }


def _credential_named(key: str) -> bool:
    """A key that names a credential itself (`api_key`, `SECRET_KEY`, `client_secret`, `db_password`), as opposed to
    one that merely mentions the word (`secret_scan`, `token_source`)."""
    words = [word.lower() for word in _CAMEL_RE.findall(key)]
    if not words:
        return False
    joined = "".join(words)
    if _is_pass_key(words):
        return True
    return (
        words[-1] in _STRONG_KEY_WORDS
        or words[-1] == "token"  # `api_token`, `authToken`, `token`: a token itself, unlike `tokens` (usually a count)
        or (words[-1] in {"key", "keys"} and any(pair in _KEY_WORD_PAIRS for pair in zip(words, words[1:])))
        or joined.endswith(("secret", "secrets", "password", "apikey", "secretkey", "privatekey", "sessionkey", "keybase",
                            "sshkey", "signingkey", "hmackey", "encryptionkey", "masterkey"))
    )


def _secret_shaped(value: str, key: str = "") -> bool:
    """Whether a value after a credential-named key should be masked: anything of credential length and
    charset that is not clearly an identifier. Kebab/snake-case words (`enabled-by-default`,
    `cl100k_base_tokenizer_v2`), ALL_CAPS codes (`E_AUTH_TOKEN_EXPIRED_0042`) and absolute paths are what
    such keys usually hold in an audit trail (`secret_scan=completed-no-findings-detected`); a secret is
    almost never shaped like that. Human-chosen passwords and random keys are both masked."""
    if re.fullmatch(r"\d{4}-\d\d-\d\d(?:[T ]\d\d(?::\d\d(?::\d\d(?:\.\d+)?)?)?(?:Z|[+-]\d\d:?\d\d)?)?", value):
        return False  # a date or timestamp
    if re.match(r"(?i)https?://[^\s@]*$", value) or value.startswith(("./", "../", "~/")) or value.isdigit():
        return False  # a URL without userinfo, a path, a number
    if re.fullmatch(r"/[\w.@%~-]+(?:/[\w.@%~-]+)+/?", value):
        return False  # an absolute path: at least two segments and none of the characters base64 adds (+ =)
    if not re.fullmatch(r"[A-Za-z0-9+/_=.~-]+", value):
        return True  # punctuation is what human-chosen passwords are made of
    if len(value) < 12 and not (len(value) >= 8 and _credential_named(key)):
        return False
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", value):
        return True  # a UUID under a credential key is a session or API identifier
    if any(len(seg) >= 8 and re.search(r"\d", seg) and re.search(r"[A-Za-z]", seg) for seg in re.split(r"[-_.]", value)):
        return True  # a long segment that mixes letters and digits looks random, not like a word
    if _credential_named(key):
        return True  # `secret_key=my-app-secret-value`: a phrase or a word chain is a credential here
    if re.fullmatch(r"[a-z][a-z0-9]*(?:[-_.][a-z0-9]+)+", value) or re.fullmatch(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+", value):
        return False
    return True


def _key_strength(key: str) -> int:
    """0 not sensitive, 1 weak (mask text values), 2 strong (mask any value)."""
    words = [word.lower() for word in _CAMEL_RE.findall(key)]
    if not words:
        return 0  # a key such as `_` or `-` has no words
    if any(word in _STRONG_KEY_WORDS for word in words) or any(pair in _KEY_WORD_PAIRS for pair in zip(words, words[1:])):
        return 2
    joined = "".join(words)  # `clientsecret`, `dbpassword`, `accesstoken`: one word to the splitter, two to a reader
    if _is_pass_key(words):
        return 2
    if any(stem in joined for stem in _KEY_STEMS) or joined.endswith(("secret", "secrets")):
        return 2
    if any(word in _WEAK_KEY_WORDS for word in words) or joined.endswith(("token", "auth")):
        return 1
    return 0


def validate_run_id(run_id: object) -> str:
    if not isinstance(run_id, str) or not _RUN_ID_RE.fullmatch(run_id) or run_id in {".", ".."}:
        raise ValueError("run_id must be 1-128 characters of [A-Za-z0-9._-], not starting with '-'")
    return run_id


def _validate_usage(usage: object) -> dict[str, int | float]:
    if usage is None:
        return {}
    if not isinstance(usage, dict):
        raise ValueError("usage must be an object")
    unknown = sorted(set(usage) - set(_USAGE_INT_FIELDS) - set(_USAGE_FLOAT_FIELDS))
    if unknown:
        raise ValueError(f"unknown usage field(s): {_short(', '.join(str(u) for u in unknown))}")
    cleaned: dict[str, int | float] = {}
    for key, value in usage.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"usage.{key} must be a number")
        if key in _USAGE_INT_FIELDS and not isinstance(value, int):
            raise ValueError(f"usage.{key} must be an integer")
        if not math.isfinite(value) or value < 0 or value > _USAGE_MAX[key]:
            raise ValueError(f"usage.{key} must be finite, non-negative, and at most {_USAGE_MAX[key]}")
        cleaned[key] = value
    if "total_tokens" in cleaned and cleaned["total_tokens"] < cleaned.get("input_tokens", 0) + cleaned.get("output_tokens", 0):
        raise ValueError("usage.total_tokens is smaller than input_tokens + output_tokens")
    return cleaned


def _tokens_of(usage: dict[str, Any]) -> int:
    """A record's tokens: the host's total if it gave one, else input + output."""
    if "total_tokens" in usage:
        return int(usage["total_tokens"])
    return int(usage.get("input_tokens", 0)) + int(usage.get("output_tokens", 0))


def _has_token_usage(usage: dict[str, Any]) -> bool:
    """Real usage is non-zero: an all-zero record is a placeholder, not a measurement."""
    return any(usage.get(key, 0) > 0 for key in _USAGE_INT_FIELDS)


def _validate_event_data(event: str, data: dict[str, Any]) -> None:
    """Free prose is the injection channel, so the two events that invite it take codes, not sentences."""
    if event == "escalated" and data.get("reason") not in REASON_CODES:
        raise ValueError(f"escalated needs data.reason, one of: {', '.join(REASON_CODES)}")
    if event == "task_selected" and not (isinstance(data.get("task_id"), str) and data["task_id"]):
        raise ValueError("task_selected needs data.task_id, the task's id: it is what the per-task budget is counted against")
    if event == "run_completed" and data.get("outcome") not in OUTCOMES:
        raise ValueError(f"run_completed needs data.outcome, one of: {', '.join(OUTCOMES)}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _fmt_ts(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _parse_ts(ts: object) -> datetime:
    if not isinstance(ts, str):
        raise ValueError(f"invalid timestamp {_short(ts)}")
    try:
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"invalid timestamp {_short(ts)}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"timestamp {_short(ts)} has no timezone")
    return parsed


def _canonical(record: dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _record_hash(record: dict[str, Any]) -> str:
    body = {key: value for key, value in record.items() if key != "hash"}
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {_short(key)}")
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ValueError(f"non-finite JSON constant {name}")


def strict_loads(text: str) -> Any:
    """json.loads that refuses duplicate keys (last-wins would let two parsers disagree) and NaN/Infinity."""
    return json.loads(text, object_pairs_hook=_no_duplicate_keys, parse_constant=_reject_constant)


def _record_shape_errors(record: dict[str, Any], run_id: str) -> list[str]:
    errors: list[str] = []
    unknown = sorted(set(record) - _RECORD_FIELDS)
    missing = sorted(_RECORD_FIELDS - set(record))
    if unknown:
        errors.append(f"unknown field(s) {_short(', '.join(unknown))}")
    if missing:
        errors.append(f"missing field(s) {', '.join(missing)}")
        return errors
    if type(record["schema_version"]) is not int or record["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
        errors.append(f"unsupported schema_version {_short(record['schema_version'])}")
    if type(record["seq"]) is not int or record["seq"] < 1:
        errors.append(f"seq {_short(record['seq'])} is not a positive integer")
    if record["run_id"] != run_id:
        errors.append(f"run_id {_short(record['run_id'])} does not match this run")
    if record["event"] not in EVENTS:
        errors.append(f"unknown event {_short(record['event'])}")
    if record["actor"] not in ACTORS:
        errors.append(f"unknown actor {_short(record['actor'])}")
    try:
        _parse_ts(record["ts"])
    except ValueError as exc:
        errors.append(str(exc))
    if not isinstance(record["data"], dict):
        errors.append("data is not an object")
    try:
        if _validate_usage(record["usage"]) != record["usage"]:
            errors.append("usage is not in normalized form")
    except ValueError as exc:
        errors.append(str(exc))
    redactions = record["redactions"]
    if not isinstance(redactions, list) or not all(isinstance(item, str) for item in redactions):
        errors.append("redactions is not a list of strings")
    for field in ("prev_hash", "hash"):
        if not isinstance(record[field], str) or not _HASH_RE.fullmatch(record[field]):
            errors.append(f"{field} is not a SHA-256 hex digest")
    return errors


def _transition_error(seq: int, event: str, completed: bool) -> str | None:
    if seq == 1 and event != "run_started":
        return f"the first record must be run_started, not {event}"
    if seq > 1 and event == "run_started":
        return "run_started may only be the first record (use run_resumed to continue a run)"
    if completed and event != "run_resumed":
        return f"{event} after run_completed; only run_resumed may continue a completed run"
    return None


# --- storage ----------------------------------------------------------------------------------


def _home_dir() -> Path:
    """The account's home directory, not $HOME: the environment is not a place to take a log location from."""
    try:
        import pwd

        return Path(pwd.getpwuid(os.geteuid()).pw_dir)
    except (ImportError, KeyError):  # pragma: no cover - Windows / odd accounts
        return Path.home()


def _within(child: str, parent: str) -> bool:
    child_real, parent_real = os.path.realpath(child), os.path.realpath(parent)
    try:
        return os.path.commonpath([child_real, parent_real]) == parent_real
    except ValueError:
        return False


def _is_repo_root(path: Path) -> bool:
    """A real git repository root, not a stub `.git` an attacker planted to make the check misfire."""
    git = path / ".git"
    try:
        if git.is_file():
            return git.read_text(encoding="utf-8", errors="ignore").startswith("gitdir:")
        if git.is_dir():
            return (git / "HEAD").is_file()
        return (path / "HEAD").is_file() and (path / "objects").is_dir() and (path / "refs").is_dir()  # bare
    except OSError:
        return False


def _enclosing_repo(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if _is_repo_root(candidate):
            return candidate
    return None


def _refuse_repository(directory: Path) -> None:
    """Refuse a directory that sits inside any git repository, whatever the current directory is.

    Asking the filesystem (does an ancestor hold a `.git`, is an ancestor the same file as the cwd's repo)
    rather than comparing path strings is what survives case-insensitive filesystems and symlinks.
    """
    chain = [Path(os.path.realpath(directory))]
    chain.extend(chain[0].parents)
    for ancestor in chain:
        if _is_repo_root(ancestor):
            raise ValueError(f"the run log directory must be outside any git repository (found one at {ancestor})")
    known = [repo for repo in (_enclosing_repo(Path.cwd().resolve()),) if repo is not None]
    known += [Path(value) for value in (os.environ.get("GIT_DIR"), os.environ.get("GIT_WORK_TREE")) if value]
    if os.environ.get("GIT_DIR") and not os.environ.get("GIT_WORK_TREE"):
        known.append(Path.cwd())  # git treats the current directory as the work tree in that case
    for repo in known:
        for ancestor in chain:
            try:
                if ancestor.exists() and repo.exists() and os.path.samefile(ancestor, repo):
                    raise ValueError(f"the run log directory must be outside the repository at {repo}")
            except OSError:
                continue


def resolve_log_dir(explicit: str | os.PathLike[str] | None) -> Path:
    """The directory the log may live in: absolute, no ``..``, and outside every git repository."""
    if explicit is not None and str(explicit) == "":
        raise ValueError("--log-dir must not be empty")
    raw = str(explicit) if explicit else ""
    if raw.startswith("~") and raw != "~" and not raw.startswith("~/"):
        raise ValueError("only a plain '~' (this account's home) is supported in --log-dir, not ~user")
    directory = (
        _home_dir() / raw[2:] if raw.startswith("~/") else _home_dir() if raw == "~"
        else Path(raw) if raw else _home_dir() / ".software-builder" / "runs"
    )
    if not directory.is_absolute():
        raise ValueError(f"the run log directory must be an absolute path, got {str(directory)!r}")
    if ".." in directory.parts:
        raise ValueError("the run log directory must not contain '..'")
    _refuse_repository(directory)
    return directory


def log_path(log_dir: Path, run_id: str) -> Path:
    validate_run_id(run_id)
    directory = Path(log_dir)
    path = directory / f"{run_id}.jsonl"
    if not _within(str(path), str(directory)) or os.path.realpath(path.parent) != os.path.realpath(directory):
        raise ValueError("the run log path escapes its directory")
    return path


def _private_dir(directory: Path) -> None:
    """Create `directory` (and the missing parents) private to this user; refuse one that already exists and is
    reachable by others, is not ours, or is the home directory (it is not ours to chmod)."""
    if directory.is_symlink():
        raise OSError(f"refusing to use a symlinked log directory: {directory}")
    missing: list[Path] = []
    probe = directory
    while not probe.exists() and probe != probe.parent:
        missing.append(probe)
        probe = probe.parent
    for created in reversed(missing):  # makedirs(mode=) only applies to the leaf, so do each level
        try:
            os.mkdir(created, 0o700)
        except FileExistsError:
            pass
    info = os.lstat(directory)
    if not os.path.isdir(directory) or directory.is_symlink():
        raise OSError(f"not a directory: {directory}")
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise OSError(f"refusing to use a log directory owned by another user: {directory}")
    if info.st_mode & 0o077:
        # Not ours to chmod: a directory that already exists (a home directory, a shared folder) may hold other
        # things, and tightening it would change who can reach them. Only directories this call created are 0700.
        raise OSError(f"the log directory is accessible to others; make it 0700 yourself or choose another: {directory}")
    try:
        is_home = os.path.samefile(directory, _home_dir())
    except OSError:  # an account whose home directory was never created cannot be the log directory
        is_home = False
    if is_home:
        raise OSError("refusing to use the home directory itself as the log directory")


@contextmanager
def _locked(fd: int, *, exclusive: bool) -> Iterator[None]:
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise OSError(f"timed out after {LOCK_TIMEOUT_SECONDS:.0f}s waiting for the run log lock") from None
            time.sleep(_LOCK_POLL_SECONDS)
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)


def _read_all(fd: int) -> bytes:
    chunks = []
    offset = 0
    while True:
        chunk = os.pread(fd, 1 << 20, offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def _fsync(fd: int) -> None:
    """Flush to the device: macOS `fsync` only reaches the drive's cache, `F_FULLFSYNC` goes further."""
    full = getattr(fcntl, "F_FULLFSYNC", None)
    if full is not None:
        try:
            fcntl.fcntl(fd, full)
            return
        except OSError:
            pass
    os.fsync(fd)


def _open_private(path: Path, flags: int) -> int:
    # O_NONBLOCK so a FIFO planted at the log path cannot hang the open; only regular files are accepted.
    fd = os.open(path, flags | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0), 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise OSError(f"the run log path is not a regular file: {path}")
        if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
            raise OSError(f"refusing to use a run log owned by another user: {path}")
        if info.st_mode & 0o077 and flags & (os.O_WRONLY | os.O_RDWR):  # readers tolerate a loose or read-only copy
            os.fchmod(fd, 0o600)
    except BaseException:
        os.close(fd)
        raise
    return fd


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write to the run log")
        view = view[written:]


def _fsync_dir(directory: Path) -> None:
    try:
        dir_fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(dir_fd)
    except OSError:  # pragma: no cover - some filesystems refuse it
        pass
    finally:
        os.close(dir_fd)


# --- chain checking ---------------------------------------------------------------------------


def _parse_line(raw: bytes, index: int) -> tuple[dict[str, Any] | None, str | None]:
    if len(raw) > MAX_RECORD_BYTES:
        return None, f"line {index}: longer than any valid record"
    try:
        text = raw.decode("utf-8")
        record = strict_loads(text)
    except (UnicodeDecodeError, ValueError, RecursionError, MemoryError) as exc:
        return None, f"line {index}: {_short(str(exc))}"
    if not isinstance(record, dict):
        return None, f"line {index}: record is not an object"
    if _canonical(record) != text:
        return None, f"line {index}: not in canonical form"
    return record, None


def _full_check(raw: bytes, run_id: str) -> tuple[VerifyResult, list[dict[str, Any]]]:
    errors: list[str] = []
    records: list[dict[str, Any]] = []
    head = ZERO_HASH
    prev_ts: datetime | None = None
    completed = False
    torn = bool(raw) and not raw.endswith(b"\n")
    if torn:
        errors.append("log does not end with a newline (a torn final write; the next append repairs a fragment under 48 KiB)")
    lines = raw.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    elif torn and _parse_line(lines[-1], len(lines))[0] is None:
        lines.pop()  # an unparseable final line is reported once, as the torn write it is
    now_limit = _now() + timedelta(seconds=FORGED_CLOCK_SECONDS)
    for index, line in enumerate(lines, start=1):
        record, problem = _parse_line(line, index)
        if record is None:
            errors.append(problem or f"line {index}: unreadable")
            continue
        shape = _record_shape_errors(record, run_id)
        errors.extend(f"line {index}: {message}" for message in shape)
        if shape:
            continue
        if record["seq"] != index:
            errors.append(f"line {index}: seq {record['seq']!r} breaks the sequence")
        if record["prev_hash"] != head:
            errors.append(f"line {index}: prev_hash does not match the previous record's hash")
        if record["hash"] != _record_hash(record):
            errors.append(f"line {index}: hash does not match record contents")
        moment = _parse_ts(record["ts"])
        if prev_ts is not None and moment < prev_ts:
            errors.append(f"line {index}: timestamp goes backwards")
        if moment > now_limit:
            errors.append(f"line {index}: timestamp is far in the future")
        problem = _transition_error(index, record["event"], completed)
        if problem:
            errors.append(f"line {index}: {problem}")
        if record["event"] == "run_completed":
            completed = True
        elif record["event"] == "run_resumed":
            completed = False
        prev_ts = moment
        head = record["hash"]
        records.append(record)
    ok = not errors and bool(records)
    recoverable = torn and len(errors) == 1 and len(raw) - raw.rfind(b"\n") - 1 < TAIL_WINDOW - MAX_RECORD_BYTES
    result = VerifyResult(
        ok, len(records), head, errors or ([] if records else ["log is empty"]),
        records[-1]["event"] if records else None, recoverable,
        sum(1 for record in records if record["data"].get("unanchored") is True),
    )
    return result, records


def _tail_state(fd: int, size: int, run_id: str) -> _Tail:
    """What the next append must chain from, read from the end of the file only (append stays O(1) in
    the log's length). Full-chain verification is `verify`'s job."""
    if size == 0:
        return _Tail(0, ZERO_HASH, None, False, None, False, None)
    window = min(size, TAIL_WINDOW)
    buf = os.pread(fd, window, size - window)
    base = size - window
    truncate_to: int | None = None
    add_newline = False

    def last_records(data: bytes) -> list[dict[str, Any]]:
        parsed: list[dict[str, Any]] = []
        lines = data.split(b"\n")
        if lines and lines[-1] == b"":
            lines.pop()
        if window < size and lines:
            lines = lines[1:]  # the first line of a partial window may be cut off
        for number, line in enumerate(lines, start=1):
            record, problem = _parse_line(line, number)
            if record is None:
                raise IntegrityError(f"cannot chain from the tail of the log: {problem}")
            parsed.append(record)
        return parsed

    fragment = b""
    if not buf.endswith(b"\n"):
        cut = buf.rfind(b"\n")
        if cut == -1 and window < size:
            raise IntegrityError("the final line of the log is longer than any valid record; it cannot be repaired by an append")
        fragment = buf[cut + 1 :]
        buf = buf[: cut + 1]
    prior = last_records(buf) if buf else []
    tail_seq, tail_head, tail_ts = 0, ZERO_HASH, None
    if prior:
        last = prior[-1]
        shape = _record_shape_errors(last, run_id)
        if shape or last["hash"] != _record_hash(last):
            raise IntegrityError("the last record of the log does not verify: " + "; ".join(shape or ["bad hash"]))
        tail_seq, tail_head, tail_ts = last["seq"], last["hash"], _parse_ts(last["ts"])
    elif base > 0:
        raise IntegrityError("cannot locate the last record in the tail window")

    if fragment:
        record, _problem = _parse_line(fragment, tail_seq + 1)
        valid = (
            record is not None
            and not _record_shape_errors(record, run_id)
            and record["seq"] == tail_seq + 1
            and record["prev_hash"] == tail_head
            and record["hash"] == _record_hash(record)
        )
        if valid:
            add_newline = True
            tail_seq, tail_head, tail_ts = record["seq"], record["hash"], _parse_ts(record["ts"])
            prior = [*prior, record]
        else:
            truncate_to = size - len(fragment)

    completed = bool(prior) and prior[-1]["event"] == "run_completed"
    return _Tail(tail_seq, tail_head, tail_ts, completed, truncate_to, add_newline, prior[-1] if prior else None)


def _make_record(
    seq: int, prev_hash: str, run_id: str, event: str, actor: str, data: dict[str, Any],
    usage: dict[str, int | float], hits: set[str], moment: datetime,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "seq": seq,
        "ts": _fmt_ts(moment),
        "run_id": run_id,
        "event": event,
        "actor": actor,
        "data": data,
        "usage": usage,
        "redactions": sorted(hits),
        "prev_hash": prev_hash,
    }
    record["hash"] = _record_hash(record)
    line = _canonical(record)
    if len(line.encode("utf-8")) + 1 > MAX_RECORD_BYTES:
        raise ValueError(f"record exceeds {MAX_RECORD_BYTES} bytes; log identifiers and counts, not content")
    return record


_SCRIPT_DATA_KEYS = frozenset({"recovered_bytes", "recovered_sha256"})  # added by a repair, never by the caller


def _without_script_keys(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if key not in _SCRIPT_DATA_KEYS}


def _head_matches(head: str, given: str) -> bool:
    return hmac.compare_digest(head[: len(given)], given)


def append_event(
    log_dir: str | os.PathLike[str],
    run_id: str,
    event: str,
    actor: str,
    *,
    data: object = None,
    usage: object = None,
    ts: str | None = None,
    expect_head: str | None = None,
    unanchored: bool = False,
) -> dict[str, Any]:
    """Validate, redact, chain, and append one record; return it.

    Every append after the first must carry ``expect_head``, the head hash from the previous receipt (a
    16+ character prefix is enough). If the log's head is anything else it raises IntegrityError, unless the
    tail record is exactly this request, already committed before its receipt was lost: then that record is
    returned and nothing is written (a retry is idempotent). ``unanchored`` is the one way to continue
    without a head, only for ``run_resumed``, and the record says so. ``ts`` exists for replay and tests.
    """
    validate_run_id(run_id)
    if event not in EVENTS:
        raise ValueError(f"unknown event {_short(event)}; expected one of: {', '.join(EVENTS)}")
    if actor not in ACTORS:
        raise ValueError(f"unknown actor {_short(actor)}; expected one of: {', '.join(ACTORS)}")
    if data is not None and not isinstance(data, dict):
        raise ValueError("data must be an object")
    if data and (_SCRIPT_DATA_KEYS | {"unanchored"}) & set(data):
        raise ValueError("data may not use the keys the script writes itself: recovered_bytes, recovered_sha256, unanchored")
    if expect_head is not None and not _HEAD_RE.fullmatch(expect_head):
        raise ValueError("expect_head must be the chain_head from your last receipt (16-64 hex characters)")
    if unanchored and (event != "run_resumed" or expect_head is not None):
        raise ValueError("--unanchored is only for run_resumed, and not together with --expect-head")
    _redaction_runtime()  # fail closed now if redaction cannot load, not only when a data key happens to need it
    cleaned_usage = _validate_usage(usage)
    given_ts = _parse_ts(ts) if ts is not None else None
    hits: set[str] = set()
    cleaned_data = _sanitize(data or {}, hits)
    if unanchored:
        cleaned_data["unanchored"] = True
    _validate_event_data(event, cleaned_data)

    directory = Path(log_dir)
    _private_dir(directory)
    path = log_path(directory, run_id)
    fd = _open_private(path, os.O_RDWR | os.O_CREAT | os.O_APPEND)
    try:
        with _locked(fd, exclusive=True):
            size = os.fstat(fd).st_size
            tail = _tail_state(fd, size, run_id)
            if expect_head is None:
                if tail.seq > 0 and not unanchored:
                    raise ValueError(
                        "append needs --expect-head (the chain_head from your previous receipt); to resume without "
                        "one, use run_resumed with --unanchored"
                    )
            elif tail.seq == 0:
                raise IntegrityError("a head was supplied but the log is missing, empty, or was wiped")
            elif not _head_matches(tail.head, expect_head):
                last = tail.last
                if (
                    last is not None
                    and _head_matches(last["prev_hash"], expect_head)
                    and _parse_ts(last["ts"]) <= _now() + timedelta(seconds=CLOCK_SKEW_SECONDS)
                    and (last["event"], last["actor"], _without_script_keys(last["data"]), last["usage"])
                    == (event, actor, cleaned_data, cleaned_usage)
                ):
                    if tail.add_newline:  # committed, only its newline was lost: finish it
                        _write_all(fd, b"\n")
                        _fsync(fd)
                    return last
                raise IntegrityError("the log's head does not match the head from your last receipt; it was changed")
            now = _now()
            if tail.ts is not None and tail.ts > now + timedelta(seconds=CLOCK_SKEW_SECONDS):
                ahead = (tail.ts - now).total_seconds()
                if ahead > FORGED_CLOCK_SECONDS:
                    raise IntegrityError("the last record is timestamped far in the future; a forged log")
                raise ValueError(f"the clock is {int(ahead)}s behind the log's last record; wait, or fix the clock")
            moment = given_ts or now
            if tail.ts is not None:
                if given_ts is not None and given_ts < tail.ts:
                    raise ValueError("ts is earlier than the previous record")
                moment = max(moment, tail.ts)
            problem = _transition_error(tail.seq + 1, event, tail.completed)
            if problem:
                raise ValueError(problem)  # a wrong call, not a damaged log: exit 2, not 1

            blob = b"\n" if tail.add_newline else b""
            if tail.truncate_to is not None:
                # A torn final write was never acknowledged, so nothing acknowledged is lost by cutting it; the
                # loss is recorded on the record that follows, not in a record of its own, so a retry with the
                # caller's head still finds that record's predecessor.
                fragment = os.pread(fd, size - tail.truncate_to, tail.truncate_to)
                cleaned_data = {
                    **cleaned_data,
                    "recovered_bytes": len(fragment),
                    "recovered_sha256": hashlib.sha256(fragment).hexdigest()[:16],
                }
            record = _make_record(tail.seq + 1, tail.head, run_id, event, actor, cleaned_data, cleaned_usage, hits, moment)
            blob += (_canonical(record) + "\n").encode("utf-8")

            restore = size
            try:
                if tail.truncate_to is not None:
                    os.ftruncate(fd, tail.truncate_to)
                    restore = tail.truncate_to
                _write_all(fd, blob)
                _fsync(fd)
            except BaseException:
                try:  # a failed or short write must not leave a torn record behind
                    os.ftruncate(fd, restore)
                except OSError:
                    pass
                raise
        if size == 0:  # the directory entry of a new (or still empty) log
            _fsync_dir(directory)
    finally:
        os.close(fd)
    return record


def _read_log(log_dir: str | os.PathLike[str], run_id: str) -> bytes:
    path = log_path(Path(log_dir), run_id)
    try:
        fd = _open_private(path, os.O_RDONLY)
    except FileNotFoundError:
        raise NoLogError(f"no run log at {path}") from None
    try:
        with _locked(fd, exclusive=False):
            raw = _read_all(fd)
    finally:
        os.close(fd)
    if not raw:
        raise NoLogError(f"the run log at {path} is empty")
    return raw


def _checked(
    log_dir: str | os.PathLike[str], run_id: str, expect_head: str | None
) -> tuple[VerifyResult, list[dict[str, Any]]]:
    if expect_head is not None and not _HEAD_RE.fullmatch(expect_head):
        raise ValueError("expect_head must be the chain_head from your last receipt (16-64 hex characters)")
    try:
        raw = _read_log(log_dir, run_id)
    except NoLogError as exc:
        if expect_head is not None:
            raise IntegrityError(f"a head was supplied but there is no usable log ({exc})") from exc
        raise
    result, records = _full_check(raw, run_id)
    if (result.ok or result.recoverable) and expect_head is not None and not _head_matches(result.head, expect_head):
        ahead = next(
            (len(records) - 1 - i for i, record in enumerate(records) if _head_matches(record["hash"], expect_head)), 0
        )
        note = (
            f"the log has {ahead} record(s) after the head from your last receipt that you did not write or whose receipt was lost"
            if ahead
            else "the log's head does not match the head from your last receipt; it was truncated or replaced"
        )
        result = result._replace(ok=False, recoverable=False, errors=[note], ahead_by=ahead)
    return result, records


def verify_log(
    log_dir: str | os.PathLike[str], run_id: str, *, expect_head: str | None = None
) -> VerifyResult:
    return _checked(log_dir, run_id, expect_head)[0]


def _require_ok(result: VerifyResult) -> None:
    if not result.ok:
        raise IntegrityError("run log does not verify: " + "; ".join(result.errors[:3]))


def _usage_totals(records: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {"input_tokens": 0, "output_tokens": 0, "elapsed_seconds": 0.0, "cost_usd": 0.0}
    usage_records = total_tokens = 0
    for record in records:
        usage = record["usage"]
        if _has_token_usage(usage):
            usage_records += 1
        total_tokens += _tokens_of(usage)
        for key in ("input_tokens", "output_tokens"):
            totals[key] += int(usage.get(key, 0))
        for key in _USAGE_FLOAT_FIELDS:
            totals[key] += float(usage.get(key, 0))
    totals["total_tokens"] = total_tokens
    totals["usage_records"] = usage_records
    return totals


def summarize_log(
    log_dir: str | os.PathLike[str], run_id: str, *, expect_head: str | None = None
) -> dict[str, Any]:
    result, records = _checked(log_dir, run_id, expect_head)
    _require_ok(result)
    counts: dict[str, int] = {}
    by_actor: dict[str, dict[str, int]] = {}
    for record in records:
        counts[record["event"]] = counts.get(record["event"], 0) + 1
        actor = by_actor.setdefault(record["actor"], {"total_tokens": 0})
        actor["total_tokens"] += _tokens_of(record["usage"])
    return {
        "run_id": run_id,
        "events": len(records),
        "chain_head": result.head,
        "counts": counts,
        "usage": _usage_totals(records),
        "by_actor": by_actor,
        "span_minutes": (_parse_ts(records[-1]["ts"]) - _parse_ts(records[0]["ts"])).total_seconds() / 60.0,
    }


def _active_minutes(records: list[dict[str, Any]], now: datetime) -> float:
    """Time spent working, as the union of intervals. Each gap between consecutive records counts at most
    MAX_GAP_MINUTES, so a human decision or an overnight pause does not spend the budget. The gap that ends at a
    `run_resumed` counts nothing when the record before it is a `run_completed` (a person waited); after any
    other record it may be a crash, and is charged like any other gap so a crash loop cannot
    hide. A session's own return record (`builder_`, `remediation_` or `review_returned`) also counts the interval
    its host-reported `elapsed_seconds` says it ran, ending at that record, so a long real session is charged what
    it took whichever records were appended in the middle of it, and parallel sessions are not charged twice."""
    cap = timedelta(minutes=MAX_GAP_MINUTES)
    moments = [_parse_ts(record["ts"]) for record in records]
    ends = [*moments[1:], max(now, moments[-1])]
    spans: list[tuple[datetime, datetime]] = []
    for index, (begin, end) in enumerate(zip(moments, ends)):
        following = records[index + 1] if index + 1 < len(records) else None
        if following is None and records[index]["event"] in PAUSE_EVENTS:
            continue  # nothing has happened since the run finished: reading the budget later is not work
        if following is not None and following["event"] == "run_resumed" and records[index]["event"] in PAUSE_EVENTS:
            continue  # the wait after a completed run is a pause; after any other record it may be a crash
        spans.append((begin, min(max(end, begin), begin + cap)))
        if following is not None and following["event"] in SESSION_RETURNS:
            ran = timedelta(seconds=float(following["usage"].get("elapsed_seconds", 0)))
            if ran > timedelta(0):
                spans.append((max(end - ran, moments[0]), end))
    total = timedelta(0)
    reach: datetime | None = None
    for begin, end in sorted(spans):
        if reach is None or begin > reach:
            total += end - begin
            reach = end
        elif end > reach:
            total += end - reach
            reach = end
    return total.total_seconds() / 60.0


def _task_window_start(records: list[dict[str, Any]]) -> int:
    """Index where the current task's budget window begins: the first of the latest run of `task_selected`
    records for the same task_id (re-selecting it after a resume does not reset its budget), or the start of the
    log if there is none. A `COMPLETE` completion that is followed by more records ends the previous window: a
    finished task that is resumed is a redo, with or without a new `task_selected`. A completion that is the last
    record is the run finishing, not a reset, so the final budget read of a run still sees all of it."""
    starts = [i for i, record in enumerate(records) if record["event"] == "task_selected"]
    start = starts[-1] if starts else 0
    task_id = records[start]["data"].get("task_id") if starts else None
    for earlier in reversed(starts[:-1]):
        if task_id is None or records[earlier]["data"].get("task_id") != task_id:
            break
        start = earlier
    finished = [
        i for i, record in enumerate(records[:-1]) if record["event"] == "run_completed" and record["data"].get("outcome") == "COMPLETE"
    ]
    return max(start, finished[-1] + 1) if finished else start


def check_budget(
    log_dir: str | os.PathLike[str],
    run_id: str,
    *,
    max_tokens: int | None,
    max_minutes: float | None,
    now: str | None = None,
    expect_head: str | None = None,
) -> dict[str, Any]:
    """Compare the CURRENT TASK's usage to its caps. ``None`` means the caller explicitly chose ``unlimited``.

    The current task is everything since the first ``task_selected`` of the latest run of selections of the
    same task (the whole log if there is none), or since a completion that a resume followed, because the caps are per task and a run may work several. Reaching a cap counts as exceeding it.
    """
    result, records = _checked(log_dir, run_id, expect_head)
    _require_ok(result)
    moment = _parse_ts(now) if now else _now()  # a future-dated record already failed verification above
    window = records[_task_window_start(records):]
    totals = _usage_totals(window)
    active = _active_minutes(window, moment)
    exceeded: list[str] = []
    unlimited: list[str] = []
    unmeasured: list[str] = []
    expected = [record for record in window if record["event"] in USAGE_EVENTS]
    if any(not _has_token_usage(record["usage"]) for record in expected):
        unmeasured.append("tokens")  # a session returned and no usage was recorded for it
    if max_tokens is None:
        unlimited.append("tokens")
    elif totals["total_tokens"] >= max_tokens:
        exceeded.append("tokens")
    if max_minutes is None:
        unlimited.append("elapsed_minutes")
    elif active >= max_minutes:
        exceeded.append("elapsed_minutes")
    return {
        "run_id": run_id,
        "window": {"since_seq": window[0]["seq"], "events": len(window)},
        "exceeded": exceeded,
        "unlimited": unlimited,
        "unmeasured": unmeasured,
        "limits": {"max_tokens": max_tokens, "max_minutes": max_minutes},
        "consumed": {
            "estimated_tokens": totals["total_tokens"],
            "elapsed_minutes": active,
            "wall_clock_minutes": max(moment - _parse_ts(window[0]["ts"]), timedelta(0)).total_seconds() / 60.0,
        },
        "chain_head": result.head,
        "seq": records[-1]["seq"],
    }


# --- CLI --------------------------------------------------------------------------------------


def derive_run_id(seeds: object) -> str:
    """A deterministic run id from its seeds (repo, base, task id and the UTC start time, or a plan execution
    identity and the start time): the same seeds give the same id, and the start time makes each start of a task
    a new run. Hashing means untrusted text never becomes a filename."""
    if not isinstance(seeds, list) or not seeds or len(seeds) > 16:
        raise ValueError("run-id takes a JSON array of 1-16 strings on stdin")
    if not all(isinstance(item, str) and 0 < len(item) <= 4000 for item in seeds):
        raise ValueError("every run-id seed must be a non-empty string of at most 4000 characters")
    digest = hashlib.sha256(json.dumps(seeds, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()
    return f"run-{digest[:16]}"


def _cap(raw: str | None, default: int | float) -> int | float | None:
    if raw is None:
        return default
    if raw == "unlimited":
        return None
    # plain digits, or digits grouped in threes by "," or "_" ("1,5" is not fifteen); an optional decimal part
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+|[0-9]{1,3}(?:_[0-9]{3})+)(?:\.[0-9]+)?", raw):
        raise ValueError(f"budget must be a positive number or the word 'unlimited', got {_short(raw)}")
    value = float(raw.replace(",", "").replace("_", ""))
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"budget must be a positive number or the word 'unlimited', got {_short(raw)}")
    return int(value) if value.is_integer() else value


def _read_stdin(name: str) -> str:
    if sys.stdin.isatty():
        raise ValueError(f"{name} reads its input from stdin (a heredoc or a pipe), not from a terminal")
    data = sys.stdin.buffer.read(MAX_STDIN_BYTES + 1)
    if len(data) > MAX_STDIN_BYTES:
        raise ValueError(f"{name} input exceeds {MAX_STDIN_BYTES} bytes")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{name} input is not valid UTF-8") from exc


def _json_arg(raw: str | None, name: str, stdin_used: list[str]) -> object:
    if raw is None:
        return None
    if raw == "-":
        if stdin_used:
            raise ValueError(f"--{name} - cannot read stdin: --{stdin_used[0]} already did")
        stdin_used.append(name)
        raw = _read_stdin(name)
    try:
        return strict_loads(raw)
    except ValueError as exc:
        raise ValueError(f"--{name} is not valid JSON: {exc}") from exc


class _Parser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("allow_abbrev", False)  # sub-parsers too: `--run` must not stand for `--run-id`
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> "NoReturn":  # type: ignore[name-defined]  # noqa: F821
        # argparse quotes what it was given; whatever the caller passed is not to be echoed back at length
        raise ValueError(re.sub(r"[^\x20-\x7e]", "?", message)[:100])

    def exit(self, status: int = 0, message: str | None = None) -> "NoReturn":  # type: ignore[name-defined]  # noqa: F821
        raise ValueError(message.strip() if message else "argument parsing exited early")


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="run_log.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--run-id", required=True)
        p.add_argument("--log-dir", default=None)

    def expect(p: argparse.ArgumentParser) -> None:
        p.add_argument("--expect-head", default=None, help="head hash from your previous receipt")

    append = sub.add_parser("append")
    common(append)
    expect(append)
    append.add_argument("--event", required=True)
    append.add_argument("--unanchored", action="store_true", help="resume without a head (run_resumed only)")
    append.add_argument("--actor", required=True)
    append.add_argument("--data-json", default=None, help="JSON object, or '-' to read it from stdin")
    append.add_argument("--usage-json", default=None, help="JSON object, or '-' to read it from stdin")
    for name in ("verify", "summarize"):
        p = sub.add_parser(name)
        common(p)
        expect(p)
    sub.add_parser("run-id")
    budget = sub.add_parser("budget")
    common(budget)
    expect(budget)
    budget.add_argument("--max-tokens", default=None)
    budget.add_argument("--max-minutes", default=None)
    return parser


def _emit_line(text: str) -> None:
    """Print one line; a reader that has gone away (`| head`, a closed pipe) must not turn a committed
    append into exit 120."""
    try:
        print(text)
        sys.stdout.flush()
    except (BrokenPipeError, ValueError, AttributeError, OSError):
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), 1)
        except OSError:
            pass


def _emit(payload: dict[str, Any]) -> None:
    _emit_line(json.dumps(payload, sort_keys=True))


def _require_supported_platform() -> None:
    if sys.version_info < (3, 10):
        raise RuntimeError(
            f"run_log.py needs Python 3.10 or newer (this repository supports 3.12+); found {sys.version.split()[0]}"
        )
    if fcntl is None:
        raise RuntimeError("run_log.py needs POSIX file locking (Linux or macOS)")


def _run(argv: list[str]) -> int:
    _require_supported_platform()
    args = _build_parser().parse_args(argv)
    if args.command == "run-id":
        _emit_line(derive_run_id(strict_loads(_read_stdin("run-id"))))
        return EXIT_OK
    validate_run_id(args.run_id)
    log_dir = resolve_log_dir(getattr(args, "log_dir", None))

    if args.command == "append":
        stdin_used: list[str] = []
        data = _json_arg(args.data_json, "data-json", stdin_used)
        usage = _json_arg(args.usage_json, "usage-json", stdin_used)
        record = append_event(
            log_dir, args.run_id, args.event, args.actor, data=data, usage=usage,
            expect_head=args.expect_head, unanchored=args.unanchored,
        )
        # A receipt, not the record: the full record would re-enter the model's context for nothing.
        receipt: dict[str, Any] = {"seq": record["seq"], "event": record["event"], "chain_head": record["hash"]}
        if record["event"] in USAGE_EVENTS and not _has_token_usage(record["usage"]):
            receipt["usage_missing"] = True
        _emit(receipt)
        return EXIT_OK
    if args.command == "verify":
        try:
            result = verify_log(log_dir, args.run_id, expect_head=args.expect_head)
        except NoLogError as exc:  # exit 2, but say so in a form a caller can branch on
            _emit({"ok": False, "no_log": True, "detail": _short(str(exc))})
            return EXIT_ERROR
        _emit({"ok": result.ok, "events": result.events, "chain_head": result.head, "last_event": result.last_event,
               "recoverable": result.recoverable, "ahead_by": result.ahead_by,
               "unanchored_resumes": result.unanchored_resumes, "error_count": len(result.errors), "errors": result.errors[:5]})
        return EXIT_OK if result.ok else EXIT_INTEGRITY
    if args.command == "summarize":
        _emit(summarize_log(log_dir, args.run_id, expect_head=args.expect_head))
        return EXIT_OK
    verdict = check_budget(
        log_dir,
        args.run_id,
        max_tokens=_cap(args.max_tokens, DEFAULT_MAX_TASK_TOKENS),  # type: ignore[arg-type]
        max_minutes=_cap(args.max_minutes, DEFAULT_MAX_TASK_MINUTES),
        expect_head=args.expect_head,
    )
    _emit(verdict)
    return EXIT_BUDGET if verdict["exceeded"] else EXIT_OK


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(sys.argv[1:] if argv is None else argv)
    except IntegrityError as exc:
        print(f"run log integrity failure: {exc}", file=sys.stderr)
        return EXIT_INTEGRITY
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"run log failed closed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 - a bug must not read as success
        print(f"run log failed closed: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
