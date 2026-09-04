import pytest

from scripts.registry.validation_primitives import (
    as_mapping,
    enum_value,
    non_empty_str,
    run_validator_cli,
    string_list,
    unknown_fields,
)


def test_as_mapping_degrades_by_default_and_raises_only_when_asked() -> None:
    assert as_mapping({"a": 1}) == {"a": 1}
    for malformed in ([], "a", None, 3):
        assert as_mapping(malformed) == {}
    with pytest.raises(TypeError):
        as_mapping([], strict=True, label="candidate")


def test_non_empty_str_rejects_whitespace_and_non_strings() -> None:
    assert non_empty_str("a") is True
    assert non_empty_str("   ") is False
    assert non_empty_str(b"a") is False
    assert non_empty_str(None) is False


def test_string_list_reports_shape_emptiness_and_duplicates_independently() -> None:
    assert string_list(["a"], "field") == []
    assert string_list("a", "field") == ["error: field must be a list of non-empty strings"]
    assert string_list([""], "field") == ["error: field must be a list of non-empty strings"]
    assert string_list([], "field") == []
    assert string_list([], "field", allow_empty=False) == ["error: field must not be empty"]
    assert string_list(["a", "a"], "field") == []
    assert string_list(["a", "a"], "field", unique=True) == ["error: field must not contain duplicates"]


def test_enum_value_fails_closed_on_an_unhashable_candidate() -> None:
    assert enum_value("PASS", {"PASS", "FAIL"}, "status") == []
    assert enum_value(["PASS"], {"PASS", "FAIL"}, "status") == [
        "error: status must be one of: FAIL, PASS",
    ]
    assert enum_value(None, {"PASS"}, "status") == ["error: status must be one of: PASS"]


def test_unknown_fields_lists_undeclared_keys_and_degrades_on_a_non_mapping() -> None:
    assert unknown_fields({"a": 1, "c": 2, "b": 3}, {"a"}) == ["b", "c"]
    assert unknown_fields("not-a-mapping", {"a"}) == []


def test_unknown_fields_reports_non_string_keys_instead_of_crashing() -> None:
    """YAML admits non-string keys; an undeclared `1:` beside an undeclared `b:` is still a
    finding, not an unorderable comparison."""
    assert unknown_fields({"a": 1, "b": 2, 1: 3, None: 4}, {"a"}) == [1, None, "b"]


def test_run_validator_cli_reports_per_path_and_returns_one_on_any_failure(capsys) -> None:
    documents = {"good.yaml": [], "bad.yaml": ["error: broken"]}
    exit_code = run_validator_cli(
        ["good.yaml", "bad.yaml", "missing.yaml"],
        load=lambda path: (path.name, "unreadable" if path.name == "missing.yaml" else None),
        validate=lambda name: documents.get(name, []),
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "good.yaml: ok" in captured.out
    assert "bad.yaml: validation failed" in captured.err
    assert "  - error: broken" in captured.err
    assert "missing.yaml: unreadable" in captured.err


def test_run_validator_cli_uses_default_paths_when_given_no_arguments(capsys) -> None:
    exit_code = run_validator_cli(
        [],
        load=lambda path: (path.name, None),
        validate=lambda _name: [],
        default_paths=["fallback.yaml"],
    )
    assert exit_code == 0
    assert "fallback.yaml: ok" in capsys.readouterr().out
