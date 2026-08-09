"""Deterministic reference normalizer for PRD Gate Markdown output."""

from __future__ import annotations

import ipaddress
import re

_REDACTED_SECRET = "[REDACTED SECRET]"
_SECRET_KEY = (
    # Environment names may namespace a credential with separator-delimited
    # identifier segments. Requiring those separators and a complete sensitive
    # suffix avoids substring matches in ordinary names such as MONKEY/TURNKEY.
    r"(?P<key>(?:[A-Za-z][A-Za-z0-9]*[_.-])*"
    r"(?:api[_-]?key|access[_-]?key|private(?:[_-]?|\s+)key|key|token|password|passphrase|secret|"
    r"client(?:[_.-]?|\s+)secret))(?![A-Za-z0-9_])"
)
_SECRET_PATTERNS = (
    re.compile(
        r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----.*?"
        r"-----END (?:[A-Z0-9]+ )?PRIVATE KEY-----",
        re.DOTALL,
    ),
    re.compile(r"(?<![A-Za-z0-9_])github_pat_[A-Za-z0-9_]{20,}(?![A-Za-z0-9_])"),
    re.compile(r"(?<![A-Za-z0-9_])ghp_[A-Za-z0-9]{36}(?![A-Za-z0-9_])"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{8,}=*"),
    re.compile(
        r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\."
        r"[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])"
    ),
    re.compile(r"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{16,}(?![A-Za-z0-9_-])", re.IGNORECASE),
    re.compile(r"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])"),
    re.compile(
        r"(?i)\bclient(?:[_.-]?|\s+)secret\s*[:=]\s*"
        r"[A-Za-z0-9+/_-]{16,}={0,2}(?![A-Za-z0-9+/_=-])"
    ),
)
_QUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?i)\b{_SECRET_KEY}\s*[:=]\s*"
    r"(?P<quote>['\"])(?P<value>(?:\\[^\r\n]|(?!(?P=quote))[^\\\r\n])+)(?P=quote)"
)
_UNQUOTED_SECRET_ASSIGNMENT_RE = re.compile(
    rf"(?i)\b{_SECRET_KEY}\s*[:=](?!\s*['\"])\s*"
    # An explicit credential label makes spaces part of an unquoted value. Stop
    # at a line end, a clear record delimiter, or the next bounded assignment
    # field. All other punctuation is secret material: stopping at brackets,
    # braces, parentheses, or ampersands can expose a credential suffix.
    r"(?P<value>[^\r\n,;|]+?)"
    r"(?=(?:[ \t]+(?=[A-Z][A-Z0-9_.-]*[ \t]*[:=]))|[\r\n,;|]|$)"
)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d .()-]{7,}\d)(?!\w)")
_STRUCTURED_NUMERIC_RE = re.compile(
    r"(?<!\w)(?:"
    r"\d{4}-\d{2}-\d{2}"
    r"|(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?"
    r"|\d+(?:\.\d+){2,}(?:-\d+(?:\.\d+)*)?"
    r"|\d{4}(?:-\d{4}){1,}"
    r")(?!\w)"
)
_TECHNICAL_IDENTIFIER_RE = re.compile(
    r"(?i)\b(?:build(?:[ _-]?id)?|sha|commit|trace(?:[ _-]?id)?|ticket|"
    r"object(?:[ _-]?id)?|order(?:[ _-]?id)?|issue|job(?:[ _-]?id)?|run(?:[ _-]?id)?)"
    r"(?:[ \t]*(?:[:=#]|\bis\b)[ \t]*|[ \t]+)\d{10,15}(?!\d)"
)
_PHONE_CONTEXT_IDENTIFIER_RE = re.compile(
    # Resolve bounded phone-label compounds before generic ID segmentation so
    # a trailing phrase such as ``number ID`` cannot shield the phone value.
    # Bare call/contact ID labels are ordinary opaque technical identifiers;
    # require an explicit phone/number term before treating them as phone context.
    r"(?i)\b(?:"
    r"(?:phone|mobile|telephone)(?:[ _-]+number)?"
    r"|call[ _-]+number"
    r"|contact[ _-]+(?:(?:phone|mobile)(?:[ _-]+number)?|call[ _-]+number|number)"
    r")(?:[ _-]+)(?:id|identifier)\b"
    r"(?:[ \t]*(?:[:=#]|\bis\b)[ \t]*|[ \t]+)(?P<phone>\d{10,15})(?!\d)"
)
_EXPLICIT_IDENTIFIER_RE = re.compile(
    # A bounded ordinary label plus an explicit ID/identifier marker is enough
    # to distinguish opaque numeric identifiers without enumerating domains.
    r"(?i)\b[A-Z][A-Z0-9]{0,31}(?:[ _-]+)(?:id|identifier)\b"
    r"(?:[ \t]*(?:[:=#]|\bis\b)[ \t]*|[ \t]+)\d{10,15}(?!\d)"
)
_STRUCTURAL_PREFIX_RE = re.compile(r"^(\s*)(#{1,6}\s|>|[-+*]\s|\d+[.)]\s)")
_URL_SCHEME_RE = re.compile(r"(?i)\b[A-Z][A-Z0-9+.-]{1,31}:(?=//|[^\s])")
_PROTOCOL_RELATIVE_RE = re.compile(r"(?<![:/])//(?=[A-Za-z0-9])")
_WWW_URL_RE = re.compile(r"(?i)\bwww\.(?=[A-Za-z0-9])")


