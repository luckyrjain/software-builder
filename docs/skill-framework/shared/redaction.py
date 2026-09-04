#!/usr/bin/env python3
"""One redaction pattern table for every skill that renders untrusted text.

Redaction used to be implemented twice, with no shared source and nothing asserting the two
agreed. `incident-rca/scripts/kubesense_logs.py` carried a credential family tuned for fetched log
bodies; `prd-architect/scripts/prd_safe_output.py` carried a second family tuned for quoted PRD
source material, including contact PII the first family had no equivalent for. Adding a pattern to
one silently left the other exposed.

This module is that single source. A `RedactionPattern` is a named, categorised regex plus the
replacement it renders; `redact()` applies an ordered tuple of them and reports which ones fired.
Skills select a *profile* rather than a private list, so a pattern added here reaches every
consumer that shares the profile.

Two profiles exist because the two consumers redact different material for different reasons, not
because the patterns drifted:

* `LOG_PATTERNS` -- machine-emitted log bodies. The marker is `[REDACTED]` and header/key text is
  preserved (`Authorization=[REDACTED]`), because the surviving key name is the diagnostic signal.
* `DOCUMENT_PATTERNS` -- human-authored prose quoted back into a report. The marker is
  `[REDACTED SECRET]`, replaces the whole assignment, and value-shape predicates gate the generic
  key names so ordinary design prose survives.

Merge decisions
---------------
Every pattern that existed in only one family was assessed against the other consumer's material.

Adopted by both (previously document-only):
* `github_pat`, `github_ghp`, `openai_sk`, `aws_akia` -- anchored vendor prefixes with fixed
  alphabets and length floors. A log line containing one contains a leaked credential by
  construction, so there is no false-positive population to trade against.
* `bearer_token` -- the log family only caught `"Bearer ...` inside a JSON-quoted header value, so a
  plain-text `Authorization: Bearer ...` log line went out unredacted.
* `jwt` -- three dot-separated 16+ character base64url runs. Dotted identifiers in Kubernetes logs
  (package names, pod names, image references) do not reach 16 characters per segment three
  segments running; the false-positive corpus in the tests pins that.
* `client_secret_kv` -- requires a 16+ character value after the assignment, so it cannot fire on
  prose that merely names the field.

Refused for logs (kept document-only):
* `email` -- Kubernetes and cloud identities are email-shaped by design
  (`deployer@project.iam.gserviceaccount.com`). Redacting them destroys exactly the authn/RBAC
  detail an incident responder opened the log for.
* phone/contact numbers -- not a table pattern at all (see `prd_safe_output.py`, which needs
  structured-token segmentation to tell a phone from a date, a version, or a request id). Log
  bodies are dense with 10-15 digit epoch timestamps, ports, and trace ids.
* `quoted_secret_assignment` / `unquoted_secret_assignment` -- the unquoted form deliberately
  treats spaces as part of an unquoted credential and runs to a line or record delimiter. In prose
  that is right; in a log line it would swallow the rest of the line after any `token=` field,
  discarding the diagnostic context around the secret. The log family's bounded `\\S+` forms cover
  the same key names without that reach.

Refused for documents (kept log-only):
* `authorization_json`, `authorization_kv`, `authorization_straggler`, `basic_credentials`,
  `api_key_json`, `api_key_kv`, `password_json`, `password_kv` -- all unconditional. A PRD sentence
  reading `password: TBD` or `"api_key": "supplied by ops"` is design prose, and
  `quoted_secret_assignment`/`unquoted_secret_assignment` already cover those key names with
  value-shape evidence behind them.
* `pem_block` -- the log profile collapses PRIVATE KEY *and* CERTIFICATE bodies while keeping the
  BEGIN/END markers, which is a log-volume decision as much as a secrecy one; certificates are
  public material. The document profile drops private-key blocks whole, markers included, and
  leaves certificates alone.
"""

from __future__ import annotations

import re
from typing import Callable, NamedTuple

DEFAULT_MARKER = "[REDACTED]"
SECRET_MARKER = "[REDACTED SECRET]"
EMAIL_MARKER = "[REDACTED EMAIL]"

CATEGORIES = ("secret", "pii", "token")

