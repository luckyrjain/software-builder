from __future__ import annotations

from scripts.registry.id_diff import report_id_coverage


def test_no_errors_when_sets_match() -> None:
    assert report_id_coverage({"a", "b"}, {"a", "b"}, dangling_label="d", missing_label="m") == []


def test_dangling_and_missing_reported_separately() -> None:
    errors = report_id_coverage({"a", "c"}, {"a", "b"}, dangling_label="dangling", missing_label="missing")
    assert any("dangling" in e and "c" in e for e in errors)
    assert any("missing" in e and "b" in e for e in errors)


def test_exempt_ids_are_not_reported_as_dangling() -> None:
    errors = report_id_coverage(
        {"a", "exempt-one"},
        {"a"},
        dangling_label="dangling",
        missing_label="missing",
        exempt=frozenset({"exempt-one"}),
    )
    assert errors == []
