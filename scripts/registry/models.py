from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HostDiscoverySpec:
    """One host's entry in a skill's `hosts:` block.

    Generic across host types instead of one dataclass per host (see
    docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md Candidate 3): a host using
    discovery-mode semantics (cursor, kiro) populates `discovery`; a host using install-flag semantics
    (claude) populates `install`. Which field a given host uses is schema.py's HOST_FIELD_KIND table, not
    a property of this class -- adding a host that reuses an existing field kind needs no new class.
    """

    discovery: str | None = None
    install: bool | None = None


@dataclass(frozen=True)
class InstallSpec:
    requires: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class LintSpec:
    skill_md_max_lines: int
    target: str


@dataclass(frozen=True)
class CompositionSpec:
    invokes: list[str] = field(default_factory=list)
    escalation_targets: list[str] = field(default_factory=list)
    mode: str = "invoke"


@dataclass(frozen=True)
class CapabilityOptional:
    name: str
    enables: str = ""


@dataclass(frozen=True)
class CapabilityPath:
    name: str
    required: list[str] = field(default_factory=list)
    optional: list[CapabilityOptional] = field(default_factory=list)


@dataclass(frozen=True)
class CapabilitiesSpec:
    required: list[str] = field(default_factory=list)
    optional: list[CapabilityOptional] = field(default_factory=list)
    any_of: list[CapabilityPath] = field(default_factory=list)
    degraded_modes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillEntry:
    path: str
    category: str
    invocation: str
    hosts: dict[str, HostDiscoverySpec]
    install: InstallSpec
    lint: LintSpec
    composition: CompositionSpec = field(default_factory=CompositionSpec)
    capabilities: CapabilitiesSpec = field(default_factory=CapabilitiesSpec)
    risk_class: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Registry:
    schema_version: int
    skills: dict[str, SkillEntry]