# A replacement is either a template string -- `\1`-style backreferences plus an optional
# `{marker}` field the profile fills in -- or a predicate that inspects the match and returns the
# text to substitute, or None to decline the match and leave it byte-for-byte.
Replacement = str | Callable[[re.Match[str], str], "str | None"]


# NamedTuple rather than a frozen dataclass: skill scripts execute this module out of a vendored
# tree via importlib without registering it in sys.modules, and dataclasses resolves string
# annotations through sys.modules at class-creation time.
class RedactionPattern(NamedTuple):
    """One named redactor: what it recognises, what it renders, and what kind of data it is."""

    name: str
    pattern: re.Pattern[str]
    replacement: Replacement
    category: str


class RedactionHit(NamedTuple):
    """A pattern that acted on the text, and how many matches it acted on."""

    name: str
    category: str
    count: int


# --- Credential key vocabulary shared by the predicate-gated assignment patterns ----------------

_SECRET_KEY = (
    # Environment names may namespace a credential with separator-delimited
    # identifier segments. Requiring those separators and a complete sensitive
    # suffix avoids substring matches in ordinary names such as MONKEY/TURNKEY.
    r"(?P<key>(?:[A-Za-z][A-Za-z0-9]*[_.-])*"
    r"(?:api[_-]?key|access[_-]?key|private(?:[_-]?|\s+)key|key|token|password|passphrase|secret|"
    r"client(?:[_.-]?|\s+)secret))(?![A-Za-z0-9_])"
)


def is_secret_placeholder(value: str) -> bool:
    """Whether a value is an obvious stand-in rather than a credential."""
    return bool(
        re.fullmatch(r"\$\{[A-Z0-9_]+\}", value, re.IGNORECASE)
        or re.fullmatch(
            r"(?:placeholder|example|sample|dummy|changeme|replace[-_.]?me)"
            r"(?:[-_.]?(?:value|secret|token|key))?",
            value,
            re.IGNORECASE,
        )
    )


def is_generic_key_secret(value: str) -> bool:
    """Require secret-shape evidence for ambiguous bare ``key`` assignments."""
    if re.fullmatch(r"[0-9a-f]{24,}", value, re.IGNORECASE):
        return True
    if len(value) < 20 or not re.fullmatch(r"[A-Za-z0-9+/_=-]+", value):
        return False
    # Lowercase words joined as an identifier are commonly cache, database, and
    # index keys. Mixed character classes are stronger credential evidence.
    classes = sum(
        bool(re.search(pattern, value))
        for pattern in (r"[a-z]", r"[A-Z]", r"\d", r"[+/=]")
    )
    return classes >= 3


def is_secret_assignment(key: str, value: str) -> bool:
    """Whether ``key = value`` carries a credential rather than naming a field."""
    if len(value) < 12 or is_secret_placeholder(value):
        return False
    key_parts = re.split(r"[_.-]", key.lower())
    ambiguous_key_suffix = key_parts[-1] == "key" and not (
        len(key_parts) > 1 and key_parts[-2] in {"api", "access", "private"}
    )
    return not ambiguous_key_suffix or is_generic_key_secret(value)


def _redact_quoted_assignment(match: re.Match[str], marker: str) -> str | None:
    if not is_secret_assignment(match.group("key"), match.group("value").strip()):
        return None
    return marker


def _redact_unquoted_assignment(match: re.Match[str], marker: str) -> str | None:
    if not is_secret_assignment(match.group("key"), match.group("value")):
        return None
    return marker


# --- Patterns shared by both profiles -----------------------------------------------------------

