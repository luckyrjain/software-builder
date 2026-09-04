from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from scripts.registry.host_adapter import HOSTS
from scripts.registry.host_registry import HostRegistryParseError, parse_host_registry
from scripts.registry.models import (
    CapabilitiesSpec,
    CapabilityOptional,
    CapabilityPath,
    CompositionSpec,
    HostDiscoverySpec,
    InstallSpec,
    LintSpec,
    Registry,
    SkillEntry,
)
from scripts.registry.manifest_merge import load_fragment_skills, skills_fragments_dir
from scripts.yaml_safety import load_unique_yaml_file
from scripts.yaml_safety import require_mapping as _require_mapping

ALLOWED_RISK_CLASSES = frozenset(
    {"posting", "merge", "unattended", "read-only", "repository-write"},
)
AUTOMATION_ONLY_INVOCATION = "automation-only"
ALLOWED_INVOCATION = {"ambient", AUTOMATION_ONLY_INVOCATION}
ALLOWED_CURSOR_DISCOVERY = {"rule", "manual", "always"}
ALLOWED_KIRO_DISCOVERY = {"manual", "always"}
# GitHub Copilot's documented behavior ("Skills are loaded when relevant based on the user's
# prompt and the skill's description") is an on-demand/semantic-match model, not an
# always-in-context one by default -- closer to Kiro's manual/always split than Cursor's three-way
# rule/manual/always vocabulary, so this reuses that narrower set rather than inventing a third.
ALLOWED_GITHUB_COPILOT_DISCOVERY = {"manual", "always"}
ALLOWED_COMPOSITION_MODE = {"invoke", "aggregate"}

# Fallback host set used only when a skills.yaml has no sibling agent-hosts.yaml (isolated test
# fixtures, mainly) -- matches this repository's real host set today so no existing fixture needs to
# change. Real callers (load_registry(root) against the actual repo root) always resolve the live set
# from agent-hosts.yaml instead, per Candidate 3 of the universal-agent-compatibility design.
_DEFAULT_HOST_IDS = frozenset({"cursor", "claude", "kiro"})

# Which field of HostDiscoverySpec a given host's `hosts.<id>` block populates. A host reusing an
# existing field kind (e.g. a future host with cursor/kiro-style discovery modes) needs only a new
# agent-hosts.yaml entry and, if it has its own discovery vocabulary, one entry here -- no new class.
_HOST_FIELD_KIND = {"cursor": "discovery", "kiro": "discovery", "claude": "install"}
_PER_HOST_ALLOWED_DISCOVERY: dict[str, frozenset[str]] = {
    "cursor": frozenset(ALLOWED_CURSOR_DISCOVERY),
    "kiro": frozenset(ALLOWED_KIRO_DISCOVERY),
    "github-copilot": frozenset(ALLOWED_GITHUB_COPILOT_DISCOVERY),
}


def _skill_host_ids(skills_yaml_path: Path) -> frozenset[str]:
    """The set of host ids a skill's `hosts:` block may/must declare.

    Driven by agent-hosts.yaml (the canonical host-identity registry, Candidate 2) when it exists next
    to the parsed skills.yaml; falls back to this repository's current host set only when no such file
    is present at all, so isolated test fixtures that construct a bare skills.yaml with no sibling
    registry keep working unchanged. A sibling agent-hosts.yaml that exists but fails to parse is a
    broken registry, not an absent one -- AD-11's fail-closed rule means that must surface as an error,
    not silently downgrade every skill's required host set to the stale 3-host default.
    """
    agent_hosts_path = skills_yaml_path.parent / "agent-hosts.yaml"
    if not agent_hosts_path.is_file():
        return _DEFAULT_HOST_IDS
    try:
        registry = parse_host_registry(agent_hosts_path)
    except (HostRegistryParseError, OSError, ValueError, yaml.YAMLError) as exc:
        raise RegistryParseError([f"{agent_hosts_path}: failed to parse: {exc}"]) from exc
    return frozenset(registry.hosts) or _DEFAULT_HOST_IDS


