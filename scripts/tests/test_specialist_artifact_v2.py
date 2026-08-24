from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def _decision(status: str, raw_verdict: str) -> dict[str, str]:
    return {"status": status, "raw_verdict": raw_verdict}


def security_decision(verdict: str) -> dict[str, str]:
    if verdict == "Pass":
        return _decision("PASS", verdict)
    if verdict == "Pass with findings":
        return _decision("CONDITIONAL", verdict)
    if verdict.startswith("Fail"):
        return _decision("FAIL", verdict)
    if verdict.startswith("Blocked"):
        return _decision("UNKNOWN", verdict)
    return _decision("UNKNOWN", verdict)


def performance_decision(
    verdict: str,
    *,
    unknown_required_areas: Iterable[str] = (),
) -> dict[str, str]:
    unknown = list(unknown_required_areas)
    if verdict.startswith("Fail"):
        return _decision("FAIL", verdict)
    if unknown:
        return _decision("UNKNOWN", verdict)
    if verdict == "Pass":
        return _decision("PASS", verdict)
    if verdict == "Pass with findings":
        return _decision("CONDITIONAL", verdict)
    return _decision("UNKNOWN", verdict)


def capacity_decision(headroom: str) -> dict[str, str]:
    return {
        "Sufficient": _decision("PASS", headroom),
        "Marginal": _decision("CONDITIONAL", headroom),
        "Insufficient": _decision("FAIL", headroom),
        "Unknown — insufficient historical data": _decision("UNKNOWN", headroom),
    }.get(headroom, _decision("UNKNOWN", headroom))


def observability_decision(
    coverage: str,
    *,
    unknown_categories: Iterable[str] = (),
) -> dict[str, str]:
    unknown = list(unknown_categories)
    if coverage == "Critical gaps":
        return _decision("FAIL", coverage)
    if unknown:
        return _decision("UNKNOWN", coverage)
    return {
        "Adequate": _decision("PASS", coverage),
        "Partial gaps": _decision("CONDITIONAL", coverage),
        "Critical gaps": _decision("FAIL", coverage),
        "Unknown — insufficient input": _decision("UNKNOWN", coverage),
    }.get(coverage, _decision("UNKNOWN", coverage))


def deployment_decision(*, risk: str, confidence: str) -> dict[str, str]:
    if risk == "Critical":
        return _decision("FAIL", risk)
    if risk == "High" and confidence == "UNKNOWN":
        return _decision("UNKNOWN", risk)
    if risk == "High":
        return _decision("FAIL", risk)
    if risk == "Low" and confidence == "HIGH":
        return _decision("PASS", risk)
    if risk in {"Low", "Moderate"}:
        return _decision("CONDITIONAL", risk)
    return _decision("UNKNOWN", risk)


def dependency_decision(
    verdict: str,
    *,
    unknown_required_checks: Iterable[str] = (),
) -> dict[str, str]:
    unknown = list(unknown_required_checks)
    if verdict == "Do not upgrade yet":
        return _decision("FAIL", verdict)
    if unknown:
        return _decision("UNKNOWN", verdict)
    return {
        "Safe to upgrade": _decision("PASS", verdict),
        "Upgrade with mitigations": _decision("CONDITIONAL", verdict),
        "Do not upgrade yet": _decision("FAIL", verdict),
        "Blocked — insufficient info": _decision("UNKNOWN", verdict),
    }.get(verdict, _decision("UNKNOWN", verdict))


def specialist_machine_result(
    *,
    artifact_type: str,
    raw_fields: Mapping[str, Any],
    normalized_decision: Mapping[str, str],
) -> dict[str, Any]:
    return {
        **dict(raw_fields),
        "assessment_target": {"kind": "repository", "repo": "acme/service"},
        "normalized_decision": dict(normalized_decision),
        "findings": [],
        "conditions": [],
        "required_actions": [],
        "evidence_refs": [f"repo:{artifact_type}"],
    }


def nonblocking_finding(category: str) -> dict[str, Any]:
    return {
        "id": f"{category}-001",
        "category": category,
        "summary": "non-blocking finding",
        "blocking": False,
        "evidence_status": "OBSERVED",
        "evidence_refs": [f"repo:{category}"],
    }


def security_machine_result(*, verdict: str) -> dict[str, Any]:
    return specialist_machine_result(
        artifact_type="security_review_report",
        raw_fields={"title": "Security review", "verdict": verdict},
        normalized_decision=security_decision(verdict),
    )


