from pathlib import Path
import importlib.util
import itertools
import re
import shutil
import subprocess
import sys

import pytest
import yaml

from scripts.validate_workflow_contracts import (
    PhaseContract,
    RoutePredicateResult,
    _check_predicate_types,
    validate_skill_contract,
)


FIXTURES = Path(__file__).parent / "fixtures" / "workflow-contracts"
ROOT = Path(__file__).resolve().parents[2]

_RENDERER_SPEC = importlib.util.spec_from_file_location(
    "prd_safe_output", ROOT / "prd-architect" / "scripts" / "prd_safe_output.py"
)
assert _RENDERER_SPEC and _RENDERER_SPEC.loader
_RENDERER = importlib.util.module_from_spec(_RENDERER_SPEC)
_RENDERER_SPEC.loader.exec_module(_RENDERER)
render_gate_output = _RENDERER.render_gate_output
normalize_untrusted_markdown = _RENDERER.normalize_untrusted_markdown


def test_accepts_route_when_required_inputs_are_available_with_matching_types() -> None:
    assert validate_skill_contract(FIXTURES / "valid") == []


def test_rejects_required_input_missing_on_one_route() -> None:
    errors = validate_skill_contract(FIXTURES / "missing-producer")

    assert errors == [
        "route 'short': phase 'emit' requires 'draft', but no required entry input "
        "or preceding phase produces it",
    ]


def test_rejects_external_input_without_an_entry_schema() -> None:
    errors = validate_skill_contract(FIXTURES / "undeclared-entry")

    assert errors == [
        "route 'default': phase 'parse' requires 'request', but no required entry input "
        "or preceding phase produces it",
    ]


def test_rejects_incompatible_producer_and_consumer_types() -> None:
    errors = validate_skill_contract(FIXTURES / "type-mismatch")

    assert errors == [
        "route 'default': phase 'emit' consumes 'summary' as 'string', but the "
        "available type is 'object'",
    ]


def test_rejects_optional_input_that_is_impossible_on_the_route() -> None:
    errors = validate_skill_contract(FIXTURES / "impossible-optional")

    assert errors == [
        "route 'default': phase 'emit' optionally consumes 'notes', but no declared "
        "entry input or preceding phase produces it",
    ]


def test_rejects_conditional_optional_input_that_is_impossible_on_the_route() -> None:
    errors = validate_skill_contract(FIXTURES / "impossible-conditional-optional")

    assert errors == [
        "route 'short': phase 'emit' optionally consumes 'draft', but no declared "
        "entry input or preceding phase produces it",
    ]


def test_rejects_route_without_when_predicate() -> None:
    assert validate_skill_contract(FIXTURES / "missing-when") == [
        "route 'default'.when must be a non-empty mapping",
    ]


def test_rejects_unknown_route_predicate_input() -> None:
    assert validate_skill_contract(FIXTURES / "unknown-predicate") == [
        "route 'default'.when references unknown or unavailable predicate input 'missing'",
    ]


def test_rejects_optional_unproduced_route_selector() -> None:
    assert validate_skill_contract(FIXTURES / "optional-selector") == [
        "route 'default'.when references unknown or unavailable predicate input 'mode'",
    ]


def test_accepts_route_selector_produced_by_preceding_phase() -> None:
    assert validate_skill_contract(FIXTURES / "produced-selector") == []


def test_rejects_malformed_route_predicate() -> None:
    assert validate_skill_contract(FIXTURES / "malformed-predicate") == [
        "route 'default'.when.request must be a scalar equality or a single "
        "'not_equals' predicate",
    ]


def test_rejects_route_predicate_value_with_wrong_type() -> None:
    assert validate_skill_contract(FIXTURES / "predicate-type-mismatch") == [
        "route 'default'.when.enabled value is incompatible with declared type 'boolean'",
    ]


def test_rejects_unknown_contract_key() -> None:
    assert validate_skill_contract(FIXTURES / "unknown-contract-key") == [
        "workflow-contract.yaml unknown keys: route_seletion",
    ]


def test_rejects_unknown_nested_contract_keys() -> None:
    assert validate_skill_contract(FIXTURES / "unknown-nested-keys") == [
        "entry_inputs.request unknown keys: requird",
        "route_selection unknown keys: after_phaze",
        "route 'default' unknown keys: phasez",
    ]


def test_rejects_unknown_phase_consumes_key() -> None:
    assert validate_skill_contract(FIXTURES / "unknown-phase-consumes-key") == [
        "phase 'parse'.consumes unknown keys: optionel",
    ]


def test_rejects_unknown_conditional_route_input_key() -> None:
    assert validate_skill_contract(FIXTURES / "unknown-conditional-route-input-key") == [
        "phase 'parse'.consumes.conditional.default unknown keys: requird",
    ]


def test_rejects_missing_phase_consumes_sections() -> None:
    assert validate_skill_contract(FIXTURES / "missing-consumes-sections") == [
        "phase 'parse'.consumes missing keys: conditional, optional",
        "phase 'parse'.consumes.optional must be a mapping of field names to types",
        "phase 'parse'.consumes.conditional must be a mapping",
    ]


def test_rejects_equality_predicate_value_outside_selector_domain() -> None:
    assert validate_skill_contract(FIXTURES / "predicate-outside-domain") == [
        "route 'default'.when.mode value 'typo' is not in selector_domains.mode",
    ]


def test_rejects_not_equals_predicate_value_outside_selector_domain() -> None:
    assert validate_skill_contract(FIXTURES / "not-equals-outside-domain") == [
        "route 'default'.when.mode value 'typo' is not in selector_domains.mode",
    ]


