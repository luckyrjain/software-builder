from __future__ import annotations

from pathlib import Path

from scripts.yaml_safety import load_unique_yaml_file, require_mapping

HOSTS = {"cursor", "claude", "codex", "chatgpt", "kiro", "generic"}
SUPPORT = {"full", "degraded", "unsupported"}
CAPABILITIES = {
    "discover_files",
    "read_repo",
    "write_repo",
    "git",
    "scm",
    "subagents",
    "task_isolation",
    "terminal",
    "browser",
    "connectors",
}


def _contracts(root: Path) -> dict:
    return require_mapping(
        load_unique_yaml_file(root / "scripts/registry/host_contracts.yaml"),
        "host contracts",
    )


def supported_hosts(root: Path, *, contracts: dict | None = None) -> list[str]:
    """Every host declared in host_contracts.yaml, sorted.

    Pass `contracts` when the caller already parsed host_contracts.yaml (e.g.
    package_release.py, which also needs its schema_version) so this doesn't
    re-read and re-parse the same file a second time; omitted, it parses
    host_contracts.yaml itself as before.
    """
    if contracts is None:
        contracts = _contracts(root)
    hosts = require_mapping(contracts.get("hosts"), "hosts")
    return sorted(hosts)


def capability_support(root: Path, host: str, capability: str) -> str:
    if host not in HOSTS:
        raise ValueError(f"unknown host {host!r}")
    if capability not in CAPABILITIES:
        raise ValueError(f"unknown host capability {capability!r}")
    contracts = _contracts(root)
    hosts = require_mapping(contracts.get("hosts"), "hosts")
    config = require_mapping(hosts.get(host), f"hosts.{host}")
    support = require_mapping(config.get("support"), f"hosts.{host}.support")
    value = support.get(capability)
    if value not in SUPPORT:
        raise ValueError(f"hosts.{host}.support.{capability} has invalid value {value!r}")
    return str(value)


def validate_host_adapter_interface(root: Path) -> list[str]:
    try:
        contracts = _contracts(root)
        errors: list[str] = []
        if contracts.get("schema_version") != 1:
            errors.append("error: host_contracts.schema_version must be 1")
        families = contracts.get("capability_families")
        if not isinstance(families, list) or set(families) != CAPABILITIES or len(families) != len(set(families)):
            errors.append("error: host capability families drift")
        allowed = contracts.get("allowed_support")
        if not isinstance(allowed, list) or set(allowed) != SUPPORT or len(allowed) != len(set(allowed)):
            errors.append("error: host support values drift")
        hosts = require_mapping(contracts.get("hosts"), "hosts")
        if set(hosts) != HOSTS:
            errors.append(f"error: host coverage drift: expected {sorted(HOSTS)}, got {sorted(hosts)}")
        for host in sorted(HOSTS & set(hosts)):
            config = require_mapping(hosts[host], f"hosts.{host}")
            if not isinstance(config.get("adapter"), str) or not config["adapter"].strip():
                errors.append(f"error: hosts.{host}.adapter must be non-empty")
            support = require_mapping(config.get("support"), f"hosts.{host}.support")
            if set(support) != CAPABILITIES:
                errors.append(f"error: hosts.{host}.support must cover every capability exactly once")
                continue
            for capability, value in support.items():
                if value not in SUPPORT:
                    errors.append(f"error: hosts.{host}.support.{capability}: invalid value {value!r}")
        return errors
    except (OSError, ValueError) as exc:
        return [f"error: host adapter interface: {exc}"]
