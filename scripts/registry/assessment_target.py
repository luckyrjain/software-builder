"""Canonical identity and digest helpers for composable assessments."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def canonical_payload_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def canonical_text_digest(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _normalize_text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("identity values must be strings")
    return unicodedata.normalize("NFC", value.strip())


def normalize_repo_identity(value: str) -> str:
    normalized = _normalize_text(value)
    parsed = urlsplit(normalized)
    if not parsed.scheme or not parsed.netloc:
        return normalized[:-4] if normalized.endswith(".git") else normalized
    hostname = (parsed.hostname or "").lower()
    host = hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    path = parsed.path[:-4] if parsed.path.endswith(".git") else parsed.path
    return urlunsplit((parsed.scheme, host, path, parsed.query, parsed.fragment))


def normalize_service_identity(value: str) -> str:
    return _normalize_text(value)


def normalize_environment_identity(value: str) -> str:
    return _normalize_text(value).lower()


def same_environment(left: str, right: str) -> bool:
    return normalize_environment_identity(left) == normalize_environment_identity(right)


def target_of(obj: Any) -> Mapping[str, Any] | None:
    """Resolve an artifact's own declared identity carrier.

    Every readiness-relevant artifact schema (scripts/registry/composition_contracts.yaml) carries
    its identity in `assessment_target` (`security_review_report`, `change_impact_report`,
    `deployment_risk_report`, etc. all declare it); a bare `target` key is the assessment modules'
    own test-fixture convention. Either is checked BEFORE any flat top-level source_revision/
    head_revision_or_digest/head_sha field the artifact might also carry -- an artifact's own
    declared, nested identity must never be shadowed by (or silently preferred over) a flat field
    that could disagree with it. A malformed nested value (a bare string/list/int instead of a
    mapping) degrades to "keep looking," never crashes -- a caller downstream calls .get() on the
    result unconditionally.
    """
    if not isinstance(obj, Mapping):
        return None
    for key in ("assessment_target", "target"):
        nested = obj.get(key)
        if isinstance(nested, Mapping):
            return nested
    if "source_revision" in obj or "head_revision_or_digest" in obj or "head_sha" in obj:
        return obj
    return None


def safe_same_environment(left: Any, right: Any) -> bool:
    """`same_environment` that fails closed on a malformed operand instead of raising.

    Environment comparison runs against caller- and child-supplied values, so a non-string
    operand must read as "not the same environment" (the fail-closed answer) rather than take
    down the whole assessment with a TypeError.
    """
    try:
        return same_environment(left, right)
    except (TypeError, AttributeError):
        return False