class RegistryParseError(ValueError):
    """Raised when one or more skills in skills.yaml have invalid shape.

    Subclasses ValueError so every existing `except ValueError` /
    `except YAML_SAFETY_ERRORS` call site keeps working unchanged. Unlike a
    plain ValueError, the message lists every broken skill's problem in one
    pass instead of just the first one found, so fixing skills.yaml doesn't
    mean fix-one/rerun/fix-the-next. Each skill's own fields are still
    validated fail-fast: a skill entry stops at its first bad field and
    moves on to the next skill, rather than accumulating every field of
    every skill -- a smaller, cheaper scope than field-level accumulation
    that still closes the actual complaint (unrelated skills no longer hide
    each other's errors).
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        # Every caller renders this as `f"error: {exc}"`; indent continuation
        # lines instead of leaving them bare so all N errors read as one
        # message block, not just the first with the rest looking unflagged.
        super().__init__("\n  ".join(errors))


def _coerce_int(value: Any, *, label: str) -> int:
    # bool is an int subclass and str is int()-coercible, so both need an explicit
    # type check before int() -- anything else (None, a list, a mapping) makes bare
    # int(value) raise TypeError, not ValueError, which callers here don't catch,
    # crashing with a raw traceback instead of a clean registry-parse error.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{label} must be an integer")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc


def resolve_registry_profiles(raw: Any) -> Any:
    """Merge each skill's `extends:` profile into its entry; strip `profiles`.

    Consumers that read skills.yaml's raw dict (with or without going through
    this module) should never see `extends`/`profiles` -- they see the same
    fully-inlined shape the registry had before profiles existed.
    """
    if not isinstance(raw, dict) or raw.get("profiles") is None:
        return raw
    profiles = raw["profiles"]
    if not isinstance(profiles, dict):
        raise ValueError("skills.yaml profiles must be a mapping")
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        return raw
    resolved: dict[str, Any] = {}
    for skill_id, entry in skills.items():
        if isinstance(entry, dict) and "extends" in entry:
            profile_name = entry["extends"]
            profile = profiles.get(profile_name) if isinstance(profile_name, str) else None
            if not isinstance(profile, dict):
                raise ValueError(f"skills.{skill_id}.extends: unknown profile {profile_name!r}")
            resolved[skill_id] = _deep_merge(
                profile,
                {key: value for key, value in entry.items() if key != "extends"},
            )
        else:
            resolved[skill_id] = entry
    result = dict(raw)
    result["skills"] = resolved
    del result["profiles"]
    return result


DEFAULT_ENTRYPOINT = "SKILL.md"


def apply_skill_defaults(raw: Any) -> Any:
    """Fill in the per-skill fields whose value is the same for every skill.

    `entrypoint` is `SKILL.md` for all 38 skills (`validate_canonical_manifest` rejects
    anything else), and `supported_hosts` is the full host roster (`host_adapter.HOSTS`, which
    the same validator already checks each skill against). Restating both in every fragment
    made them look like per-skill decisions and gave a new skill two more lines to copy
    wrongly. Declaring them stays legal and wins -- a skill that genuinely narrows its host
    set says so -- but omitting them now means "the default", resolved here so every consumer
    of the raw dict sees the same fully-inlined shape, exactly as `resolve_registry_profiles`
    does for `extends`.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("skills"), dict):
        return raw
    defaults = {"entrypoint": DEFAULT_ENTRYPOINT, "supported_hosts": sorted(HOSTS)}

    def with_defaults(entry: Any) -> Any:
        if not isinstance(entry, dict):
            return entry
        filled = dict(entry)
        for key, value in defaults.items():
            filled.setdefault(key, value)
        return filled

    skills = {skill_id: with_defaults(entry) for skill_id, entry in raw["skills"].items()}
    result = dict(raw)
    result["skills"] = skills
    return result


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


_registry_raw_cache: dict[tuple[Path, str], Any] = {}
_registry_cache: dict[tuple[Path, str], Registry] = {}


