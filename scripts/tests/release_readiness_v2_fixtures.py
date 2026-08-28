"""Shared test fixtures/harnesses for scripts/tests/test_release_readiness_v2.py.

Plain builder functions, matching this repo's existing convention (see
scripts/tests/production_readiness_fixtures.py) of module-level helper
functions rather than pytest fixtures.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

from scripts.registry.canonical_manifest import load_canonical_manifest
from scripts.registry.load import load_registry
from scripts import release_readiness_v2

ROOT = Path(__file__).resolve().parents[2]

_DEFAULT_REVISION = "a" * 40
_DEFAULT_DIGEST = "sha256:" + "b" * 64


# ---------------------------------------------------------------------------
# v1/v2 golden parser fixture
# ---------------------------------------------------------------------------


def legacy_parse(entry: Mapping[str, Any]) -> Mapping[str, Any]:
    """The v1 manifest shape, captured before the v2 parser existed: exactly
    {repo, service, since, release_ref}. Never modified after being captured --
    the point of this fixture is a frozen reference, not a second implementation
    that could drift alongside the real parser.
    """
    return {
        "repo": entry.get("repo"),
        "service": entry.get("service"),
        "since": entry.get("since"),
        "release_ref": entry.get("release_ref"),
    }


# ---------------------------------------------------------------------------
# Manifest entry fixtures
# ---------------------------------------------------------------------------


def v1_entry(**overrides: Any) -> dict:
    base = {"repo": "acme/payments", "service": "payments", "since": "v1.2.3"}
    base.update(overrides)
    return base


def v2_entry(
    *,
    required: bool = False,
    repo: str = "acme/checkout",
    service: str = "checkout",
    since: str = "v2.0.0",
    environment: str | None = None,
    source_revision: str | None = _DEFAULT_REVISION,
    release_ref: str = _DEFAULT_DIGEST,
    criticality: str | None = None,
    **overrides: Any,
) -> dict:
    entry = {
        "repo": repo,
        "service": service,
        "since": since,
        "environment": environment,
        "source_revision": source_revision,
        "release_ref": release_ref,
        "criticality": criticality,
        "production_readiness_required": required,
        "production_readiness_ref": None,
    }
    entry.update(overrides)
    return entry


# ---------------------------------------------------------------------------
# production_readiness_report fixtures
# ---------------------------------------------------------------------------


def trusted_production_report(
    *,
    verdict: str = "READY",
    repo: str = "acme/checkout",
    service: str = "checkout",
    environment: str | None = None,
    deployable: str = _DEFAULT_DIGEST,
    source_revision: str | None = _DEFAULT_REVISION,
    acquisition: str = "runtime_validated",
    producer_trusted: bool = True,
    report_ref: str | None = None,
    **extra: Any,
) -> dict:
    result = {
        "artifact_type": "production_readiness_report",
        "assessment_target": {
            "repo": repo,
            "service": service,
            "environment": environment,
            "head_revision_or_digest": deployable,
        },
        "source_revision": source_revision,
        "verdict": verdict,
        "acquisition": acquisition,
        "producer_trusted": producer_trusted,
        "report_ref": report_ref,
        "dimension_statuses": [],
        "conditions": [],
        "waivers": [],
        "evidence_refs": ["production-readiness:1"],
    }
    result.update(extra)
    return result


def file_supplied_production_report(*, verdict: str = "READY", **overrides: Any) -> dict:
    return trusted_production_report(
        verdict=verdict,
        acquisition="repository_file",
        **overrides,
    )


# ---------------------------------------------------------------------------
# Release-level result fixture (Task 7.5)
# ---------------------------------------------------------------------------


def release_fixture(*, overall: str = "READY", unknown_dimensions: Sequence[str] | None = None, **extra: Any) -> dict:
    return {"overall": overall, "unknown_dimensions": list(unknown_dimensions or []), **extra}


# ---------------------------------------------------------------------------
# Dispatch / spy fixtures
# ---------------------------------------------------------------------------


def spy(*, return_value: Any = None):
    calls = {"count": 0}

    class _Spy:
        def __call__(self, *args: Any, **kwargs: Any) -> Any:
            calls["count"] += 1
            return return_value

        @property
        def calls(self) -> int:
            return calls["count"]

    return _Spy()


def release_check_spy():
    executed: list = []

    class _CheckSpy:
        executed_checks = executed

        def run(self, name: str) -> dict:
            executed.append(name)
            return {"status": "PASS"}

    return _CheckSpy()


# ---------------------------------------------------------------------------
# Registry helpers (read the real canonical manifest/runtime)
# ---------------------------------------------------------------------------


def registry():
    return load_registry(ROOT)


def invoked_skills(skill_id: str) -> list[str]:
    return list(registry().skills[skill_id].composition.invokes)


def runtime_handoff_artifacts(parent: str, child: str) -> list[str]:
    manifest = load_canonical_manifest(ROOT)
    handoffs = manifest["contracts"]["composition_runtime"]["handoffs"]
    return list(handoffs.get(parent, {}).get(child, []))


def consumes(skill_id: str, artifact_type: str) -> bool:
    manifest = load_canonical_manifest(ROOT)
    contract = manifest["contracts"]["composition"]["skills"].get(skill_id, {})
    return artifact_type in contract.get("consumes", [])


def default_max_depth() -> int:
    manifest = load_canonical_manifest(ROOT)
    return manifest["contracts"]["composition_runtime"]["recursion_guard"]["default_max_depth"]


def max_release_v2_composition_depth() -> int:
    # release-readiness-checker (root, depth 0) -> production-readiness-review
    # (depth 1) -> prerequisite/specialist leaf (depth 2).
    return 2


def child_context(*, parent: str, child: str, depth: int) -> dict:
    # Tied to the real registry, not pure arithmetic: fails if this edge isn't
    # actually a registered runtime handoff, so a future removal of the
    # release->production composition edge breaks this fixture instead of
    # silently leaving the depth assertion vacuous.
    if not runtime_handoff_artifacts(parent, child):
        raise AssertionError(f"no registered runtime handoff from {parent!r} to {child!r}")
    return {"parent": parent, "child": child, "depth": depth + 1}


def grandchild_context(*, root: str, parent: str, child: str) -> dict:
    if not runtime_handoff_artifacts(root, parent):
        raise AssertionError(f"no registered runtime handoff from {root!r} to {parent!r}")
    if not runtime_handoff_artifacts(parent, child):
        raise AssertionError(f"no registered runtime handoff from {parent!r} to {child!r}")
    return {"root": root, "parent": parent, "child": child, "depth": 2}


# ---------------------------------------------------------------------------
# Task 5.5 end-to-end harnesses
# ---------------------------------------------------------------------------


class Trace(list):
    def __init__(self, items: Sequence[str], *, production_readiness_invoked_pr_review: bool = False) -> None:
        super().__init__(items)
        self.production_readiness_invoked_pr_review = production_readiness_invoked_pr_review


def expected_release_pr_review_invocations() -> int:
    # release-readiness-checker's own existing-checks pass invokes pr-review
    # exactly once per manifest entry; production-readiness-review must reuse
    # that release-assembled coverage rather than invoking pr-review again.
    return 1


def run_v2_release_with_complete_review_coverage() -> Trace:
    trace: list = []

    class _CheckSpy:
        executed_checks = trace

        def run(self, name: str) -> dict:
            trace.append(name.replace("_", "-"))
            return {"status": "PASS"}

    coverage = release_readiness_v2.build_code_review_coverage(
        candidate_source_revision=_DEFAULT_REVISION,
        repo="acme/checkout",
        service="checkout",
        included_change_refs=["mr:1"],
        trusted_review_refs=["mr:1"],
    )

    invoked_pr_review_in_child = {"value": False}

    def production_invoke(candidate: Mapping[str, Any], *, assessment_context: Mapping[str, Any] | None = None):
        supplied_coverage = (assessment_context or {}).get("inputs", {}).get("code_review_coverage")
        if not supplied_coverage or supplied_coverage.get("status") != "COMPLETE":
            invoked_pr_review_in_child["value"] = True
            trace.append("pr-review")
        return trusted_production_report(verdict="READY")

    entry = v2_entry(required=True, source_revision=_DEFAULT_REVISION)
    release_readiness_v2.run_release(
        entry,
        trusted_reports=[],
        production_invoke=production_invoke,
        check_spy=_CheckSpy(),
        code_review_coverage=coverage,
    )
    return Trace(trace, production_readiness_invoked_pr_review=invoked_pr_review_in_child["value"])


def run_v2_release_with_uncovered_change():
    trace: list = []

    class _CheckSpy:
        executed_checks = trace

        def run(self, name: str) -> dict:
            trace.append(name.replace("_", "-"))
            return {"status": "PASS"}

    coverage = release_readiness_v2.build_code_review_coverage(
        candidate_source_revision=_DEFAULT_REVISION,
        repo="acme/checkout",
        service="checkout",
        included_change_refs=["mr:1", "commit:2"],
        trusted_review_refs=["mr:1"],
    )

    invoked_pr_review_in_child = {"value": False}

    def production_invoke(candidate: Mapping[str, Any], *, assessment_context: Mapping[str, Any] | None = None):
        # Must never be reached: incomplete release-assembled coverage short-
        # circuits to UNKNOWN before any child invocation is attempted.
        invoked_pr_review_in_child["value"] = True
        trace.append("pr-review")
        return trusted_production_report(verdict="READY")

    entry = v2_entry(required=True, source_revision=_DEFAULT_REVISION)
    result = release_readiness_v2.run_release(
        entry,
        trusted_reports=[],
        production_invoke=production_invoke,
        check_spy=_CheckSpy(),
        code_review_coverage=coverage,
    )
    # A plain wrapper, never a mutation of the real ReleaseResult dataclass --
    # `production_readiness_invoked_pr_review` here is this fixture's OWN
    # bookkeeping of whether its fake `production_invoke` was ever called,
    # not something the real run_release return value claims to observe.
    return SimpleNamespace(
        overall=result.overall,
        production_readiness_invoked_pr_review=invoked_pr_review_in_child["value"],
    )