def test_rejects_overlapping_route_predicates() -> None:
    assert validate_skill_contract(FIXTURES / "overlapping-routes") == [
        "routes 'default' and 'override' have overlapping when predicates",
    ]


def test_rejects_routes_with_different_preselection_phase_order() -> None:
    assert validate_skill_contract(FIXTURES / "different-prefix") == [
        "route 'short' selection prefix ['select'] differs from common prefix "
        "['parse', 'select']",
    ]


def test_rejects_route_missing_selection_phase() -> None:
    assert validate_skill_contract(FIXTURES / "missing-selection-phase") == [
        "route 'default' must include route-selection phase 'select' exactly once; found 0",
    ]


def test_rejects_route_with_duplicate_selection_phase() -> None:
    assert validate_skill_contract(FIXTURES / "duplicate-selection-phase") == [
        "route 'default' must include route-selection phase 'select' exactly once; found 2",
    ]


def test_rejects_uncovered_selector_state() -> None:
    assert validate_skill_contract(FIXTURES / "incomplete-routes") == [
        "selector state {mode='b'} is not covered by any route",
    ]


def test_accepts_exhaustive_boolean_routes() -> None:
    assert validate_skill_contract(FIXTURES / "exhaustive-boolean") == []


def test_accepts_exhaustive_enum_routes() -> None:
    assert validate_skill_contract(FIXTURES / "exhaustive-enum") == []


def _write_boolean_selector_contract(skill: Path, field_count: int, *, exhaustive: bool) -> None:
    fields = [f"flag_{index}" for index in range(field_count)]
    routes = {}
    states = itertools.product([False, True], repeat=field_count) if exhaustive else [()]
    for index, values in enumerate(states):
        when = dict(zip(fields, values, strict=True)) if exhaustive else {
            field: False for field in fields
        }
        routes[f"route_{index}"] = {"when": when, "phases": ["parse", "emit"]}
    data = yaml.safe_load((skill / "workflow-contract.yaml").read_text(encoding="utf-8"))
    data["entry_inputs"].update({
        field: {"type": "boolean", "provenance": "user", "required": True, "trust": "trusted"}
        for field in fields
    })
    data["selector_domains"] = {field: [False, True] for field in fields}
    data["routes"] = routes
    (skill / "workflow-contract.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False), encoding="utf-8"
    )


def test_rejects_selector_cartesian_space_before_product(tmp_path: Path) -> None:
    skill = _copy_valid_contract(tmp_path)
    _write_boolean_selector_contract(skill, 9, exhaustive=False)

    assert validate_skill_contract(skill) == [
        "selector Cartesian space has 512 states; maximum is 256"
    ]


def test_accepts_selector_cartesian_space_at_documented_boundary(tmp_path: Path) -> None:
    skill = _copy_valid_contract(tmp_path)
    _write_boolean_selector_contract(skill, 8, exhaustive=True)

    assert validate_skill_contract(skill) == []


def test_rejects_duplicate_route_id_at_nested_mapping_level() -> None:
    assert validate_skill_contract(FIXTURES / "duplicate-route-id") == [
        "invalid workflow-contract.yaml: duplicate YAML mapping key 'default'",
    ]


def test_rejects_duplicate_nested_typed_frontmatter_field() -> None:
    assert validate_skill_contract(FIXTURES / "duplicate-phase-field") == [
        "parse.md: duplicate YAML mapping key 'summary'",
    ]


def test_prd_architect_review_routes_cover_all_declared_selector_states() -> None:
    assert validate_skill_contract(ROOT / "prd-architect") == []

    contract = yaml.safe_load((ROOT / "prd-architect" / "workflow-contract.yaml").read_text())
    assert contract["selector_domains"]["premise_verdict"] == [
        "Strong",
        "Reasonable but unvalidated",
        "Weak",
        "Fundamentally flawed",
    ]
    flawed_review_states = [
        ({"critique_only": False, "user_insists_on_full_prd": False}, "flawed_review_stop"),
        ({"critique_only": True, "user_insists_on_full_prd": False}, "flawed_review_stop"),
        ({"critique_only": False, "user_insists_on_full_prd": True}, "flawed_review_override"),
        ({"critique_only": True, "user_insists_on_full_prd": True}, "flawed_review_override"),
    ]
    for flags, expected_route in flawed_review_states:
        state = {"response_mode": "Review", "premise_verdict": "Fundamentally flawed", **flags}
        matches = []
        for route_id, route in contract["routes"].items():
            matched = True
            for name, predicate in route["when"].items():
                if isinstance(predicate, dict):
                    matched = matched and state[name] != predicate["not_equals"]
                else:
                    matched = matched and state[name] == predicate
            if matched:
                matches.append(route_id)
        assert matches == [expected_route]


def test_rejects_incomplete_flawed_review_override_state() -> None:
    assert validate_skill_contract(FIXTURES / "incomplete-review-routes") == [
        "selector state {critique_only=True, mode='Review', premise='Flawed', "
        "user_insists=True} is not covered by any route",
    ]


def _copy_valid_contract(tmp_path: Path) -> Path:
    target = tmp_path / "skill"
    shutil.copytree(FIXTURES / "valid", target)
    return target


def _rewrite_yaml(path: Path, mutate) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _rewrite_phase(path: Path, mutate) -> None:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    data = yaml.safe_load(frontmatter)
    mutate(data)
    path.write_text(f"---\n{yaml.safe_dump(data, sort_keys=False)}---{body}", encoding="utf-8")