def clear_registry_cache() -> None:
    """Drop every cached `load_registry_raw` and `parse_registry` result.

    A single `make generate`/`make validate` invocation calls `parse_registry`/
    `load_registry_raw`/`load_canonical_manifest` (directly or transitively) at
    roughly 28 separate call sites across scripts/registry/ -- each independently
    re-reading and re-parsing the same skills.yaml, re-merging the same
    scripts/registry/skills.d/ fragments, and re-running the same
    has_canonical_manifest_shape check on the result. `load_registry_raw` caches
    per resolved root path instead.

    The two places that write to skills.yaml both call this immediately after:
    `cmd_generate`'s own `_write_outputs` step (so a later read in the same
    invocation -- e.g. a second `_prune_stale_adapters` pass -- sees the
    just-written state rather than a pre-write cache entry) and
    `cmd_backfill`'s `write_text` in backfill_capabilities.py. Neither call is
    load-bearing for the CLI's own real usage today -- every invocation is one
    subcommand per process, so nothing reads the cache again after `cmd_backfill`
    writes regardless -- but calling it there means `load_registry_raw` doesn't
    depend on that one-shot-process invariant to stay correct if a future caller
    (a library user, a batch script chaining subcommands in-process) breaks it.
    """
    _registry_raw_cache.clear()
    _registry_cache.clear()


def load_registry_raw(path: Path) -> Any:
    """Load skills.yaml's raw dict with `extends:` profile inheritance resolved.

    When `scripts/registry/skills.d/` exists next to `path` (skills.yaml split into
    per-skill authoring fragments, see manifest_merge.py), the `skills:` mapping is
    loaded fresh from those fragments rather than trusting `path`'s own `skills:`
    block, which may be stale until the next `make generate` writes the merged
    projection back to disk. This is the single choke point resolving that
    staleness for every parse_registry()/load_registry_raw() caller at once --
    including a skill that only exists as a new fragment and has never yet been
    merged into skills.yaml, which would otherwise be invisible to validation.

    Cached per resolved *root directory* (see clear_registry_cache) so the ~28
    call sites that share this one path within a single invocation don't each
    pay their own disk read + YAML parse + fragment merge. Every caller gets an
    independent deep copy of the cached value -- some callers (e.g.
    canonical_manifest.load_canonical_manifest) mutate the dict they get back,
    and must not corrupt the shared cache entry by doing so.

    Keyed on `(path.parent.resolve(), path.name)` -- the root directory's
    identity plus the filename -- not `path.resolve()` (the file's identity)
    alone. The root half guards the symlink case: the cached value depends on
    BOTH `path` itself AND `skills_fragments_dir(path.parent)`, which is derived
    from the *root*, not the file, so if only `skills.yaml` were symlinked
    across two otherwise-distinct roots with their own, different `skills.d/`
    fragments, keying on the file's resolved identity alone would conflate
    them -- root B's first read would populate the shared entry, and root A's
    read would then silently return root B's fragment-merged skills instead of
    its own. The filename half guards the sibling case: every current caller
    only ever passes `root / "skills.yaml"`, but the function itself accepts
    any `path`, and keying on the directory alone would silently return one
    file's content for a different file requested from the same directory.
    """
    cache_key = (path.parent.resolve(), path.name)
    if cache_key not in _registry_raw_cache:
        raw = load_unique_yaml_file(path)
        fragments_dir = skills_fragments_dir(path.parent)
        if fragments_dir.is_dir():
            raw = dict(_require_mapping(raw, str(path)))
            raw["skills"] = load_fragment_skills(path.parent)
        _registry_raw_cache[cache_key] = apply_skill_defaults(resolve_registry_profiles(raw))
    return copy.deepcopy(_registry_raw_cache[cache_key])


def parse_registry(path: Path) -> Registry:
    """The typed registry for one skills.yaml, memoized on the same key as its raw read.

    `load_registry_raw`'s cache removed the repeated disk read and fragment merge, but every
    caller still rebuilt the whole Registry/SkillEntry graph on top of it -- roughly nine
    full rebuilds per `registry validate`. The models are frozen dataclasses and nothing
    mutates `Registry.skills`, so callers can share one instance instead of each paying for
    how many times the registry is asked for. Invalidated by `clear_registry_cache`, the
    same seam that invalidates the raw layer; a parse that raises is not cached, so a
    repaired skills.yaml still reparses.
    """
    cache_key = (path.parent.resolve(), path.name)
    cached = _registry_cache.get(cache_key)
    if cached is not None:
        return cached
    raw = load_registry_raw(path)
    root = _require_mapping(raw, "skills.yaml root")
    schema_version = _coerce_int(root.get("schema_version", 0), label="schema_version")
    if schema_version != 1:
        raise ValueError(f"unsupported schema_version: {schema_version}")

    host_ids = _skill_host_ids(path)

    skills_raw = _require_mapping(root.get("skills"), "skills")
    skills: dict[str, SkillEntry] = {}
    errors: list[str] = []
    for skill_id, entry_raw in skills_raw.items():
        if not isinstance(skill_id, str):
            errors.append(f"skills.{skill_id!r}: skill id must be a string")
            continue
        try:
            skills[skill_id] = _parse_skill_entry(skill_id, entry_raw, host_ids)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise RegistryParseError(errors)
    registry = Registry(schema_version=schema_version, skills=skills)
    _registry_cache[cache_key] = registry
    return registry


