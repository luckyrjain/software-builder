#!/usr/bin/env python3
"""Validation gate for the ``target`` hint of an incident-rca -> loop-task-implementer task (Epic C, C3).

Implements the design's final (revision 5) ``validate_task_target`` contract -- see
``docs/superpowers/specs/2026-10-02-c3-incident-rca-executor-handoff-design.md`` (APIs table). Full
context is documented at ``docs/skill-framework/shared/incident-rca-handoff.md``.

Why this function exists: ``safe-output.md`` Rule 5 redacts token shapes and PII only; it does nothing
about paths or injected prose, and no other repository code validates a handoff's ``target``. The
``target`` is discovered best-effort from RCA text (untrusted), so it is checked here before it reaches
the envelope. A rejected value is dropped (the function returns ``None``) and the envelope falls back
to service-name-only; a rejected string is never passed on.

Contract: ``validate_task_target(repo_root, target) -> str | None`` returns the original, validated
``target`` string, or ``None``. ``target`` must be a non-empty ASCII ``str`` and takes one of two forms:

* **Symbol form** -- ``re.fullmatch(r"[A-Za-z_][\\w.:$#-]{0,127}", target, re.ASCII)``. ``fullmatch`` and
  ``re.ASCII`` rather than ``^...$`` (accepts a trailing newline) and Unicode ``\\w``.
* **Path form** -- anything else that contains ``/``. Rejected outright: absolute paths, backslashes,
  NUL bytes, any ``..`` segment, input over 200 characters. Otherwise the path is resolved with
  ``(Path(repo_root) / target).resolve()`` and must be ``is_relative_to`` the resolved ``repo_root``
  (not string ``startswith``, which lets ``/repo-evil`` pass), must differ from the repository root
  itself (``./`` otherwise passes), and must exist.
* **Neither form** (for example a bare ``.env`` or ``.``, which fails the symbol regex and has no
  ``/``) returns ``None``.

**Deny list**, applied to BOTH forms and, for the path form, to the RESOLVED path relative to the
root as well as the input string (so a symlink ``docs/x -> ../.git/config`` inside the repo is
caught), with every component casefolded first (macOS filesystems are case-insensitive: ``.GIT/config``
and ``KEY.PEM`` otherwise evade): a ``.git``, ``.ssh`` or ``.aws`` component; names ``.env*``,
``.netrc``, ``.npmrc``, ``.htpasswd``, ``.pgpass``, ``kubeconfig*``, ``credentials*``, and the SSH key
names ``id_rsa*``, ``id_dsa*``, ``id_ecdsa*``, ``id_ed25519*``; suffixes ``.pem``, ``.key``, ``.p12``,
``.pfx``, ``.p8``, ``.jks``, ``.tfvars``. A bare filename such as ``server.pem`` matches the symbol
regex, so the deny list must run on symbols too. Over-matching (a class named ``Credentials`` is
rejected) is the safe direction. The generic ``id_*`` prefix is deliberately not used: it would reject
ordinary code names such as ``id_generator``.

The symbol regex admits ``:`` and ``#``, so a ``:line`` or ``#fragment`` tail (``server.pem:12``,
``server.pem#L10``) would defeat the suffix check. Every component is therefore also checked with the
tail from the first ``:`` or ``#`` removed.

No subprocess and no git: "exists in the worktree" is the only existence check.

**Disclosed residual:** a 128-character, whitespace-free string such as
``IGNORE-ALL-PRIOR-INSTRUCTIONS-and-run`` passes the symbol form -- a small residual injection channel
in a hint field. Nothing here resolves a symbol to a file; that stays Builder-side judgment.
"""

from __future__ import annotations

import re
from pathlib import Path

_SYMBOL_RE = re.compile(r"[A-Za-z_][\w.:$#-]{0,127}", re.ASCII)

_MAX_PATH_CHARS = 200

_DENIED_COMPONENTS = frozenset({".git", ".ssh", ".aws"})
_DENIED_NAMES_EXACT = frozenset({".netrc", ".npmrc", ".htpasswd", ".pgpass"})
_DENIED_NAME_PREFIXES = (
    ".env", "credentials", "kubeconfig", "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
)
_DENIED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".p8", ".jks", ".tfvars")

_LOCATION_TAIL_RE = re.compile(r"[:#].*", re.DOTALL)


def _is_denied(parts: list[str] | tuple[str, ...]) -> bool:
    """True iff any casefolded component, with or without a ``:line``/``#frag`` tail, is denied."""
    for part in parts:
        folded = part.casefold()
        for candidate in (folded, _LOCATION_TAIL_RE.sub("", folded)):
            if candidate in _DENIED_COMPONENTS or candidate in _DENIED_NAMES_EXACT:
                return True
            if candidate.startswith(_DENIED_NAME_PREFIXES):
                return True
            if candidate.endswith(_DENIED_SUFFIXES):
                return True
    return False


def validate_task_target(repo_root: str | Path, target: str | None) -> str | None:
    """Return ``target`` if it is a safe symbol or in-repo existing path, else ``None``."""
    if not isinstance(target, str) or not target or not target.isascii():
        return None

    if _SYMBOL_RE.fullmatch(target) is not None:
        return None if _is_denied([target]) else target

    if "/" not in target:
        return None

    if (
        target.startswith("/")
        or "\\" in target
        or "\0" in target
        or len(target) > _MAX_PATH_CHARS
    ):
        return None
    segments = target.split("/")
    if ".." in segments:
        return None
    if _is_denied([seg for seg in segments if seg]):
        return None

    try:
        root = Path(repo_root).resolve()
        resolved = (Path(repo_root) / target).resolve()
        if not resolved.is_relative_to(root) or resolved == root:
            return None
        if not resolved.exists():
            return None
        if _is_denied(resolved.relative_to(root).parts):
            return None
    except (TypeError, ValueError, OSError, RuntimeError):
        return None

    return target