def _is_secret_placeholder(value: str) -> bool:
    return bool(
        re.fullmatch(r"\$\{[A-Z0-9_]+\}", value, re.IGNORECASE)
        or re.fullmatch(
            r"(?:placeholder|example|sample|dummy|changeme|replace[-_.]?me)"
            r"(?:[-_.]?(?:value|secret|token|key))?",
            value,
            re.IGNORECASE,
        )
    )


def _is_generic_key_secret(value: str) -> bool:
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


def _is_secret_assignment(key: str, value: str) -> bool:
    if len(value) < 12 or _is_secret_placeholder(value):
        return False
    key_parts = re.split(r"[_.-]", key.lower())
    ambiguous_key_suffix = key_parts[-1] == "key" and not (
        len(key_parts) > 1 and key_parts[-2] in {"api", "access", "private"}
    )
    return not ambiguous_key_suffix or _is_generic_key_secret(value)


def _redact_secrets(source: str) -> tuple[str, bool]:
    """Redact ordered, conservative credential forms without exposing matched values."""
    normalized = source
    redacted = False
    for pattern in _SECRET_PATTERNS:
        normalized, count = pattern.subn(_REDACTED_SECRET, normalized)
        redacted = redacted or count > 0

    def redact_quoted(match: re.Match[str]) -> str:
        nonlocal redacted
        value = match.group("value").strip()
        if not _is_secret_assignment(match.group("key"), value):
            return match.group(0)
        redacted = True
        return _REDACTED_SECRET

    normalized = _QUOTED_SECRET_ASSIGNMENT_RE.sub(redact_quoted, normalized)

    def redact_unquoted(match: re.Match[str]) -> str:
        nonlocal redacted
        value = match.group("value")
        if not _is_secret_assignment(match.group("key"), value):
            return match.group(0)
        redacted = True
        return _REDACTED_SECRET

    return _UNQUOTED_SECRET_ASSIGNMENT_RE.sub(redact_unquoted, normalized), redacted


def _redact_phone(match: re.Match[str]) -> str:
    """Redact plausible phones while preserving dates, versions, and numeric IDs."""
    candidate = match.group(0)
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        pass
    else:
        return candidate
    digits = re.sub(r"\D", "", candidate)
    if not 10 <= len(digits) <= 15:
        return candidate
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
        return candidate
    if re.fullmatch(r"\d{4}-\d{4}-\d{4}", candidate):
        return candidate
    # Country prefixes, domestic formatting, and 10+ contiguous digits are strong
    # phone evidence. Keep identifier-style equal four-digit groups literal.
    if candidate.startswith("+") or "(" in candidate or ")" in candidate:
        return "[REDACTED PHONE]"
    if candidate.isdigit():
        return "[REDACTED PHONE]"
    if " " in candidate or "." in candidate:
        groups = re.split(r"[ .]+", candidate)
        if len(groups) >= 3 and not all(len(group) == 4 for group in groups):
            return "[REDACTED PHONE]"
        return candidate
    groups = candidate.split("-")
    if (
        len(groups) >= 3
        and len(groups[0]) <= 3
        and all(2 <= len(group) <= 4 for group in groups)
    ):
        return "[REDACTED PHONE]"
    return candidate


