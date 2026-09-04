from __future__ import annotations

from pathlib import Path

from scripts.yaml_safety import load_unique_yaml_file, require_mapping

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

# The one roster of hosts this adapter layer generates for, and the skill surface each
# one expects. `HOSTS` is derived from it rather than restated, so adding a host is one
# edit here instead of one here plus one in host_portability.py; every drift validator
# below (host_contracts.yaml, evals/host-parity/expected.yaml) then keys off this set.
EXPECTED_SURFACES = {
    "cursor": "per_skill_generated",
    "claude": "canonical_root",
    "codex": "canonical_root",
    "chatgpt": "canonical_root",
    "kiro": "per_skill_generated",
    "generic": "canonical_root",
}
HOSTS = frozenset(EXPECTED_SURFACES)

# The bridge between this module's coarse adapter-generation capability families and the
# finer-grained `host.*` capability ids skills.yaml's per-skill capabilities and
# agent-hosts.yaml's HostSpec.capabilities share. One direction only (`host.* -> families`)
# and one location: the two halves of the correspondence live beside each other here, so
# "which family gates this host.* id" has a single answer.
#
# capability_families.yaml deliberately exempts `host.*` ids from its own
# (differently-scoped) provider-resolution mapping -- see its module docstring -- so this
# is a separate, purpose-built join for the compatibility matrix. Only ids that actually
# appear in some skill's global `required` list need an entry; an unmapped `host.*` id in
# `required` fails the build (see generate_compatibility._required_host_families) instead
# of silently rendering the old blanket per-host profile.
HOST_CAPABILITY_FAMILIES: dict[str, tuple[str, ...]] = {
    "host.repository.read": ("read_repo",),
    "host.repository.read_write": ("read_repo", "write_repo"),
    "host.filesystem.read": ("read_repo",),
    "host.report.write": ("write_repo",),
    "host.role.isolation": ("task_isolation",),
    "host.ci.status": ("scm",),
    "host.pull_request.write": ("scm",),
    "host.issue_tracker.read": ("connectors",),
}


def host_contracts_path(root: Path) -> Path:
    """The one construction of the host contract path shared across scripts/registry."""
    return root / "scripts" / "registry" / "host_contracts.yaml"


def expected_surface(host: str) -> str:
    """The skill surface `host` must declare, with a named error for an unrostered host."""
    try:
        return EXPECTED_SURFACES[host]
    except KeyError:
        raise ValueError(
            f"host {host!r} has no expected skill surface; add it to "
            f"host_adapter.EXPECTED_SURFACES (known hosts: {sorted(EXPECTED_SURFACES)})"
        ) from None


def _contracts(root: Path) -> dict:
    return require_mapping(
        load_unique_yaml_file(host_contracts_path(root)),
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
    # Every host key must be a string before sorting -- a non-string key (e.g. a bare
    # numeric YAML key) makes sorted() raise TypeError comparing str to int, which
    # isn't a ValueError/OSError callers here catch, crashing with a raw traceback
    # instead of a clean error.
    non_string_hosts = sorted(str(key) for key in hosts if not isinstance(key, str))
    if non_string_hosts:
        raise ValueError(f"hosts keys must be strings, got non-string key(s): {non_string_hosts}")
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


def validate_host_adapter_identities(root: Path) -> list[str]:
    """Check adapter names against the checked-in host-parity contract."""
    expected_path = root / "evals" / "host-parity" / "expected.yaml"
    if not expected_path.is_file():
        return ["error: host parity expected contract missing"]
    try:
        contracts = _contracts(root)
        host_map = require_mapping(contracts.get("hosts"), "hosts")
        expected = require_mapping(load_unique_yaml_file(expected_path), "host parity expected")
        snapshots = require_mapping(expected.get("hosts"), "host parity expected hosts")
        errors: list[str] = []
        if expected.get("schema_version") != 1:
            errors.append("error: host parity expected schema_version must be 1")
        for label, mapping in (("hosts", host_map), ("host parity expected hosts", snapshots)):
            if any(not isinstance(key, str) for key in mapping):
                errors.append(f"error: {label} keys must be strings")
        if set(key for key in host_map if isinstance(key, str)) != HOSTS:
            errors.append("error: host contract coverage drift")
        if set(key for key in snapshots if isinstance(key, str)) != HOSTS:
            errors.append("error: host parity snapshot coverage drift")
        if errors:
            return errors
        for host in sorted(HOSTS):
            actual = require_mapping(host_map.get(host), f"hosts.{host}")
            snapshot = require_mapping(snapshots.get(host), f"host parity expected hosts.{host}")
            if actual.get("adapter") != snapshot.get("adapter"):
                errors.append(f"error: {host}: adapter identity drift")
        return errors
    except (OSError, TypeError, ValueError) as exc:
        return [f"error: host adapter identity: {exc}"]


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
    except (OSError, TypeError, ValueError) as exc:
        return [f"error: host adapter interface: {exc}"]