def registered_skill_ids(path: Path) -> set[str]:
    """The set of skill ids skills.yaml declares.

    Thin wrapper around `parse_registry` for callers (validators, health reports) that only need
    the id set, not the full typed registry — reuses the one correct, validated read of
    skills.yaml instead of a second hand-rolled `raw.get("skills", {})` with its own error
    handling that can silently diverge from this one.
    """
    return set(parse_registry(path).skills)


def _parse_hosts(
    skill_id: str,
    hosts_raw: Any,
    host_ids: frozenset[str],
) -> dict[str, HostDiscoverySpec]:
    mapping = _require_mapping(hosts_raw, f"skills.{skill_id}.hosts")
    unknown = sorted(set(mapping) - host_ids)
    if unknown:
        raise ValueError(
            f"skills.{skill_id}.hosts declares host(s) not present in agent-hosts.yaml: {unknown}"
        )
    hosts: dict[str, HostDiscoverySpec] = {}
    for host_id in sorted(host_ids):
        label = f"skills.{skill_id}.hosts.{host_id}"
        host_raw = _require_mapping(mapping.get(host_id), label)
        if _HOST_FIELD_KIND.get(host_id, "discovery") == "install":
            hosts[host_id] = HostDiscoverySpec(install=bool(host_raw.get("install", True)))
            continue
        discovery = str(host_raw.get("discovery", ""))
        allowed = _PER_HOST_ALLOWED_DISCOVERY.get(host_id)
        if allowed is not None and discovery not in allowed:
            raise ValueError(f"{label}.discovery invalid: {discovery!r}")
        hosts[host_id] = HostDiscoverySpec(discovery=discovery)
    return hosts


def _parse_skill_entry(skill_id: str, entry_raw: Any, host_ids: frozenset[str]) -> SkillEntry:
    entry = _require_mapping(entry_raw, f"skills.{skill_id}")
    invocation = str(entry.get("invocation", ""))
    if invocation not in ALLOWED_INVOCATION:
        raise ValueError(f"skills.{skill_id}.invocation invalid: {invocation!r}")

    hosts = _parse_hosts(skill_id, entry.get("hosts"), host_ids)

    install_raw = _require_mapping(entry.get("install"), f"skills.{skill_id}.install")
    requires = install_raw.get("requires", [])
    if not isinstance(requires, list):
        raise ValueError(f"skills.{skill_id}.install.requires must be a list")

    lint_raw = _require_mapping(entry.get("lint"), f"skills.{skill_id}.lint")

    composition_raw = entry.get("composition")
    composition = _parse_composition(
        composition_raw,
        skill_id,
        [str(item) for item in requires],
    )
    capabilities = _parse_capabilities(entry.get("capabilities"), skill_id)
    risk_class = _parse_risk_class(entry.get("risk_class"), skill_id)

    return SkillEntry(
        path=str(entry.get("path", skill_id)),
        category=str(entry.get("category", "")),
        invocation=invocation,
        hosts=hosts,
        install=InstallSpec(requires=[str(item) for item in requires]),
        lint=LintSpec(
            skill_md_max_lines=_coerce_int(
                lint_raw.get("skill_md_max_lines", 180),
                label=f"skills.{skill_id}.lint.skill_md_max_lines",
            ),
            target=str(lint_raw.get("target", skill_id)),
        ),
        composition=composition,
        capabilities=capabilities,
        risk_class=risk_class,
    )