def normalize_untrusted_markdown(source: str) -> tuple[str, bool]:
    """Return one structurally inert Markdown paragraph and whether redaction occurred."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    normalized, redacted = _redact_secrets(source)
    normalized, count = _EMAIL_RE.subn("[REDACTED EMAIL]", normalized)
    redacted = redacted or count > 0

    phone_redacted = False

    def redact_phone(match: re.Match[str]) -> str:
        nonlocal phone_redacted
        replacement = _redact_phone(match)
        phone_redacted = phone_redacted or replacement != match.group(0)
        return replacement

    def redact_phone_context_identifier(match: re.Match[str]) -> str:
        nonlocal phone_redacted
        phone_redacted = True
        phone_start, phone_end = match.span("phone")
        relative_start = phone_start - match.start()
        relative_end = phone_end - match.start()
        return (
            match.group(0)[:relative_start]
            + "[REDACTED PHONE]"
            + match.group(0)[relative_end:]
        )

    normalized = _PHONE_CONTEXT_IDENTIFIER_RE.sub(redact_phone_context_identifier, normalized)

    # Structured numeric tokens delimit phone candidates. Without segmentation,
    # the permissive whitespace in _PHONE_RE can merge adjacent dates, endpoints,
    # versions, or IDs into one phone-shaped match.
    chunks: list[str] = []
    cursor = 0
    structured_tokens = sorted(
        (
            *_STRUCTURED_NUMERIC_RE.finditer(normalized),
            *_TECHNICAL_IDENTIFIER_RE.finditer(normalized),
            *_EXPLICIT_IDENTIFIER_RE.finditer(normalized),
        ),
        key=lambda match: match.start(),
    )
    for structured in structured_tokens:
        if structured.start() < cursor:
            continue
        chunks.append(_PHONE_RE.sub(redact_phone, normalized[cursor : structured.start()]))
        chunks.append(structured.group(0))
        cursor = structured.end()
    chunks.append(_PHONE_RE.sub(redact_phone, normalized[cursor:]))
    normalized = "".join(chunks)
    redacted = redacted or phone_redacted
    lines: list[str] = []
    for line in normalized.splitlines():
        # Fullwidth brackets make inline links/images and reference definitions/uses inert.
        line = line.replace("[", "［").replace("]", "］")
        # Break explicit and renderer-generated autolinks while leaving URLs readable.
        line = _URL_SCHEME_RE.sub(lambda match: match.group(0)[:-1] + "：", line)
        line = _PROTOCOL_RELATIVE_RE.sub("/／", line)
        line = _WWW_URL_RE.sub(lambda match: match.group(0)[:-1] + "．", line)
        line = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        # Escape user-authored backslashes first so they cannot consume the escapes
        # added for inline emphasis, strong emphasis, or GFM strikethrough delimiters.
        # Markdown renderers omit these escapes, preserving the visible literal text.
        line = re.sub(r"([\\*~])", r"\\\1", line)
        # Unlike asterisks, underscores embedded in identifiers cannot open or close
        # CommonMark emphasis. Preserve those byte-for-byte while escaping paired
        # delimiter runs that a renderer can turn into inline formatting nodes.
        line = re.sub(
            r"(?<![A-Za-z0-9])(?P<open>_{1,3})(?=\S)(?P<body>.+?\S)(?P=open)(?![A-Za-z0-9])",
            lambda match: (
                match.group("open").replace("_", "\\_")
                + match.group("body")
                + match.group("open").replace("_", "\\_")
            ),
            line,
        )
        line = line.replace("`", "ˋ").replace("|", "\\|")
        line = _STRUCTURAL_PREFIX_RE.sub(r"\1\\\2", line)
        for marker in (_REDACTED_SECRET, "[REDACTED EMAIL]", "[REDACTED PHONE]"):
            line = line.replace(marker.replace("[", "［").replace("]", "］"), marker)
        lines.append(line)
    return " ⤶ ".join(lines), redacted


def render_gate_output(source: str, verdict: str, rationale: str) -> str:
    """Render the concrete safe-output contract used at the PRD Gate boundary."""
    if verdict not in {"Ready", "Ready With Non-Blocking Questions", "Not Ready"}:
        raise ValueError("unsupported Build Readiness verdict")
    excerpt, source_redacted = normalize_untrusted_markdown(source)
    safe_rationale, rationale_redacted = normalize_untrusted_markdown(rationale)
    disclosure = (
        "\n\n_Sensitive source data was redacted._"
        if source_redacted or rationale_redacted
        else ""
    )
    return (
        f"Source excerpt: {excerpt}{disclosure}\n\n"
        f"## Build Readiness\n\n**{verdict}** — {safe_rationale}"
    )
