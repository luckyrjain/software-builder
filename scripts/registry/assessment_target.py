"""Canonical identity and digest helpers for composable assessments."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def canonical_payload_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
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