def _parse_composition(
    raw: Any,
    skill_id: str,
    install_requires: list[str],
) -> CompositionSpec:
    if raw is None:
        return CompositionSpec(invokes=list(install_requires), mode="invoke")
    composition = _require_mapping(raw, f"skills.{skill_id}.composition")
    mode = str(composition.get("mode", "invoke"))
    if mode not in ALLOWED_COMPOSITION_MODE:
        raise ValueError(f"skills.{skill_id}.composition.mode invalid: {mode!r}")

    invokes_raw = composition.get("invokes")
    if invokes_raw is None:
        invokes = [] if mode == "aggregate" else list(install_requires)
    else:
        if not isinstance(invokes_raw, list):
            raise ValueError(f"skills.{skill_id}.composition.invokes must be a list")
        invokes = [str(item) for item in invokes_raw]

    escalation_raw = composition.get("escalation_targets", [])
    if not isinstance(escalation_raw, list):
        raise ValueError(f"skills.{skill_id}.composition.escalation_targets must be a list")

    return CompositionSpec(
        invokes=invokes,
        escalation_targets=[str(item) for item in escalation_raw],
        mode=mode,
    )


def _parse_capabilities(raw: Any, skill_id: str) -> CapabilitiesSpec:
    if raw is None:
        return CapabilitiesSpec()
    capabilities = _require_mapping(raw, f"skills.{skill_id}.capabilities")

    required_raw = capabilities.get("required", [])
    if not isinstance(required_raw, list):
        raise ValueError(f"skills.{skill_id}.capabilities.required must be a list")

    optional_raw = capabilities.get("optional", [])
    if not isinstance(optional_raw, list):
        raise ValueError(f"skills.{skill_id}.capabilities.optional must be a list")
    optional = _parse_optional_capabilities(
        optional_raw,
        f"skills.{skill_id}.capabilities.optional",
    )

    any_of_raw = capabilities.get("any_of", [])
    if not isinstance(any_of_raw, list):
        raise ValueError(f"skills.{skill_id}.capabilities.any_of must be a list")
    any_of: list[CapabilityPath] = []
    for index, item in enumerate(any_of_raw):
        path = _require_mapping(item, f"skills.{skill_id}.capabilities.any_of[{index}]")
        name = str(path.get("name", ""))
        if not name:
            raise ValueError(f"skills.{skill_id}.capabilities.any_of[{index}].name is required")
        path_required = path.get("required", [])
        if not isinstance(path_required, list):
            raise ValueError(
                f"skills.{skill_id}.capabilities.any_of[{index}].required must be a list",
            )
        path_optional_raw = path.get("optional", [])
        if not isinstance(path_optional_raw, list):
            raise ValueError(
                f"skills.{skill_id}.capabilities.any_of[{index}].optional must be a list",
            )
        any_of.append(
            CapabilityPath(
                name=name,
                required=[str(item) for item in path_required],
                optional=_parse_optional_capabilities(
                    path_optional_raw,
                    f"skills.{skill_id}.capabilities.any_of[{index}].optional",
                ),
            ),
        )

    degraded_raw = capabilities.get("degraded_modes", {})
    if not isinstance(degraded_raw, dict):
        raise ValueError(f"skills.{skill_id}.capabilities.degraded_modes must be a mapping")
    degraded_modes = {str(key): str(value) for key, value in degraded_raw.items()}

    return CapabilitiesSpec(
        required=[str(item) for item in required_raw],
        optional=optional,
        any_of=any_of,
        degraded_modes=degraded_modes,
    )


def _parse_optional_capabilities(
    optional_raw: list[Any],
    label: str,
) -> list[CapabilityOptional]:

    optional: list[CapabilityOptional] = []
    for index, item in enumerate(optional_raw):
        if isinstance(item, str):
            optional.append(CapabilityOptional(name=item))
            continue
        if isinstance(item, dict):
            name = str(item.get("name", ""))
            if not name:
                raise ValueError(f"{label}[{index}].name is required")
            optional.append(
                CapabilityOptional(
                    name=name,
                    enables=str(item.get("enables", "")),
                ),
            )
            continue
        raise ValueError(f"{label}[{index}] must be a string or mapping")
    return optional


def _parse_risk_class(raw: Any, skill_id: str) -> list[str]:
    if raw is None:
        raise ValueError(f"skills.{skill_id}.risk_class is required")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"skills.{skill_id}.risk_class must be a non-empty list")
    parsed = [str(item) for item in raw]
    unknown = sorted({item for item in parsed if item not in ALLOWED_RISK_CLASSES})
    if unknown:
        raise ValueError(f"skills.{skill_id}.risk_class invalid values: {', '.join(unknown)}")
    return parsed
