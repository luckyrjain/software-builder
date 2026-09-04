import math

import pytest

from scripts.registry.assessment_target import (
    canonical_payload_digest,
    canonical_text_digest,
    normalize_environment_identity,
    normalize_repo_identity,
    safe_same_environment,
    same_environment,
    target_of,
)


def test_payload_digest_is_key_order_independent() -> None:
    assert canonical_payload_digest({"b": 2, "a": 1}) == canonical_payload_digest({"a": 1, "b": 2})


def test_payload_digest_rejects_non_json_numbers() -> None:
    with pytest.raises(ValueError):
        canonical_payload_digest({"value": math.nan})


def test_text_digest_normalizes_crlf_only() -> None:
    assert canonical_text_digest("a\r\nb\r\n") == canonical_text_digest("a\nb\n")


def test_environment_aliases_do_not_fuzzy_match() -> None:
    assert normalize_environment_identity(" PROD ") == "prod"
    assert normalize_environment_identity("production") == "production"
    assert same_environment("prod", "production") is False


def test_repo_normalization_does_not_alias_different_paths() -> None:
    assert normalize_repo_identity("https://GitHub.com/acme/a.git") == "https://github.com/acme/a"
    assert normalize_repo_identity("https://github.com/acme/a") != normalize_repo_identity("https://github.com/acme/b")


def test_target_of_prefers_a_nested_carrier_over_flat_identity_fields() -> None:
    nested = {"source_revision": "b" * 40}
    assert target_of({"assessment_target": nested, "source_revision": "a" * 40}) is nested
    assert target_of({"target": nested, "head_sha": "a" * 40}) is nested


def test_target_of_falls_back_to_the_object_and_degrades_on_a_malformed_carrier() -> None:
    flat = {"head_sha": "a" * 40}
    assert target_of(flat) is flat
    malformed = {"assessment_target": "not-a-mapping", "head_sha": "a" * 40}
    assert target_of(malformed) is malformed
    assert target_of({"unrelated": 1}) is None
    assert target_of("not-a-mapping") is None


def test_safe_same_environment_fails_closed_on_a_malformed_operand() -> None:
    assert safe_same_environment("prod", "prod") is True
    assert safe_same_environment(["prod"], "prod") is False
    assert safe_same_environment(None, None) is False
