"""Compatibility shim: selector routing now lives in scripts/registry/install_resolver.py.

Kept only for `LEGACY_AGENT_SELECTORS`, which scripts/tests/test_host_registry.py still imports
to assert that no `--agent kiro` selector exists. Import install_resolver directly in new code.
"""

from __future__ import annotations

from scripts.registry.install_resolver import SELECTORS, resolve_install_destinations

LEGACY_AGENT_SELECTORS = frozenset(SELECTORS) - {"agents"}

resolve_legacy_install_destinations = resolve_install_destinations

__all__ = ["LEGACY_AGENT_SELECTORS", "resolve_legacy_install_destinations"]