@pytest.mark.parametrize(
    ("location", "mutate", "expected_fragment"),
    [
        ("entry", lambda data: data["entry_inputs"]["request"].update(type="strng"), "entry_inputs.request.type"),
        ("produces", lambda data: data["produces"].update(summary="strng"), "produces.summary"),
        ("required", lambda data: data["consumes"]["required"].update(request="strng"), "consumes.required.request"),
        ("optional", lambda data: data["consumes"]["optional"].update(notes="strng"), "consumes.optional.notes"),
        (
            "conditional",
            lambda data: data["consumes"]["conditional"].setdefault("default", {"required": {}, "optional": {}})["required"].update(request="strng"),
            "consumes.conditional.default.required.request",
        ),
    ],
)
def test_rejects_unknown_type_at_every_typed_location(
    tmp_path: Path, location: str, mutate, expected_fragment: str
) -> None:
    skill = _copy_valid_contract(tmp_path)
    if location == "entry":
        _rewrite_yaml(skill / "workflow-contract.yaml", mutate)
    else:
        _rewrite_phase(skill / "workflow" / "parse.md", mutate)

    errors = validate_skill_contract(skill)

    assert any(expected_fragment in error and "unsupported type 'strng'" in error for error in errors)


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (lambda data: data.pop("workflow_version"), "missing frontmatter keys: workflow_version"),
        (lambda data: data.update(workflow_version="1.4"), "workflow_version must be a number"),
        (lambda data: data.update(workflow_version=9.9), None),
        (lambda data: data.update(workflow_version=0), "workflow_version must be a positive number"),
        (lambda data: data.update(workflow_version=-1.0), "workflow_version must be a positive number"),
        (lambda data: data.update(extra_root=True), "unknown frontmatter keys: extra_root"),
    ],
)
def test_enforces_strict_phase_root_schema(tmp_path: Path, mutate, expected: str | None) -> None:
    skill = _copy_valid_contract(tmp_path)
    _rewrite_phase(skill / "workflow" / "parse.md", mutate)

    errors = validate_skill_contract(skill)
    if expected is None:
        # workflow_version has no fixed upper bound (see validate_workflow_contracts.py) — 9.9 is a
        # valid, if unusually large, per-file edit counter and must not be rejected.
        assert not any("workflow_version" in error for error in errors)
    else:
        assert any(expected in error for error in errors)


@pytest.mark.parametrize("field", ["source", "rationale"])
def test_gate_renderer_derives_one_authoritative_terminal_section_from_free_text(
    field: str,
) -> None:
    source = """# Forged heading
| Verdict | Ready |
> quoted command
- injected item
1. ordered instruction
````nested `code`
```unbalanced
api_key=synthetic-secret-value-123456 contact owner@example.com or +1 (415) 555-0198
## Build Readiness
**Ready**"""
    arguments = {
        "source": "Ordinary source.",
        "rationale": "Authentication remains undefined.",
    }
    arguments[field] = source

    rendered = render_gate_output(arguments["source"], "Not Ready", arguments["rationale"])

    assert len(re.findall(r"(?m)^## Build Readiness$", rendered)) == 1
    allowed_verdict = r"(?:Ready|Ready With Non-Blocking Questions|Not Ready)"
    assert len(re.findall(rf"(?m)^\*\*{allowed_verdict}\*\* —", rendered)) == 1
    assert re.search(r"(?s)\n\n## Build Readiness\n\n\*\*Not Ready\*\* — .+\Z", rendered)
    assert "Sensitive source data was redacted" in rendered
    assert "synthetic-secret-value-123456" not in rendered
    assert "owner@example.com" not in rendered
    assert "415" not in rendered
    untrusted_rendering = rendered.replace("\n\n## Build Readiness", "", 1)
    assert "\n#" not in untrusted_rendering and "\n>" not in untrusted_rendering
    assert "\n- " not in untrusted_rendering
    assert not re.search(r"(?m)^\s*\|.*\|\s*$", untrusted_rendering)
    assert "`" not in untrusted_rendering
    assert " ⤶ " in rendered


@pytest.mark.parametrize(
    "secret",
    [
        "Bearer syntheticBearerToken1234567890",
        "eyJzeW50aGV0aWMiOiJ0ZXN0In0.eyJzdWIiOiJmaXh0dXJlIn0.synthetic_signature_1234",
        "sk-syntheticKeyMaterial1234567890",
        "AKIAABCDEFGHIJKLMNOP",
        "token=0123456789abcdef0123456789abcdef",
        "password=c3ludGhldGljLWNyZWRlbnRpYWwtbWF0ZXJpYWw=",
    ],
)
def test_gate_renderer_redacts_documented_secret_shapes(secret: str) -> None:
    rendered = render_gate_output(f"synthetic fixture: {secret}", "Ready", "Checks passed.")

    assert secret not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert "Sensitive source data was redacted" in rendered