def performance_machine_result(
    *,
    verdict: str,
    findings: list[dict[str, Any]] | None = None,
    unknown_required_areas: list[str] | None = None,
) -> dict[str, Any]:
    result = specialist_machine_result(
        artifact_type="performance_review_report",
        raw_fields={"title": "Performance review", "verdict": verdict},
        normalized_decision=performance_decision(
            verdict,
            unknown_required_areas=unknown_required_areas or [],
        ),
    )
    result["findings"] = findings or []
    return result


def capacity_machine_result(*, headroom: str) -> dict[str, Any]:
    return specialist_machine_result(
        artifact_type="capacity_plan",
        raw_fields={"title": "Capacity plan", "headroom": headroom},
        normalized_decision=capacity_decision(headroom),
    )


def observability_machine_result(
    *,
    coverage: str,
    unknown_categories: list[str] | None = None,
) -> dict[str, Any]:
    return specialist_machine_result(
        artifact_type="observability_review_report",
        raw_fields={"title": "Observability review", "coverage": coverage},
        normalized_decision=observability_decision(
            coverage,
            unknown_categories=unknown_categories or [],
        ),
    )


def deployment_machine_result(*, risk: str, confidence: str) -> dict[str, Any]:
    return specialist_machine_result(
        artifact_type="deployment_risk_report",
        raw_fields={
            "title": "Deployment risk",
            "risk": risk,
            "deployment_confidence": confidence,
        },
        normalized_decision=deployment_decision(risk=risk, confidence=confidence),
    )


def dependency_machine_result(
    *,
    verdict: str,
    unknown_required_checks: list[str] | None = None,
) -> dict[str, Any]:
    return specialist_machine_result(
        artifact_type="dependency_upgrade_report",
        raw_fields={"title": "Dependency upgrade", "verdict": verdict},
        normalized_decision=dependency_decision(
            verdict,
            unknown_required_checks=unknown_required_checks or [],
        ),
    )


def test_performance_pass_with_findings_plus_unknown_is_unknown() -> None:
    result = performance_machine_result(
        verdict="Pass with findings",
        findings=[nonblocking_finding("cache")],
        unknown_required_areas=["concurrency"],
    )
    assert result["normalized_decision"]["status"] == "UNKNOWN"


def test_performance_known_minor_finding_is_conditional() -> None:
    result = performance_machine_result(
        verdict="Pass with findings",
        findings=[nonblocking_finding("cache")],
        unknown_required_areas=[],
    )
    assert result["normalized_decision"]["status"] == "CONDITIONAL"


def test_performance_proven_failure_is_not_downgraded_by_unknown_area() -> None:
    result = performance_machine_result(
        verdict="Fail — regression risk",
        unknown_required_areas=["concurrency"],
    )
    assert result["normalized_decision"]["status"] == "FAIL"


def test_capacity_unknown_history_is_unknown() -> None:
    result = capacity_machine_result(headroom="Unknown — insufficient historical data")
    assert result["normalized_decision"]["status"] == "UNKNOWN"


def test_observability_missing_category_is_unknown() -> None:
    result = observability_machine_result(
        coverage="Unknown — insufficient input",
        unknown_categories=["alerts"],
    )
    assert result["normalized_decision"]["status"] == "UNKNOWN"


def test_observability_critical_gap_is_not_downgraded_by_unknown_category() -> None:
    result = observability_machine_result(
        coverage="Critical gaps",
        unknown_categories=["alerts"],
    )
    assert result["normalized_decision"]["status"] == "FAIL"


def test_critical_risk_is_fail() -> None:
    result = deployment_machine_result(risk="Critical", confidence="HIGH")
    assert result["normalized_decision"]["status"] == "FAIL"


def test_high_risk_unknown_confidence_is_unknown() -> None:
    result = deployment_machine_result(risk="High", confidence="UNKNOWN")
    assert result["normalized_decision"]["status"] == "UNKNOWN"


def test_critical_risk_is_not_downgraded_by_unknown_confidence() -> None:
    result = deployment_machine_result(risk="Critical", confidence="UNKNOWN")
    assert result["normalized_decision"]["status"] == "FAIL"


def test_low_risk_high_confidence_is_pass() -> None:
    result = deployment_machine_result(risk="Low", confidence="HIGH")
    assert result["normalized_decision"]["status"] == "PASS"


def test_dependency_missing_advisory_data_is_unknown() -> None:
    result = dependency_machine_result(
        verdict="Blocked — insufficient info",
        unknown_required_checks=["cve-advisory"],
    )
    assert result["normalized_decision"]["status"] == "UNKNOWN"


def test_dependency_proven_blocker_is_not_downgraded_by_missing_advisory() -> None:
    result = dependency_machine_result(
        verdict="Do not upgrade yet",
        unknown_required_checks=["cve-advisory"],
    )
    assert result["normalized_decision"]["status"] == "FAIL"