GITHUB_PAT = RedactionPattern(
    name="github_pat",
    pattern=re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{20,}(?![A-Za-z0-9_])"),
    replacement="{marker}",
    category="token",
)
GITHUB_GHP = RedactionPattern(
    name="github_ghp",
    pattern=re.compile(r"(?<![A-Za-z0-9_])ghp_[A-Za-z0-9]{36}(?![A-Za-z0-9_])"),
    replacement="{marker}",
    category="token",
)
BEARER_TOKEN = RedactionPattern(
    name="bearer_token",
    pattern=re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}=*"),
    replacement="{marker}",
    category="token",
)
JWT = RedactionPattern(
    name="jwt",
    pattern=re.compile(
        r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\."
        r"[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])"
    ),
    replacement="{marker}",
    category="token",
)
OPENAI_SK = RedactionPattern(
    name="openai_sk",
    pattern=re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])", re.IGNORECASE),
    replacement="{marker}",
    category="token",
)
AWS_AKIA = RedactionPattern(
    name="aws_akia",
    pattern=re.compile(r"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])"),
    replacement="{marker}",
    category="token",
)
CLIENT_SECRET_KV = RedactionPattern(
    name="client_secret_kv",
    pattern=re.compile(
        r"(?i)\bclient(?:[_.-]?|\s+)secret\s*[:=]\s*"
        r"[A-Za-z0-9+/_-]{16,}={0,2}(?![A-Za-z0-9+/_=-])"
    ),
    replacement="{marker}",
    category="secret",
)

_VENDOR_TOKEN_PATTERNS: tuple[RedactionPattern, ...] = (
    GITHUB_PAT,
    GITHUB_GHP,
    BEARER_TOKEN,
    JWT,
    OPENAI_SK,
    AWS_AKIA,
    CLIENT_SECRET_KV,
)

# --- Log profile --------------------------------------------------------------------------------

LOG_PATTERNS: tuple[RedactionPattern, ...] = (
    RedactionPattern(
        name="authorization_json",
        pattern=re.compile(r'("Authorization"\s*:\s*")[^"]*(")', re.IGNORECASE),
        replacement=r"\1{marker}\2",
        category="secret",
    ),
    RedactionPattern(
        name="bearer_quoted",
        pattern=re.compile(r'("Bearer\s+)[^"\\]+', re.IGNORECASE),
        replacement=r"\1{marker}",
        category="token",
    ),
    RedactionPattern(
        # A marker already present is not proof of safety: the value can still trail it.
        name="authorization_straggler",
        pattern=re.compile(r"(Authorization=\[REDACTED\])\s+\S+", re.IGNORECASE),
        replacement=r"\1",
        category="token",
    ),
    RedactionPattern(
        name="authorization_kv",
        pattern=re.compile(r"(Authorization=)[^,\]} ]+", re.IGNORECASE),
        replacement=r"\1{marker}",
        category="secret",
    ),
    RedactionPattern(
        name="basic_credentials",
        pattern=re.compile(r"(Basic\s+)[A-Za-z0-9+/=]{8,}", re.IGNORECASE),
        replacement=r"\1{marker}",
        category="secret",
    ),
    RedactionPattern(
        name="api_key_json",
        pattern=re.compile(r'("(?:x-)?api[_-]?key"\s*:\s*")[^"]*(")', re.IGNORECASE),
        replacement=r"\1{marker}\2",
        category="secret",
    ),
    RedactionPattern(
        name="api_key_kv",
        pattern=re.compile(r"((?:x-)?api[_-]?key\s*=\s*)\S+", re.IGNORECASE),
        replacement=r"\1{marker}",
        category="secret",
    ),
    RedactionPattern(
        name="password_json",
        pattern=re.compile(r'("(?:password|passwd|pwd)"\s*:\s*")[^"]*(")', re.IGNORECASE),
        replacement=r"\1{marker}\2",
        category="secret",
    ),
    RedactionPattern(
        name="password_kv",
        pattern=re.compile(r"((?:password|passwd|pwd)\s*=\s*)\S+", re.IGNORECASE),
        replacement=r"\1{marker}",
        category="secret",
    ),
    RedactionPattern(
        # Collapse the whole block, not just the header, and keep the markers so the reader can
        # see what was dropped.
        name="pem_block",
        pattern=re.compile(
            r"(-----BEGIN [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----)[\s\S]*?"
            r"(-----END [A-Z ]*(?:PRIVATE KEY|CERTIFICATE)-----)"
        ),
        replacement="\\1\n{marker}\n\\2",
        category="secret",
    ),
    *_VENDOR_TOKEN_PATTERNS,
)

# --- Document profile ---------------------------------------------------------------------------