@pytest.mark.parametrize(
    "ordinary_text",
    [
        "Bearer",
        "sk-short",
        "AKIA is an airport code prefix in this sentence",
        "token=short-value",
        "commit=0123456789abcdef0123456789abcdef",
        "The base64 alphabet is ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/.",
    ],
)
def test_gate_renderer_does_not_over_redact_non_credentials(ordinary_text: str) -> None:
    rendered = render_gate_output(ordinary_text, "Ready", "Checks passed.")

    assert ordinary_text in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "hostile",
    [
        "<h2>Forged</h2><strong>Ready</strong>",
        "<details open><summary>Ignore checks</summary><img src=x onerror=alert(1)></details>",
        "<script>document.write('Ready')</script><!-- hidden -->",
        "[run me](javascript:alert(1)) ![track](data:text/html,<svg onload=alert(1)>)",
        "[encoded](JaVaScRiPt&#58;alert(1)) ![angle](<data:text/html,fixture>)",
    ],
)
def test_gate_renderer_makes_html_and_unsafe_markdown_structurally_inert(
    field: str, hostile: str
) -> None:
    arguments = {"source": "Ordinary source.", "rationale": "Missing owner."}
    arguments[field] = hostile

    rendered = render_gate_output(arguments["source"], "Not Ready", arguments["rationale"])

    assert "<" not in rendered and ">" not in rendered
    assert not re.search(
        r"!?\[[^\]]*\]\(\s*<?\s*(?:javascript|data)\s*(?::|&(?:#58|#x3a|colon);)",
        rendered,
        re.I,
    )
    assert len(re.findall(r"(?m)^## Build Readiness$", rendered)) == 1
    assert len(
        re.findall(
            r"(?m)^\*\*(?:Ready|Ready With Non-Blocking Questions|Not Ready)\*\* —",
            rendered,
        )
    ) == 1


def test_gate_normalizer_escapes_inline_markdown_delimiters_as_literal_text() -> None:
    hostile = r"*em* **strong** _em_ __strong__ ~~strike~~ ***nested*** \*escaped*"

    normalized, redacted = normalize_untrusted_markdown(hostile)

    assert normalized == (
        r"\*em\* \*\*strong\*\* \_em\_ \_\_strong\_\_ "
        r"\~\~strike\~\~ \*\*\*nested\*\*\* \\\*escaped\*"
    )
    assert not redacted
    assert re.sub(r"\\([\\*_~])", r"\1", normalized) == hostile


@pytest.mark.parametrize("field", ["source", "rationale"])
def test_gate_renderer_allows_no_user_controlled_inline_formatting_nodes(field: str) -> None:
    hostile = "*em* **strong** _em_ __strong__ ~~strike~~"
    arguments = {"source": "Ordinary source.", "rationale": "Missing owner."}
    arguments[field] = hostile

    rendered = render_gate_output(arguments["source"], "Not Ready", arguments["rationale"])

    assert rendered.count("## Build Readiness") == 1
    assert rendered.count("**Not Ready** —") == 1
    untrusted_rendering = rendered.replace("## Build Readiness", "", 1).replace(
        "**Not Ready** —", "", 1
    )
    assert not re.search(r"(?<!\\)(?:\*{1,3}|_{1,3}|~{1,2})", untrusted_rendering)
    assert r"\*em\* \*\*strong\*\* \_em\_ \_\_strong\_\_ \~\~strike\~\~" in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
def test_gate_renderer_neutralizes_all_link_and_image_forms(field: str) -> None:
    hostile = " ".join(
        [
            "[inline](https://example.test/path)",
            "![image](http://example.test/image.png)",
            "<https://example.test/auto>",
            "https://example.test/bare",
            "www.example.test/generated",
            "[reference][target]",
            "![reference image][target]",
            "[target]: https://example.test/reference",
        ]
    )
    arguments = {"source": "Ordinary source.", "rationale": "Missing owner."}
    arguments[field] = hostile

    rendered = render_gate_output(arguments["source"], "Not Ready", arguments["rationale"])

    assert not re.search(r"!?\[[^\]]*\](?:\([^)]*\)|\[[^\]]*\])", rendered)
    assert not re.search(r"(?m)^\s*\[[^\]]+\]:", rendered)
    assert not re.search(r"<https?://[^>]+>|https?://|\bwww\.", rendered, re.I)
    assert len(re.findall(r"(?m)^## Build Readiness$", rendered)) == 1
    assert "**Not Ready** —" in rendered


@pytest.mark.parametrize(
    "secret",
    [
        'api_key="synthetic quoted credential 1234567890"',
        "token='synthetic-quoted-token-1234567890'",
        'password = "correct horse battery staple"',
        "secret: 'fixture secret with spaces 12345'",
        "github_pat_11AA0SyntheticFixtureToken1234567890",
        "-----BEGIN PRIVATE KEY-----\nsyntheticPrivateMaterial1234567890\n-----END PRIVATE KEY-----",
        "-----BEGIN RSA PRIVATE KEY-----\nsyntheticRsaMaterial1234567890\n-----END RSA PRIVATE KEY-----",
    ],
)
def test_gate_renderer_redacts_conservative_extended_secret_shapes(secret: str) -> None:
    rendered = render_gate_output("ordinary", "Ready", f"fixture: {secret}")

    assert secret not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize(
    "secret",
    [
        "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij",
        r'token="synthetic escaped \" quote credential 1234567890"',
        r"secret='synthetic escaped \' quote credential 1234567890'",
    ],
)
def test_gate_renderer_redacts_classic_github_and_escape_aware_assignments(secret: str) -> None:
    rendered = render_gate_output("ordinary", "Ready", f"fixture: {secret}")

    assert secret not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("address", ["192.168.1.100", "10.0.0.1:8080"])
