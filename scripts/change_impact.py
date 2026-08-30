"""Deterministic, bounded change-impact analysis primitives.

This module deliberately performs shallow classification only. Repository evidence can identify
direct callers, consumers, contracts, and ownership metadata, but the analyzer never performs an
unbounded dependency-graph crawl.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from scripts.registry.artifact_trust import classify_assessment_context_trust
from scripts.registry.assessment_target import normalize_repo_identity

CHANGE_CLASSES = (
    "docs_only",
    "test_only",
    "build_tooling",
    "runtime_code",
    "api_contract",
    "schema_or_data",
    "infra_or_config",
    "dependency",
    "operational",
)

_DIFF_PATH = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.MULTILINE)
_LOCKFILES = {
    "package-lock.json",
    "npm-shrinkwrap.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "pipfile.lock",
    "go.sum",
    "cargo.lock",
    "composer.lock",
}
_DEPENDENCY_NAMES = {
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "cargo.toml",
    "pom.xml",
    "build.gradle",
}
_BUILD_TOOLING_NAMES = {"makefile", "justfile", "taskfile.yml", "taskfile.yaml"}
_INSTRUCTION_LINE = re.compile(
    r"^\s*(?:ignore|disregard|follow|obey|mark|set|treat|claim|report|do not|don't)\b.{0,120}\b(?:instruction|database|consumer|impact|status|complete|pass|fail|unknown|coverage)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NormalizedDecision:
    status: str
    raw_verdict: str


@dataclass(frozen=True)
class SkillExecutionResult:
    status: str
    blockers: list[str] | None = None
    state_semantic: str = "proposed_state"


@dataclass(frozen=True)
class AssessmentTarget:
    source_type: str | None = None
    repo: str | None = None
    service: str | None = None
    environment: str | None = None
    base_revision: str | None = None
    head_revision_or_digest: str | None = None


@dataclass(frozen=True)
class ImpactResult:
    payload: dict[str, Any]
    normalized_decision: NormalizedDecision
    skill_result: SkillExecutionResult
    provenance: dict[str, Any] | None = None

    @property
    def assessment_target(self) -> AssessmentTarget:
        target = self.payload.get("assessment_target", {})
        return AssessmentTarget(
            source_type=target.get("source_type"),
            repo=target.get("repo"),
            service=target.get("service"),
            environment=target.get("environment"),
            base_revision=target.get("base_revision"),
            head_revision_or_digest=target.get("head_revision_or_digest"),
        )

    def _completed_dod_checks(self, coverage: str | None) -> list[str]:
        """Derive which DoD checks genuinely completed, so PARTIAL reflects real gaps."""
        if self.skill_result.status not in {"SUCCESS", "PARTIAL"}:
            return []
        checks: list[str] = []
        # COMPLETE coverage means the target identity was confirmed against bounded, authoritative
        # repository evidence (see _coverage); anything less means normalization is unfinished.
        if coverage == "COMPLETE":
            checks.append("target_normalized")
        if self.payload.get("change_classes"):
            checks.append("change_classes_evaluated")
        if not self.payload.get("material_unknowns") and self.payload.get("evidence_refs"):
            checks.append("surfaces_and_unknowns_recorded")
        return checks

    def to_envelope(self) -> dict[str, Any]:
        """Serialize to the manifest-backed runtime result envelope."""
        target = self.assessment_target
        source_revision = target.head_revision_or_digest or "UNKNOWN"
        coverage = self.payload.get("coverage_status")
        sources = (self.provenance or {}).get("sources", [])
        observed_at = next(
            (item.get("observed_at") for item in sources if isinstance(item, Mapping) and item.get("observed_at")),
            "UNKNOWN",
        )
        confidence = {"COMPLETE": "HIGH", "PARTIAL": "MEDIUM", "UNKNOWN": "UNKNOWN"}.get(coverage, "UNKNOWN")
        if observed_at == "UNKNOWN":
            confidence = "UNKNOWN"
        payload = {field: self.payload.get(field) for field in REPORT_FIELDS}
        list_fields = {
            "material_unknowns", "impacted_repositories", "change_classes", "impacted_services",
            "impacted_contracts", "impacted_data", "impacted_dependencies", "impacted_owners",
            "required_tests", "operational_impacts", "review_triggers", "unknowns", "evidence_refs",
        }
        for field in REPORT_FIELDS:
            if payload[field] is None:
                payload[field] = [] if field in list_fields else {} if field == "assessment_target" else "UNKNOWN"
        completed_checks = self._completed_dod_checks(coverage)
        return {
            "skill_result": {
                "skill": "change-impact-analyzer",
                "version": "1.0.0",
                "status": self.skill_result.status,
                "confidence": confidence,
                "source_revision": source_revision,
                "evidence_status": "OBSERVED" if sources else "UNKNOWN",
                "artifacts": ["change_impact_report"],
                "blockers": self.skill_result.blockers or [],
                "recommended_next_skill": None,
                "artifact_schema_version": 1,
                "state_semantic": self.skill_result.state_semantic,
            },
            "provenance": {
                "source_revision": source_revision,
                # change_impact_report is registered as a v1 non-machine-summary artifact;
                # its envelope stores root refs as strings. Internal provenance retains typed
                # authority metadata for callers that need it before serialization.
                "sources": [
                    item["ref"] for item in sources if isinstance(item, Mapping) and item.get("ref")
                ],
            },
            "freshness": {
                "observed_at": observed_at,
                "source_revision": source_revision,
                "source_environment": target.environment or "UNKNOWN",
            },
            "definition_of_done": {
                "required_artifacts": ["change_impact_report"],
                "required_checks": ["target_normalized", "change_classes_evaluated", "surfaces_and_unknowns_recorded"],
                "completed_checks": completed_checks,
                "blocked_conditions": self.skill_result.blockers or [],
                "partial_result_behavior": "return PARTIAL or UNKNOWN with explicit evidence gaps",
            },
            "authority": {
                "write_authority": "read-only",
                "canonical_owner": "change-impact-analyzer",
            },
            "payload": payload,
        }
_DOC_SUFFIXES = (".md", ".mdx", ".rst", ".adoc", ".txt")
_TEST_MARKERS = ("/test/", "/tests/", "_test.", ".test.", ".spec.")
_CRITICALITY_TIERS = {"tier0", "tier1", "tier2", "tier3"}
REPORT_FIELDS = (
    "title", "assessment_target", "coverage_status", "material_unknowns",
    "impacted_repositories", "criticality", "change_classes", "impacted_services",
    "impacted_contracts", "impacted_data", "impacted_dependencies", "impacted_owners",
    "required_tests", "operational_impacts", "review_triggers", "unknowns", "evidence_refs",
)


def _as_mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _unique_strings(values: Iterable[object]) -> list[str]:
    return sorted({value.strip() for value in values if isinstance(value, str) and value.strip()})


def _source_mapping(source: object) -> dict[str, Any]:
    if isinstance(source, Mapping):
        result = dict(source)
        context = source.get("assessment_context")
        if isinstance(context, Mapping):
            inputs = context.get("inputs")
            if isinstance(inputs, Mapping):
                merged = dict(inputs)
                merged.update({key: value for key, value in result.items() if value is not None})
                result = merged
            if isinstance(context.get("input_provenance"), Mapping):
                result["input_provenance"] = dict(context["input_provenance"])
            if isinstance(context.get("evidence_refs"), list):
                result["evidence_refs"] = list(context["evidence_refs"])
            if isinstance(context.get("unresolved"), list):
                result["unresolved"] = list(context["unresolved"])
            if isinstance(context.get("assessment_target"), Mapping):
                result["assessment_target"] = dict(context["assessment_target"])
        return result
    if isinstance(source, str) and source.strip():
        return {"text": source, "source_type": "change"}
    return {}


def _diff_paths(text: str) -> list[str]:
    paths: list[str] = []
    for left, right in _DIFF_PATH.findall(text):
        if left == right:
            paths.append(right)
        else:
            paths.extend((left, right))
    return _unique_strings(paths)


def _changed_paths(source: Mapping[str, Any]) -> list[str]:
    paths = list(source.get("changed_paths", [])) if isinstance(source.get("changed_paths"), list) else []
    diff = source.get("diff_text")
    if isinstance(diff, str):
        paths.extend(_diff_paths(diff))
    return _unique_strings(paths)


def _source_text(source: Mapping[str, Any]) -> str:
    values = [source.get("text"), source.get("diff_text"), source.get("description")]
    return "\n".join(value for value in values if isinstance(value, str)).lower()


def _safe_source_text(source: Mapping[str, Any]) -> tuple[str, bool]:
    raw = _source_text(source)
    normalized_lines = [re.sub(r"^\s*[+-]\s?", "", line) for line in raw.splitlines()]
    safe_lines = [line for line in normalized_lines if not _INSTRUCTION_LINE.search(line)]
    return "\n".join(safe_lines), len(safe_lines) != len(raw.splitlines())


def _basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1].lower()


def _is_test_path(path: str) -> bool:
    normalized = f"/{path.replace('\\', '/').lower().strip('/')}/"
    basename = _basename(path)
    return any(marker in normalized for marker in _TEST_MARKERS) or basename in {"test.py", "tests.py"} or basename.startswith("test_")


def _classify_paths(paths: list[str], text: str) -> list[str]:
    if not paths:
        if any(marker in text for marker in ("openapi", "graphql", "event schema", "api contract")):
            return ["api_contract"]
        if any(marker in text for marker in ("migration", "schema", "database", "table")):
            return ["schema_or_data"]
        return ["runtime_code"] if text else []

    classes: set[str] = set()
    for path in paths:
        lowered = path.lower().replace("\\", "/")
        basename = _basename(lowered)
        path_classes: set[str] = set()
        if lowered.startswith(("docs/", "doc/")) or lowered.endswith(_DOC_SUFFIXES):
            path_classes.add("docs_only")
        if _is_test_path(lowered):
            path_classes.add("test_only")
        if basename in _LOCKFILES or basename in _DEPENDENCY_NAMES or basename.endswith((".lock", ".lockfile")):
            path_classes.add("dependency")
        if basename in _BUILD_TOOLING_NAMES or any(
            token in lowered for token in ("build/", "build-tools/", "ci/", ".github/workflows/", ".pre-commit")
        ):
            path_classes.add("build_tooling")
        if any(token in lowered for token in ("openapi", "swagger", "graphql", "api-schema", "event-schema")):
            path_classes.add("api_contract")
        if any(token in lowered for token in ("migration", "migrations/", "schema", "database", ".sql")):
            path_classes.add("schema_or_data")
        if any(token in lowered for token in ("k8s/", "kubernetes/", "helm/", "terraform/", "ansible/", "dockerfile", ".github/", "deployment", "infra/", "config/")):
            path_classes.add("infra_or_config")
        if any(token in lowered for token in ("monitor", "alert", "dashboard", "slo", "observability", "logging")):
            path_classes.add("operational")
        if not path_classes:
            path_classes.add("runtime_code")
        classes.update(path_classes)

    # A path containing a more specific class is not also runtime code unless a separate source
    # path clearly warrants it. This keeps docs-only and test-only assertions deterministic.
    if len(paths) == 1 and ("docs_only" in classes or "test_only" in classes):
        classes.discard("runtime_code")
    if not classes:
        classes.add("runtime_code")
    return [item for item in CHANGE_CLASSES if item in classes]


def _triggers(classes: list[str], text: str, paths: list[str]) -> list[str]:
    lowered = f"{text}\n{' '.join(paths).lower()}"
    triggers: set[str] = set()
    if "api_contract" in classes or any(token in lowered for token in ("api contract", "openapi", "graphql", "endpoint")):
        triggers.add("api")
    if "schema_or_data" in classes or any(token in lowered for token in ("schema", "migration", "database", "table", "backfill")):
        triggers.add("database")
    if any(token in lowered for token in ("authn", "authz", "authentication", "authorization", "secret", "crypto", "trust boundary", "data exposure")):
        triggers.add("security")
    if any(token in lowered for token in ("hot-path", "hot path", "n+1", "cache", "concurrency", "pool", "fanout", "fan-out")):
        triggers.add("performance")
    if any(token in lowered for token in ("demand", "headroom", "replica", "replicas", "hpa", "resources:", "limits:", "requests:")):
        triggers.add("capacity")
    if any(token in lowered for token in ("metrics", "logs", "traces", "slo", "alerts", "correlation")):
        triggers.add("observability")
    if any(token in lowered for token in ("timeout", "retry", "backpressure", "circuit-breaker", "partial failure", "recovery")):
        triggers.add("resilience")
    if "dependency" in classes or any(token in lowered for token in ("dependency", "framework", "lockfile", "package-lock", "version bump")):
        triggers.add("dependency_upgrade")
    if any(token in lowered for token in ("k8s", "kubernetes", "hpa", "resources:", "limits:", "requests:")):
        triggers.add("k8s_rightsizing")
    return sorted(triggers)


def _coverage(source: Mapping[str, Any], repository_evidence: Mapping[str, Any], unknowns: list[str]) -> str:
    source_type = str(source.get("source_type", "")).lower()
    if not source:
        return "UNKNOWN"
    if source_type in {"pull_request", "merge_request", "pr", "mr"}:
        exact = bool(source.get("base_revision") and source.get("head_revision_or_digest"))
        complete_diff = source.get("diff_complete") is True
        exact_repository_evidence = (
            repository_evidence.get("exact_revision") is True
            and repository_evidence.get("base_sha") == source.get("base_revision")
            and repository_evidence.get("head_sha") == source.get("head_revision_or_digest")
            and repository_evidence.get("bounded_discovery_complete") is True
            and repository_evidence.get("final_head_verified") is True
            and _has_authoritative_evidence(repository_evidence)
        )
        if exact and complete_diff and exact_repository_evidence:
            return "COMPLETE" if not unknowns else "PARTIAL"
        return "UNKNOWN" if not repository_evidence else "PARTIAL"
    if unknowns:
        return "PARTIAL"
    if not repository_evidence:
        return "PARTIAL"
    if repository_evidence.get("bounded_discovery_complete") is not True or not _has_authoritative_evidence(repository_evidence):
        return "PARTIAL"
    return "COMPLETE"


def _canonical_repositories(source: Mapping[str, Any], repository: Mapping[str, Any]) -> list[str]:
    values: list[object] = []
    for owner in (source, repository):
        candidates = owner.get("impacted_repositories")
        if isinstance(candidates, list):
            values.extend(candidates)
    normalized: list[str] = []
    for value in values:
        if isinstance(value, str) and value.strip():
            normalized.append(normalize_repo_identity(value))
    return sorted(set(normalized))


def _criticality(source: Mapping[str, Any], repository: Mapping[str, Any]) -> str:
    authoritative: list[str] = []
    direct = repository.get("criticality")
    if isinstance(direct, str) and direct.strip().lower() in _CRITICALITY_TIERS:
        authoritative.append(direct.strip().lower())
    by_repo = repository.get("criticality_by_repository")
    if isinstance(by_repo, Mapping):
        for value in by_repo.values():
            if isinstance(value, str) and value.strip().lower() in _CRITICALITY_TIERS:
                authoritative.append(value.strip().lower())
    authoritative = sorted(set(authoritative))
    if len(authoritative) > 1:
        return "unknown"

    trusted = repository.get("trusted_criticality")
    if not isinstance(trusted, str):
        trusted = source.get("trusted_criticality")
    trusted_value = trusted.strip().lower() if isinstance(trusted, str) else ""
    caller = source.get("criticality")
    caller_value = caller.strip().lower() if isinstance(caller, str) else ""
    candidates = [value for value in (trusted_value, caller_value) if value in _CRITICALITY_TIERS]
    if authoritative:
        candidates.append(authoritative[0])
    if not candidates:
        return "unknown"
    # Lower tier number is more critical. Caller/trusted claims can conservatively raise risk but
    # never reduce an authoritative tier.
    return min(candidates, key=lambda value: int(value[-1]))


def _owners(source: Mapping[str, Any], repository: Mapping[str, Any], repositories: list[str]) -> list[str]:
    by_repo = repository.get("owners_by_repository")
    values: list[object] = []
    if isinstance(by_repo, Mapping):
        normalized_map = {
            normalize_repo_identity(key): value
            for key, value in by_repo.items()
            if isinstance(key, str)
        }
        for repo in repositories:
            owner_value = normalized_map.get(repo)
            if isinstance(owner_value, list):
                values.extend(owner_value)
            elif isinstance(owner_value, str):
                values.append(owner_value)
    if not values:
        direct = repository.get("impacted_owners")
        if isinstance(direct, list):
            values.extend(direct)
    owners = _unique_strings(values)
    return owners or ["UNKNOWN — ownership evidence unavailable; recommend squad-map"]


def _surface_values(
    source: Mapping[str, Any], repository: Mapping[str, Any], key: str
) -> list[str]:
    values: list[object] = []
    for owner in (repository, source):
        candidate = owner.get(key)
        if isinstance(candidate, list):
            values.extend(candidate)
    return _unique_strings(values)


def _evidence_refs(source: Mapping[str, Any], repository: Mapping[str, Any]) -> list[str]:
    refs: list[Any] = []
    for owner in (repository, source):
        candidate = owner.get("evidence_refs")
        if isinstance(candidate, list):
            refs.extend(item for item in candidate if isinstance(item, (str, Mapping)))
    deduplicated: list[str] = []
    seen: set[str] = set()
    for item in refs:
        ref = item if isinstance(item, str) else item.get("ref")
        key = ref if isinstance(ref, str) else repr(item)
        if key not in seen:
            seen.add(key)
            if isinstance(ref, str) and ref.strip():
                deduplicated.append(ref)
    return deduplicated


def _has_authoritative_evidence(repository: Mapping[str, Any]) -> bool:
    provenance = repository.get("provenance")
    if not isinstance(provenance, Mapping) or not isinstance(provenance.get("sources"), list):
        return False
    return any(
        isinstance(item, Mapping)
        and item.get("authority") in {"authoritative_host", "repository"}
        and item.get("kind") in {"scm", "repo_content"}
        and isinstance(item.get("ref"), str)
        and item.get("ref")
        for item in provenance["sources"]
    )


def _result_provenance(
    source: object, repository_evidence: object, *, runtime_metadata: object = None
) -> dict[str, Any]:
    source_map = _source_mapping(source)
    repository = _as_mapping(repository_evidence)
    context = source.get("assessment_context") if isinstance(source, Mapping) else None
    trust = classify_assessment_context_trust(context, runtime_metadata=runtime_metadata)
    sources: list[dict[str, Any]] = []
    for owner, authority in ((repository, "repository"), (source_map, "caller")):
        candidate_refs = owner.get("evidence_refs")
        if not isinstance(candidate_refs, list):
            continue
        for item in candidate_refs:
            if isinstance(item, str):
                ref = item
                kind = "caller_input"
            elif isinstance(item, Mapping):
                ref = item.get("ref")
                kind = str(item.get("kind") or item.get("type") or "caller_input")
            else:
                continue
            if isinstance(ref, str) and ref.strip() and not any(
                entry["ref"] == ref for entry in sources
            ):
                entry = {
                    "ref": ref,
                    "authority": authority,
                    "kind": kind,
                }
                if isinstance(item, Mapping):
                    for field in ("observed_at", "source_revision", "source_environment", "derived_from"):
                        if field in item:
                            entry[field] = item[field]
                sources.append(entry)
    repository_provenance = repository.get("provenance")
    if isinstance(repository_provenance, Mapping) and isinstance(repository_provenance.get("sources"), list):
        for item in repository_provenance["sources"]:
            if not isinstance(item, Mapping) or not isinstance(item.get("ref"), str):
                continue
            if any(entry["ref"] == item["ref"] for entry in sources):
                continue
            sources.append(dict(item))
    input_provenance = source_map.get("input_provenance")
    if isinstance(input_provenance, Mapping):
        for input_key, metadata in input_provenance.items():
            if not isinstance(metadata, Mapping):
                continue
            refs = metadata.get("evidence_refs")
            if not isinstance(refs, list):
                continue
            for ref in refs:
                ref_value = ref if isinstance(ref, str) else ref.get("ref") if isinstance(ref, Mapping) else None
                if not isinstance(ref_value, str) or not ref_value.strip():
                    continue
                # Caller-controlled metadata cannot attest to a stronger authority. Runtime-owned
                # handoff metadata is required before an external source can be elevated.
                authority = trust.effective_authority(input_key)
                existing = next((entry for entry in sources if entry["ref"] == ref_value), None)
                if existing is not None:
                    # A ref already claimed (e.g. from the flat evidence_refs list, always tagged
                    # "caller") is upgraded in place when a runtime handoff vouches for the same
                    # input; an already-stronger authority from elsewhere is never weakened.
                    if existing["authority"] == "caller" and authority != "caller":
                        existing["authority"] = authority
                    continue
                entry = {
                    "ref": ref_value,
                    "authority": authority,
                    "kind": str(metadata.get("kind") or "caller_input"),
                }
                for field in ("observed_at", "source_revision", "source_environment"):
                    if field in metadata:
                        entry[field] = metadata[field]
                sources.append(entry)
    return {"sources": sources}


def analyze_change(
    *,
    source: object,
    repository_evidence: object = None,
) -> dict[str, Any]:
    """Analyze one supplied change/design using bounded evidence only."""
    source_map = _source_mapping(source)
    repository = _as_mapping(repository_evidence)
    paths = _changed_paths(source_map)
    text, ignored_instructions = _safe_source_text(source_map)
    classes = _classify_paths(paths, text)
    if source_map.get("events") and "api_contract" not in classes:
        classes = [item for item in CHANGE_CLASSES if item in {*classes, "api_contract"}]
    triggers = _triggers(classes, text, paths)
    unknowns: list[str] = []
    if ignored_instructions:
        unknowns.append("instruction-like source text was treated as untrusted data")

    if source_map.get("source_type") in {"pull_request", "merge_request", "pr", "mr"}:
        if source_map.get("diff_complete") is not True:
            unknowns.append("exact complete PR/MR diff was not supplied")
        if not source_map.get("base_revision") or not source_map.get("head_revision_or_digest"):
            unknowns.append("exact PR/MR base and head identity is unavailable")
    if isinstance(source_map.get("partial_diff"), bool) and source_map["partial_diff"]:
        unknowns.append("change diff is partial")
    unresolved = repository.get("unresolved_consumers")
    unresolved_values = list(unresolved) if isinstance(unresolved, list) else []
    parent_unresolved = source_map.get("unresolved")
    if isinstance(parent_unresolved, list):
        unresolved_values.extend(parent_unresolved)
    unknowns.extend(str(item) for item in unresolved_values if str(item).strip())
    if source_map.get("events") and not repository.get("direct_consumers") and not unresolved_values:
        unknowns.append("direct event consumer evidence is unavailable")

    repositories = _canonical_repositories(source_map, repository)
    services = _surface_values(source_map, repository, "impacted_services")
    contracts = _surface_values(source_map, repository, "impacted_contracts")
    data = _surface_values(source_map, repository, "impacted_data")
    dependencies = _surface_values(source_map, repository, "impacted_dependencies")
    tests = _surface_values(source_map, repository, "required_tests")
    operational = _surface_values(source_map, repository, "operational_impacts")
    if "api_contract" in classes and not contracts:
        unknowns.append("affected API or event contracts are not identified by authoritative evidence")
    if "schema_or_data" in classes and not data:
        unknowns.append("affected schema or data artifacts are not identified by authoritative evidence")
    if "dependency" in classes and not dependencies:
        unknowns.append("affected dependency names are not identified by authoritative evidence")
    if not tests:
        unknowns.append("required test evidence is unavailable")
    embedded_target = _as_mapping(source_map.get("assessment_target"))
    target = {
        "source_type": str(source_map.get("source_type") or embedded_target.get("source_type") or "change"),
        "repo": source_map.get("repo") or embedded_target.get("repo"),
        "service": source_map.get("service") or embedded_target.get("service"),
        "environment": source_map.get("environment") or embedded_target.get("environment"),
        "base_revision": source_map.get("base_revision") or embedded_target.get("base_revision"),
        "head_revision_or_digest": source_map.get("head_revision_or_digest") or embedded_target.get("head_revision_or_digest"),
    }
    return {
        "title": "Change impact analysis",
        "assessment_target": target,
        "coverage_status": _coverage(source_map, repository, unknowns),
        "material_unknowns": _unique_strings(unknowns),
        "impacted_repositories": repositories,
        "criticality": _criticality(source_map, repository),
        "change_classes": classes,
        "impacted_services": services,
        "impacted_contracts": contracts,
        "impacted_data": data,
        "impacted_dependencies": dependencies,
        "impacted_owners": _owners(source_map, repository, repositories),
        "required_tests": tests,
        "operational_impacts": operational,
        "review_triggers": triggers,
        "unknowns": _unique_strings(unknowns),
        "evidence_refs": _evidence_refs(source_map, repository),
    }


def analyze_pr_impact(
    mr_context: Mapping[str, Any],
    *,
    scm_change_read: object = None,
    assessment_context: object = None,
    final_head_reader: Callable[[], str] | None = None,
    runtime_metadata: object = None,
) -> ImpactResult:
    """Analyze a remote PR/MR only at the supplied exact head revision."""
    context = _as_mapping(mr_context)
    scm = _as_mapping(scm_change_read)
    head_sha = context.get("head_sha") if isinstance(context.get("head_sha"), str) else None
    source: dict[str, Any] = {
        "source_type": "pull_request",
        "repo": context.get("project"),
        "merge_request_iid": context.get("merge_request_iid"),
        "impacted_repositories": [context["project"]] if isinstance(context.get("project"), str) else [],
        "head_revision_or_digest": head_sha,
        "base_revision": scm.get("base_sha"),
        "diff_text": scm.get("diff_text"),
        "diff_complete": scm.get("diff_complete") is True,
    }
    if assessment_context is not None:
        source["assessment_context"] = assessment_context
    if not isinstance(scm.get("diff_text"), str):
        source.pop("diff_text", None)
    if not isinstance(scm.get("base_sha"), str):
        source.pop("base_revision", None)
    if "diff_complete" not in scm:
        source.pop("diff_complete", None)
    identity_matches = (
        isinstance(scm.get("head_sha"), str)
        and scm.get("head_sha") == head_sha
        and scm.get("final_head_sha") == head_sha
        and scm.get("project") == context.get("project")
        and scm.get("merge_request_iid") == context.get("merge_request_iid")
    )
    final_head_verified = identity_matches
    if callable(final_head_reader):
        try:
            final_head_verified = final_head_reader() == head_sha
        except Exception:
            final_head_verified = False
    if not identity_matches:
        source["diff_complete"] = False
    if scm_change_read is None:
        source["diff_complete"] = False
    repository = dict(scm.get("repository_evidence")) if isinstance(scm.get("repository_evidence"), Mapping) else {}
    for field in ("base_sha", "head_sha"):
        if field in scm and field not in repository:
            repository[field] = scm[field]
    repository["final_head_verified"] = final_head_verified
    result = run_impact(
        change_source=source,
        repository_evidence=repository or None,
        runtime_metadata=runtime_metadata,
    )
    if not isinstance(scm_change_read, Mapping) or not scm_change_read:
        return ImpactResult(
            payload=result.payload,
            normalized_decision=NormalizedDecision("UNKNOWN", "MISSING_EXACT_SCM_MATERIAL"),
            skill_result=SkillExecutionResult(
                "BLOCKED",
                ["exact remote SCM change material is unavailable"],
                "current_state",
            ),
            provenance=result.provenance,
        )
    return result


def finalize_impact(impact: Mapping[str, Any]) -> ImpactResult:
    """Map impact coverage to a decision and independent execution status."""
    payload = dict(impact)
    blockers = payload.get("blockers", [])
    if not isinstance(blockers, list):
        blockers = ["invalid blockers value"]
    normalized_blockers = _unique_strings(blockers)
    impact_blockers = payload.get("impact_blockers", [])
    if not isinstance(impact_blockers, list):
        impact_blockers = ["invalid impact_blockers value"]
    impact_blockers = _unique_strings(impact_blockers)
    if impact_blockers:
        payload["operational_impacts"] = _unique_strings(
            [
                *(payload.get("operational_impacts", []) if isinstance(payload.get("operational_impacts"), list) else []),
                *(f"BLOCKER: {item}" for item in impact_blockers),
            ],
        )
    payload.pop("blockers", None)
    payload.pop("impact_blockers", None)
    coverage = payload.get("coverage_status")
    state_semantic = "current_state" if str(payload.get("assessment_target", {}).get("source_type", "")).lower() in {"pull_request", "merge_request", "pr", "mr"} else "proposed_state"
    if normalized_blockers:
        return ImpactResult(
            payload=payload,
            normalized_decision=NormalizedDecision("UNKNOWN", "BLOCKED"),
            skill_result=SkillExecutionResult("BLOCKED", normalized_blockers, state_semantic),
        )
    if coverage == "COMPLETE" and impact_blockers:
        return ImpactResult(
            payload=payload,
            normalized_decision=NormalizedDecision("FAIL", "IMPACT_BLOCKER"),
            skill_result=SkillExecutionResult("SUCCESS", [], state_semantic),
        )
    if coverage == "COMPLETE" and payload.get("material_unknowns"):
        return ImpactResult(
            payload=payload,
            normalized_decision=NormalizedDecision("UNKNOWN", "MATERIAL_UNKNOWNS"),
            skill_result=SkillExecutionResult("PARTIAL", [], state_semantic),
        )
    if coverage == "COMPLETE":
        if not payload.get("evidence_refs"):
            return ImpactResult(
                payload=payload,
                normalized_decision=NormalizedDecision("UNKNOWN", "MISSING_EVIDENCE_REFS"),
                skill_result=SkillExecutionResult("PARTIAL", [], state_semantic),
            )
        return ImpactResult(
            payload=payload,
            normalized_decision=NormalizedDecision("PASS", "COMPLETE"),
            skill_result=SkillExecutionResult("SUCCESS", [], state_semantic),
        )
    if coverage in {"PARTIAL", "UNKNOWN"}:
        return ImpactResult(
            payload=payload,
            normalized_decision=NormalizedDecision("UNKNOWN", str(coverage)),
            skill_result=SkillExecutionResult("PARTIAL", [], state_semantic),
        )
    return ImpactResult(
        payload=payload,
        normalized_decision=NormalizedDecision("UNKNOWN", "INVALID_COVERAGE"),
        skill_result=SkillExecutionResult("FAILED", [], state_semantic),
    )


def run_impact(
    *, change_source: object, repository_evidence: object = None, runtime_metadata: object = None
) -> ImpactResult:
    """Execute the documented Inputs -> Analyze -> Report path."""
    if not change_source or (isinstance(change_source, str) and not change_source.strip()):
        result = finalize_impact(
            {
                "title": "Change impact analysis",
                "assessment_target": {"source_type": "change"},
                "coverage_status": "UNKNOWN",
                "material_unknowns": ["primary change source is missing"],
                "unknowns": ["primary change source is missing"],
                "blockers": ["primary change source is missing"],
            },
        )
        return ImpactResult(
            payload=result.payload,
            normalized_decision=result.normalized_decision,
            skill_result=result.skill_result,
            provenance=_result_provenance(change_source, repository_evidence, runtime_metadata=runtime_metadata),
        )
    result = finalize_impact(
        analyze_change(source=change_source, repository_evidence=repository_evidence),
    )
    return ImpactResult(
        payload=result.payload,
        normalized_decision=result.normalized_decision,
        skill_result=result.skill_result,
        provenance=_result_provenance(change_source, repository_evidence, runtime_metadata=runtime_metadata),
    )
