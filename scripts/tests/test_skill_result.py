from scripts.change_impact import finalize_impact
from scripts.implementation_plan import finalize_plan
from scripts.registry.envelope_contract import COMPLETION_STATUSES, EVIDENCE_STATUSES
from scripts.registry.skill_result import SkillResult, derive_execution_status
from scripts.release_readiness_v2 import finalize_release
from scripts.production_readiness import Dimension, aggregate_readiness


def test_blockers_outrank_unknowns_and_both_outrank_success() -> None:
    assert derive_execution_status(blockers=["a"], unknowns=["b"]) == ("BLOCKED", "UNKNOWN")
    assert derive_execution_status(blockers=["a"]) == ("BLOCKED", "UNKNOWN")
    assert derive_execution_status(unknowns=["b"]) == ("PARTIAL", "UNKNOWN")
    assert derive_execution_status() == ("SUCCESS", "OBSERVED")


def test_carriers_are_taken_by_emptiness_not_by_type() -> None:
    assert derive_execution_status(unknowns=set()) == ("SUCCESS", "OBSERVED")
    assert derive_execution_status(unknowns={"timeout_budgets"}) == ("PARTIAL", "UNKNOWN")
    assert derive_execution_status(blockers=({"id": "missing"},)) == ("BLOCKED", "UNKNOWN")


def test_derived_values_stay_inside_the_declared_vocabularies() -> None:
    for blockers, unknowns in (([], []), ([], ["u"]), (["b"], [])):
        status, evidence_status = derive_execution_status(blockers=blockers, unknowns=unknowns)
        assert status in COMPLETION_STATUSES
        assert evidence_status in EVIDENCE_STATUSES


def test_defaults_describe_an_unevidenced_proposal() -> None:
    result = SkillResult(status="PARTIAL")
    assert (result.evidence_status, result.blockers, result.state_semantic) == (
        "UNKNOWN",
        (),
        "proposed_state",
    )


def test_every_assessment_module_reports_through_the_one_carrier() -> None:
    # Four modules previously declared their own carrier type; they now share this one, so the
    # axis split has a single definition to test rather than four to keep in sync.
    readiness = aggregate_readiness([Dimension("ci", "UNKNOWN", evidence_status="UNKNOWN")])
    assert (readiness.skill_result_status, readiness.evidence_status) == ("PARTIAL", "UNKNOWN")
    carriers = [
        finalize_release({"overall": "READY", "unknown_dimensions": ["ci"]}).skill_result,
        finalize_impact({"coverage_status": "PARTIAL"}).skill_result,
        finalize_plan({"readiness": "PARTIAL"}).skill_result,
    ]
    for carrier in carriers:
        assert isinstance(carrier, SkillResult)
        assert carrier.status in COMPLETION_STATUSES
    # The two whose only unresolved input is a declared unknown land on the same PARTIAL.
    assert [carrier.status for carrier in carriers[:2]] == ["PARTIAL", "PARTIAL"]