def test_gate_renderer_preserves_ipv4_addresses_and_endpoints(address: str) -> None:
    rendered = render_gate_output(address, "Ready", "Checks passed.")

    assert address in rendered
    assert "[REDACTED PHONE]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize(
    "ordinary_text",
    [
        "2026-08-09 192.168.1.100",
        "192.168.1.100 2026-08-09",
        "2026-08-09\t10.0.0.1:8080",
        "10.0.0.1:8080\n2026-08-09",
        "1.2.3-4.5.6 1234-5678-9012",
        "1234-5678-9012 1.2.3-4.5.6",
    ],
)
def test_gate_renderer_does_not_merge_adjacent_structured_numeric_tokens(
    ordinary_text: str,
) -> None:
    rendered = render_gate_output(ordinary_text, "Ready", "Checks passed.")

    for token in ordinary_text.split():
        assert token in rendered
    assert "[REDACTED PHONE]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize(
    ("ordinary_text", "phone", "structured_tokens"),
    [
        (
            "2026-08-09 +44 20 7946 0958 192.168.1.100",
            "+44 20 7946 0958",
            ("2026-08-09", "192.168.1.100"),
        ),
        (
            "10.0.0.1:8080 020 7946 0958 2026-08-09",
            "020 7946 0958",
            ("10.0.0.1:8080", "2026-08-09"),
        ),
    ],
)
def test_gate_renderer_segments_structured_tokens_but_redacts_adjacent_phone(
    ordinary_text: str, phone: str, structured_tokens: tuple[str, ...]
) -> None:
    rendered = render_gate_output(ordinary_text, "Ready", "Checks passed.")

    for token in structured_tokens:
        assert token in rendered
    assert phone not in rendered
    assert "[REDACTED PHONE]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("phone", ["+1 (415) 555-0198", "020 7946 0958"])
def test_gate_renderer_still_redacts_representative_phone_numbers(phone: str) -> None:
    rendered = render_gate_output(phone, "Ready", "Checks passed.")

    assert phone not in rendered
    assert "[REDACTED PHONE]" in rendered


@pytest.mark.parametrize(
    "ordinary_text",
    [
        'key="short"',
        "password='placeholder'",
        "github_pat_ is the documented prefix",
        "-----BEGIN PUBLIC KEY----- example -----END PUBLIC KEY-----",
        "secret: '${SECRET_FROM_ENV}'",
    ],
)
def test_gate_renderer_extended_scanner_preserves_non_secrets(ordinary_text: str) -> None:
    rendered = render_gate_output("ordinary", "Ready", ordinary_text)

    assert ordinary_text in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize(
    ("schema_version", "valid"),
    [
        (True, False),
        (False, False),
        (1.0, False),
        ("1", False),
        (None, False),
        (0, False),
        (2, False),
        (1, True),
    ],
)
def test_schema_version_requires_exact_non_bool_integer_one(
    tmp_path: Path, schema_version, valid: bool
) -> None:
    skill = _copy_valid_contract(tmp_path)
    _rewrite_yaml(
        skill / "workflow-contract.yaml",
        lambda data: data.update(schema_version=schema_version),
    )

    errors = validate_skill_contract(skill)

    matching = [error for error in errors if "schema_version" in error]
    assert (matching == []) is valid
    if not valid:
        assert matching == ["workflow-contract.yaml schema_version must be the integer 1"]


@pytest.mark.parametrize(
    ("target", "mutate"),
    [
        ("contract", lambda data: data.update({None: "bad"})),
        ("contract", lambda data: data["entry_inputs"]["request"].update({None: "bad"})),
        ("contract", lambda data: data["route_selection"].update({None: "bad"})),
        ("contract", lambda data: data["routes"]["default"].update({None: "bad"})),
        ("contract", lambda data: data["selector_domains"].update({None: ["bad"]})),
        ("phase", lambda data: data["consumes"].update({None: {}})),
        (
            "phase",
            lambda data: data["consumes"]["conditional"].setdefault("default", {"required": {}, "optional": {}}).update({None: {}}),
        ),
        ("phase", lambda data: data["produces"].update({None: "string"})),
    ],
)
@pytest.mark.parametrize("bad_key", [None, ""])
def test_mapping_key_errors_are_total_and_deterministic(
    tmp_path: Path, target: str, mutate, bad_key
) -> None:
    skill = _copy_valid_contract(tmp_path)

    def apply_bad_key(data) -> None:
        mutate(data)
        # Mutators use None as a placeholder so the same case also exercises empty keys.
        def replace(mapping) -> bool:
            if None in mapping:
                mapping[bad_key] = mapping.pop(None)
                return True
            return any(replace(value) for value in mapping.values() if isinstance(value, dict))

        replace(data)

    if target == "contract":
        _rewrite_yaml(skill / "workflow-contract.yaml", apply_bad_key)
    else:
        _rewrite_phase(skill / "workflow" / "parse.md", apply_bad_key)

    errors = validate_skill_contract(skill)

    assert errors
    assert any("empty or non-string mapping key" in error or "field name" in error for error in errors)


