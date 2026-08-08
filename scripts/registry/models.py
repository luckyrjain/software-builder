from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class HostCursor:
    discovery: str


@dataclass(frozen=True)
class HostClaude:
    install: bool = True


@dataclass(frozen=True)
class HostKiro:
    discovery: str


@dataclass(frozen=True)
class Hosts:
    cursor: HostCursor
    claude: HostClaude
    kiro: HostKiro


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
class CapabilitiesSpec:
    required: list[str] = field(default_factory=list)
    optional: list[CapabilityOptional] = field(default_factory=list)
    degraded_modes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillEntry:
    path: str
    category: str
    invocation: str
    hosts: Hosts
    install: InstallSpec
    lint: LintSpec
    composition: CompositionSpec = field(default_factory=CompositionSpec)
    capabilities: CapabilitiesSpec = field(default_factory=CapabilitiesSpec)


@dataclass(frozen=True)
class Registry:
    schema_version: int
    skills: dict[str, SkillEntry]
