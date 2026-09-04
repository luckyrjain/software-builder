"""Deterministic reference normalizer for PRD Gate Markdown output."""

from __future__ import annotations

import importlib.util
import ipaddress
import re
from pathlib import Path
from types import ModuleType

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
        path = SKILL_ROOT.parent / "docs/skill-framework/shared/shared_runtime_loader.py"
    if not path.is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    spec = importlib.util.spec_from_file_location("software_builder_shared_runtime_loader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
# GENERATED shared-runtime-bootstrap:end


_redaction = _shared_runtime_loader().load_shared_runtime(
    SKILL_ROOT,
    "redaction",
    alias="shared_redaction",
    description=_RUNTIME_DESCRIPTION,
)

# The document profile of the shared table: credential forms whose generic key names are gated by
# value-shape predicates, plus contact PII. Phone numbers are not a table pattern -- telling a
# phone from a date, a version, or a request id needs the structured-token segmentation below.
REDACTION_PROFILE = _redaction.DOCUMENT_PATTERNS

_REDACTED_SECRET = _redaction.SECRET_MARKER
_REDACTED_EMAIL = _redaction.EMAIL_MARKER
_REDACTED_PHONE = "[REDACTED PHONE]"
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
        return _REDACTED_PHONE
    if candidate.isdigit():
        return _REDACTED_PHONE
    if " " in candidate or "." in candidate:
        groups = re.split(r"[ .]+", candidate)
        if len(groups) >= 3 and not all(len(group) == 4 for group in groups):
            return _REDACTED_PHONE
        return candidate
    groups = candidate.split("-")
    if (
        len(groups) >= 3
        and len(groups[0]) <= 3
        and all(2 <= len(group) <= 4 for group in groups)
    ):
        return _REDACTED_PHONE
    return candidate


def normalize_untrusted_markdown(source: str) -> tuple[str, bool]:
    """Return one structurally inert Markdown paragraph and whether redaction occurred."""
    if not isinstance(source, str):
        raise TypeError("source must be a string")
    normalized, hits = _redaction.redact(
        source, patterns=REDACTION_PROFILE, marker=_REDACTED_SECRET
    )
    redacted = bool(hits)

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
            + _REDACTED_PHONE
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
        for marker in (_REDACTED_SECRET, _REDACTED_EMAIL, _REDACTED_PHONE):
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