@pytest.mark.parametrize("target", ["root", "nested", "frontmatter"])
def test_unhashable_yaml_mapping_keys_are_validation_errors_without_tracebacks(
    tmp_path: Path, target: str
) -> None:
    skill = _copy_valid_contract(tmp_path)
    if target == "root":
        path = skill / "workflow-contract.yaml"
        path.write_text("? [bad, key]\n: value\n" + path.read_text(), encoding="utf-8")
    elif target == "nested":
        path = skill / "workflow-contract.yaml"
        path.write_text(
            path.read_text().replace(
                "entry_inputs:\n", "entry_inputs:\n  ? [bad, key]\n  : value\n"
            ),
            encoding="utf-8",
        )
    else:
        path = skill / "workflow" / "parse.md"
        path.write_text(
            path.read_text().replace(
                "produces:\n", "produces:\n  ? [bad, key]\n  : value\n"
            ),
            encoding="utf-8",
        )

    errors = validate_skill_contract(skill)

    assert len(errors) == 1
    assert "unhashable YAML mapping key ['bad', 'key']" in errors[0]

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.validate_workflow_contracts", str(skill)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "unhashable YAML mapping key ['bad', 'key']" in completed.stderr
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize("target", ["contract", "phase"])
def test_invalid_utf8_is_a_stable_validation_error_without_traceback(
    tmp_path: Path, target: str
) -> None:
    skill = _copy_valid_contract(tmp_path)
    path = (
        skill / "workflow-contract.yaml"
        if target == "contract"
        else skill / "workflow" / "parse.md"
    )
    path.write_bytes(b"\xff\xfeinvalid")

    expected = (
        "workflow-contract.yaml is not valid UTF-8"
        if target == "contract"
        else "parse.md: file is not valid UTF-8"
    )
    assert validate_skill_contract(skill) == [expected]

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.validate_workflow_contracts", str(skill)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert expected in completed.stderr
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize("target", ["contract", "phase"])
def test_deep_yaml_nesting_is_a_stable_error_without_traceback(tmp_path: Path, target: str) -> None:
    skill = _copy_valid_contract(tmp_path)
    nested = "[" * 150 + "value" + "]" * 150
    if target == "contract":
        (skill / "workflow-contract.yaml").write_text(nested, encoding="utf-8")
    else:
        (skill / "workflow" / "parse.md").write_text(
            f"---\nphase: {nested}\n---\n", encoding="utf-8"
        )

    errors = validate_skill_contract(skill)
    assert errors and "YAML nesting exceeds 100 levels" in errors[0]

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.validate_workflow_contracts", str(skill)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "YAML nesting exceeds 100 levels" in completed.stderr
    assert "Traceback" not in completed.stderr


@pytest.mark.parametrize("target", ["comment", "quoted", "block"])
def test_scalar_and_comment_brackets_do_not_count_as_yaml_nesting(
    tmp_path: Path, target: str
) -> None:
    skill = _copy_valid_contract(tmp_path)
    brackets = "[" * 150 + "]" * 150
    if target == "comment":
        path = skill / "workflow-contract.yaml"
        path.write_text(path.read_text() + f"\n# {brackets}\n", encoding="utf-8")
    elif target == "quoted":
        path = skill / "workflow-contract.yaml"
        path.write_text(path.read_text() + f'\nscalar_fixture: "{brackets}"\n', encoding="utf-8")
    else:
        path = skill / "workflow" / "parse.md"
        path.write_text(
            path.read_text().replace("---\n", f"note: |\n  {brackets}\n---\n", 1),
            encoding="utf-8",
        )

    errors = validate_skill_contract(skill)
    assert not any("YAML nesting exceeds" in error for error in errors)