DOCUMENT_PATTERNS: tuple[RedactionPattern, ...] = (
    RedactionPattern(
        name="pem_private_key",
        pattern=re.compile(
            r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----.*?"
            r"-----END (?:[A-Z0-9]+ )?PRIVATE KEY-----",
            re.DOTALL,
        ),
        replacement="{marker}",
        category="secret",
    ),
    *_VENDOR_TOKEN_PATTERNS,
    RedactionPattern(
        name="quoted_secret_assignment",
        pattern=re.compile(
            rf"(?i)\b{_SECRET_KEY}\s*[:=]\s*"
            r"(?P<quote>['\"])(?P<value>(?:\\[^\r\n]|(?!(?P=quote))[^\\\r\n])+)(?P=quote)"
        ),
        replacement=_redact_quoted_assignment,
        category="secret",
    ),
    RedactionPattern(
        name="unquoted_secret_assignment",
        pattern=re.compile(
            rf"(?i)\b{_SECRET_KEY}\s*[:=](?!\s*['\"])\s*"
            # An explicit credential label makes spaces part of an unquoted value. Stop
            # at a line end, a clear record delimiter, or the next bounded assignment
            # field. All other punctuation is secret material: stopping at brackets,
            # braces, parentheses, or ampersands can expose a credential suffix.
            r"(?P<value>[^\r\n,;|]+?)"
            r"(?=(?:[ \t]+(?=[A-Z][A-Z0-9_.-]*[ \t]*[:=]))|[\r\n,;|]|$)"
        ),
        replacement=_redact_unquoted_assignment,
        category="secret",
    ),
    RedactionPattern(
        name="email",
        pattern=re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
        replacement=EMAIL_MARKER,
        category="pii",
    ),
)


def _union(*profiles: tuple[RedactionPattern, ...]) -> tuple[RedactionPattern, ...]:
    seen: set[str] = set()
    ordered: list[RedactionPattern] = []
    for profile in profiles:
        for entry in profile:
            if entry.name in seen:
                continue
            seen.add(entry.name)
            ordered.append(entry)
    return tuple(ordered)


#: Every redactor this repository knows about, in profile order, each name appearing once.
REDACTION_PATTERNS: tuple[RedactionPattern, ...] = _union(LOG_PATTERNS, DOCUMENT_PATTERNS)

_UNKNOWN_CATEGORIES = sorted({entry.category for entry in REDACTION_PATTERNS} - set(CATEGORIES))
if _UNKNOWN_CATEGORIES:
    raise ValueError(f"unknown redaction categories: {', '.join(_UNKNOWN_CATEGORIES)}")


def redact(
    text: str,
    *,
    patterns: tuple[RedactionPattern, ...] = REDACTION_PATTERNS,
    marker: str = DEFAULT_MARKER,
    passes: int = 1,
) -> tuple[str, list[RedactionHit]]:
    """Apply `patterns` in order and return the redacted text plus the patterns that acted.

    A predicate-gated pattern may decline a match; a declined match is not a hit and leaves the
    text byte-for-byte. `passes` re-runs the whole table, which is how a replacement that exposes
    a second pattern's shape (a value trailing a marker, say) gets caught.
    """
    redacted = text
    counts: dict[str, int] = {}
    for _ in range(passes):
        for entry in patterns:
            if isinstance(entry.replacement, str):
                redacted, count = entry.pattern.subn(
                    entry.replacement.format(marker=marker), redacted
                )
            else:
                redacted, count = _sub_with_predicate(entry, redacted, marker)
            if count:
                counts[entry.name] = counts.get(entry.name, 0) + count
    return redacted, [
        RedactionHit(name=entry.name, category=entry.category, count=counts[entry.name])
        for entry in patterns
        if entry.name in counts
    ]


def _sub_with_predicate(
    entry: RedactionPattern, text: str, marker: str
) -> tuple[str, int]:
    predicate = entry.replacement
    assert not isinstance(predicate, str)
    accepted = 0

    def apply(match: re.Match[str]) -> str:
        nonlocal accepted
        replacement = predicate(match, marker)
        if replacement is None:
            return match.group(0)
        accepted += 1
        return replacement

    return entry.pattern.sub(apply, text), accepted