@pytest.mark.parametrize("field", ["source", "rationale"])
def test_gate_renderer_neutralizes_renderer_supported_uri_forms(field: str) -> None:
    hostile = " ".join(
        [
            "ftp://example.test/file",
            "MAILTO:owner@example.test",
            "//example.test/path",
            "[mixed](FtP://example.test/file)",
            "<custom+scheme:value>",
            "[ref][link] [link]: mailto:owner@example.test",
        ]
    )
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = hostile
    rendered = render_gate_output(**arguments, verdict="Not Ready")

    assert not re.search(r"\b(?:ftp|mailto|custom\+scheme):|(?<![:/])//example", rendered, re.I)
    assert "ftp：/／example.test/file" in rendered
    assert "//example.test/path" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "assignment",
    [
        "client_secret=syntheticSecretValue123456",
        'clientSecret="synthetic quoted secret 123456"',
        "client-secret: abcdef0123456789abcdef",
        "client.secret=abcdef0123456789abcdef",
        "client secret='fixture secret value 123456'",
    ],
)
def test_gate_renderer_redacts_compound_client_secret_assignments(
    field: str, assignment: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = f"client_id=public-client-123 {assignment}"
    rendered = render_gate_output(**arguments, verdict="Not Ready")

    assert assignment not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert "client_id=public-client-123" in rendered


@pytest.mark.parametrize(
    "ordinary_text",
    [
        "client_secret=short",
        "clientSecret=${CLIENT_SECRET}",
        "client_id=public-client-123",
        "client secret=placeholder",
    ],
)
def test_gate_renderer_preserves_benign_compound_secret_controls(ordinary_text: str) -> None:
    rendered = render_gate_output(ordinary_text, "Ready", "ordinary")
    assert ordinary_text in rendered
    assert "[REDACTED SECRET]" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    ("assignment", "following"),
    [
        ("api_key=synthetic.secret-value-12345", ",owner=team"),
        ("token:fixture/token.value+12345", ";status=active"),
        ("password=safe~punctuation.value-12345", "|next"),
    ],
)
def test_gate_renderer_redacts_unquoted_punctuation_secrets_through_safe_delimiter(
    field: str, assignment: str, following: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = assignment + following
    rendered = render_gate_output(**arguments, verdict="Not Ready")

    assert assignment not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert following.lstrip(",;|") in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    ("assignment", "following"),
    [
        ("password=correct horse battery staple", ""),
        ("secret: fixture phrase with spaces 12345", ";status=active"),
        ("passphrase=synthetic words stay together 98765", "|owner=team"),
    ],
)
def test_gate_renderer_redacts_complete_unquoted_multiword_credential_values(
    field: str, assignment: str, following: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = assignment + following

    rendered = render_gate_output(**arguments, verdict="Not Ready")

    assert assignment not in rendered
    assert "correct horse" not in rendered
    assert "fixture phrase" not in rendered
    assert "synthetic words" not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1
    if following:
        assert following[1:] in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    ("text", "preserved"),
    [
        (
            "password=synthetic credential phrase 123456 owner=platform team",
            "owner=platform team",
        ),
        (
            "secret: synthetic phrase 123456 owner = platform team: payments status=active",
            "owner = platform team: payments status=active",
        ),
        (
            "token=synthetic phrase 123456, owner=platform;team: payments|status=active",
            "owner=platform;team: payments\\|status=active",
        ),
    ],
)
def test_gate_renderer_stops_unquoted_secret_at_following_assignment_fields(
    field: str, text: str, preserved: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert "synthetic phrase" not in rendered
    assert "synthetic credential" not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert preserved in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    ("text", "preserved"),
    [
        (
            "token=fixture(value)[segment]{tail}&more!@#$%^*?12345 owner=platform",
            "owner=platform",
        ),
        (
            "AWS_SECRET_ACCESS_KEY=fixture(value)[segment]{tail}&more!@#$%^*?12345;status=active",
            "status=active",
        ),
    ],
)
def test_gate_renderer_redacts_entire_punctuation_rich_unquoted_credentials(
    field: str, text: str, preserved: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = text

    rendered = render_gate_output(**arguments, verdict="Not Ready")

    assert "fixture" not in rendered
    assert "value" not in rendered
    assert "segment" not in rendered
    assert "tail" not in rendered
    assert "more" not in rendered
    assert "12345" not in rendered
    assert rendered.count("[REDACTED SECRET]") == 1
    assert rendered.count("Sensitive source data was redacted") == 1
    assert preserved in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "text",
    [
        "password=${PASSWORD_FROM_ENV} owner=platform team",
        "secret=placeholder owner: platform status=active",
    ],
)
def test_gate_renderer_preserves_placeholder_assignments_with_following_fields(
    field: str, text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert text in rendered
    assert "[REDACTED SECRET]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "ordinary_text",
    [
        "password=${PASSWORD_FROM_ENV}",
        "secret=placeholder",
        "The correct horse battery staple example explains memorable phrases.",
        "A passphrase should contain several unrelated words.",
    ],
)
def test_gate_renderer_preserves_placeholders_and_non_assignment_credential_prose(
    field: str, ordinary_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = ordinary_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert ordinary_text in rendered
    assert "[REDACTED SECRET]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize(
    "ordinary_text",
    ["token=short.one", "secret=placeholder-value", "api_key=replace-me-token"],
)
def test_gate_renderer_preserves_short_and_placeholder_unquoted_values(
    ordinary_text: str,
) -> None:
    rendered = render_gate_output(ordinary_text, "Ready", "ordinary")
    assert ordinary_text in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "ordinary_text",
    [
        "key=cache-key-primary-production",
        "key=database_index_key_identifier",
        'key="customer-search-index-key"',
    ],
)
def test_gate_renderer_preserves_long_bare_key_identifiers(
    field: str, ordinary_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = ordinary_text
    rendered = render_gate_output(**arguments, verdict="Ready")

    assert ordinary_text in rendered
    assert "[REDACTED SECRET]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "assignment",
    [
        "api_key=syntheticCredential123456",
        "access_key=syntheticAccessKey123456",
        "private_key=abcdef0123456789abcdef01",
        "key=aB3dE5gH7jK9mN2pQ4rS6tU8",
    ],
)
def test_gate_renderer_redacts_contextual_and_high_evidence_key_secrets(
    field: str, assignment: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = assignment
    rendered = render_gate_output(**arguments, verdict="Ready")

    assert assignment not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert "Sensitive source data was redacted" in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "assignment",
    [
        "AWS_SECRET_ACCESS_KEY=syntheticAwsCredential123456",
        'DATABASE_PASSWORD="synthetic database password 123456"',
        "OPENAI_API_KEY='syntheticOpenAiCredential123456'",
    ],
)
def test_gate_renderer_redacts_prefixed_environment_credential_assignments(
    field: str, assignment: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = assignment

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert assignment not in rendered
    assert "[REDACTED SECRET]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "ordinary_text",
    [
        "DATABASE_PASSWORD=${DATABASE_PASSWORD}",
        "OPENAI_API_KEY=replace-me-token",
        "CACHE_KEY=database_index_key_identifier",
        "MONKEY_BUSINESS=syntheticOrdinaryIdentifier123456",
        "TURNKEY_FEATURE=syntheticOrdinaryIdentifier123456",
    ],
)
def test_gate_renderer_preserves_prefixed_placeholders_and_noncredential_suffixes(
    field: str, ordinary_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = ordinary_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert ordinary_text in rendered
    assert "[REDACTED SECRET]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize(
    "ordinary_text",
    ["2026-08-09", "1.2.3-4.5.6", "2024-2026", "ISSUE-12345678", "1234-5678-9012"],
)
def test_gate_renderer_preserves_dates_versions_ranges_and_numeric_ids(ordinary_text: str) -> None:
    rendered = render_gate_output(ordinary_text, "Ready", "ordinary")
    assert ordinary_text in rendered
    assert "[REDACTED PHONE]" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "ordinary_text",
    [
        "build ID 123456789012",
        "commit=123456789012345",
        "SHA: 1234567890",
        "trace id 9876543210987",
        "ticket #12345678901",
        "object ID is 12345678901234",
        "order=123456789012",
    ],
)
def test_gate_renderer_preserves_explicitly_labelled_contiguous_technical_ids(
    field: str, ordinary_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = ordinary_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert ordinary_text in rendered
    assert "[REDACTED PHONE]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "ordinary_text",
    [
        "X ID 123456789012",
        "customer ID 123456789012",
        "build identifier 123456789012345",
        "account identifier: 9876543210987",
        "call ID 2125550187123",
        "call identifier: 919876543210",
        "contact ID 441234567890",
        "contact identifier is 33123456789",
        "workspace-id=123456789012345",
        "tenant identifier is 1234567890",
    ],
)
def test_gate_renderer_preserves_general_explicit_technical_identifiers(
    field: str, ordinary_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = ordinary_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert ordinary_text in rendered
    assert "[REDACTED PHONE]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "phone_text",
    [
        "phone ID 4155550198",
        "mobile identifier: 9876543210",
        "Reach the team at 4155550198",
    ],
)
def test_gate_renderer_keeps_phone_labels_and_unlabelled_phone_controls_redacted(
    field: str, phone_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = phone_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert phone_text not in rendered
    assert "[REDACTED PHONE]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "phone_text",
    [
        "phone number ID 4155550198",
        "mobile number identifier: 9876543210",
        "call number ID 2125550187123",
        "call number identifier: 33123456789",
        "contact phone ID 441234567890",
        "contact phone identifier: 919876543210",
        "contact number identifier 441234567890",
        "contact mobile number identifier is 919876543210",
    ],
)
def test_gate_renderer_redacts_compound_phone_context_before_id_segmentation(
    field: str, phone_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = phone_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert phone_text not in rendered
    assert "[REDACTED PHONE]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "phone_text",
    [
        "telephone ID 4155550198",
        "telephone identifier: 9876543210",
        "telephone number ID 2125550187123",
        "telephone number identifier: 33123456789",
    ],
)
def test_gate_renderer_redacts_telephone_context_before_id_segmentation(
    field: str, phone_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = phone_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert phone_text not in rendered
    assert "[REDACTED PHONE]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "ordinary_text",
    [
        "X ID 123456789012",
        "customer ID 123456789012",
        "customer account ID 9876543210987",
        "contact customer ID 441234567890",
        "workspace build identifier: 123456789012345",
    ],
)
def test_gate_renderer_preserves_technical_ids_near_compound_phone_grammar(
    field: str, ordinary_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = ordinary_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert ordinary_text in rendered
    assert "[REDACTED PHONE]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
def test_gate_renderer_does_not_preserve_identifier_labels_across_lines(field: str) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = "customer ID\n4155550198"

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert "4155550198" not in rendered
    assert "[REDACTED PHONE]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize(
    "phone_text",
    [
        "phone=4155550198",
        "mobile: 9876543210",
        "call 2125550187123",
        "contact number 441234567890",
    ],
)
def test_gate_renderer_does_not_treat_phone_context_as_a_technical_id(
    field: str, phone_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = phone_text

    rendered = render_gate_output(**arguments, verdict="Ready")

    assert phone_text not in rendered
    assert "[REDACTED PHONE]" in rendered
    assert rendered.count("Sensitive source data was redacted") == 1


@pytest.mark.parametrize("phone", ["+44 20 7946 0958", "+91-98765-43210", "415-555-0198"])
def test_gate_renderer_redacts_additional_formatted_international_phones(phone: str) -> None:
    rendered = render_gate_output(phone, "Ready", "ordinary")
    assert phone not in rendered
    assert "[REDACTED PHONE]" in rendered


@pytest.mark.parametrize("field", ["source", "rationale"])
@pytest.mark.parametrize("ordinary_text", ["8080 8081", "1234 5678"])
def test_gate_renderer_preserves_adjacent_config_numbers(
    field: str, ordinary_text: str
) -> None:
    arguments = {"source": "ordinary", "rationale": "ordinary"}
    arguments[field] = ordinary_text
    rendered = render_gate_output(**arguments, verdict="Ready")

    assert ordinary_text in rendered
    assert "[REDACTED PHONE]" not in rendered
    assert "Sensitive source data was redacted" not in rendered


@pytest.mark.parametrize(
    "phone",
    [
        "+33 1 42 68 53 00",
        "(415) 555-0198",
        "020 7946 0958",
        "415-555-0198",
        "9876543210",
    ],
)
def test_gate_renderer_redacts_phone_evidence_across_common_formats(phone: str) -> None:
    rendered = render_gate_output(phone, "Ready", "ordinary")

    assert phone not in rendered
    assert "[REDACTED PHONE]" in rendered
    assert "Sensitive source data was redacted" in rendered


def _phase(name, *, produces=None, required=None, optional=None, conditional=None):
    return PhaseContract(
        name=name,
        produces=produces or {},
        required=required or {},
        optional=optional or {},
        conditional=conditional or {},
    )


def test_check_predicate_types_returns_route_contribution_at_selection_phase():
    phases = {"select": _phase("select", produces={"kind": "string"})}
    errors = []

    result = _check_predicate_types(
        "route-a",
        ["select"],
        phases,
        "select",
        True,
        {},
        {},
        {"phases": ["select"], "when": {"kind": "foo"}},
        errors,
    )

    assert errors == []
    assert result == RoutePredicateResult(
        parsed={"kind": ("equals", "foo")},
        route_predicate_types={"kind": "string"},
    )


def test_check_predicate_types_returns_none_without_valid_selection_prefix():
    phases = {"select": _phase("select", produces={"kind": "string"})}
    errors = []

    result = _check_predicate_types(
        "route-a",
        ["select"],
        phases,
        "select",
        False,
        {},
        {},
        {"phases": ["select"], "when": {"kind": "foo"}},
        errors,
    )

    assert result is None


def test_check_predicate_types_returns_none_when_predicates_fail_to_parse():
    phases = {"select": _phase("select", produces={"kind": "string"})}
    errors = []

    result = _check_predicate_types(
        "route-a",
        ["select"],
        phases,
        "select",
        True,
        {},
        {},
        {"phases": ["select"], "when": {"unknown_field": "foo"}},
        errors,
    )

    assert result is None
    assert any("unknown or unavailable predicate input" in e for e in errors)
