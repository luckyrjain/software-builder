"""Tests for KubeSense SPL log fetcher."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from kubesense_logs import (  # noqa: E402
    KubesenseError,
    build_evidence_fragment,
    build_spl_query,
    choose_cluster,
    extract_message,
    find_workload_locations,
    redact_secrets,
    spl_rows_to_logs,
)

HIERARCHY = [
    {
        "name": "acme-neo-prod-eks-cluster",
        "type": "cluster",
        "childs": [
            {
                "name": "domain",
                "type": "namespace",
                "childs": [
                    {"name": "autodebit-service", "type": "workload", "childs": []},
                ],
            }
        ],
    },
    {
        "name": "acme-neo-uat-eks-cluster",
        "type": "cluster",
        "childs": [
            {
                "name": "domain",
                "type": "namespace",
                "childs": [
                    {"name": "autodebit-service", "type": "workload", "childs": []},
                ],
            }
        ],
    },
]


def test_redact_secrets_masks_authorization():
    raw = '{"requestHeaders":{"Authorization":"Basic SECRETTOKEN","x-merchantid":"acme"}}'
    redacted = redact_secrets(raw)
    assert "SECRETTOKEN" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_secrets_masks_token_after_redacted_marker():
    raw = "requestHeaders={Authorization=[REDACTED] MDEzMUEyRDBDNkY0NEQ0QjFGNDIwODk2NkY1MTlF, x-merchantid=acme}"
    redacted = redact_secrets(raw)
    assert "MDEzMUEy" not in redacted
    assert "Authorization=[REDACTED]" in redacted


def test_redact_secrets_masks_api_key_key_value_form():
    redacted = redact_secrets("api_key=sk_live_abcdef1234567890")
    assert "sk_live_abcdef1234567890" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_secrets_masks_x_api_key_case_insensitive():
    redacted = redact_secrets("X-API-KEY=sk_live_abcdef1234567890")
    assert "sk_live_abcdef1234567890" not in redacted


def test_redact_secrets_masks_api_key_json_form():
    redacted = redact_secrets('{"api_key": "sk_live_abcdef1234567890"}')
    assert "sk_live_abcdef1234567890" not in redacted
    assert '"api_key": "[REDACTED]"' in redacted


def test_redact_secrets_masks_password_key_value_and_json_form():
    assert "hunter2superSecret" not in redact_secrets("password=hunter2superSecret")
    assert "hunter2superSecret" not in redact_secrets('{"password": "hunter2superSecret"}')
    assert "hunter2superSecret" not in redact_secrets("pwd=hunter2superSecret")


def test_redact_secrets_masks_pem_private_key_block():
    raw = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA1234567890abcdef\n"
        "-----END RSA PRIVATE KEY-----"
    )
    redacted = redact_secrets(raw)
    assert "MIIEpAIBAAKCAQEA1234567890abcdef" not in redacted
    assert "-----BEGIN RSA PRIVATE KEY-----" in redacted
    assert "-----END RSA PRIVATE KEY-----" in redacted


def test_redact_secrets_does_not_false_positive_on_ordinary_identifiers():
    # A variable/field named similarly to a secret but not actually a key=value secret assignment
    # must survive untouched — matches the discipline #54's mysql scan tests apply.
    raw = "passwordResetRequired=true and apiKeyRotationEnabled=false in the feature flags"
    redacted = redact_secrets(raw)
    assert redacted == raw


def test_extract_message_from_json_body():
    body = json.dumps({"level": "ERROR", "message": "payment gateway timeout"})
    assert extract_message(body) == "payment gateway timeout"


def test_extract_message_plain_text_fallback():
    body = "plain log line"
    assert extract_message(body) == "plain log line"


def test_find_workload_locations():
    locations = find_workload_locations(HIERARCHY, "autodebit-service")
    assert len(locations) == 2
    assert all(loc.namespace == "domain" for loc in locations)


def test_choose_cluster_auto_selects_single_prod():
    locations = find_workload_locations(HIERARCHY, "autodebit-service")
    loc = choose_cluster(locations, cluster=None, namespace=None)
    assert loc.cluster == "acme-neo-prod-eks-cluster"


def test_choose_cluster_requires_flag_when_multiple_prod():
    hierarchy = [
        {
            "name": "acme-neo-prod-eks-cluster",
            "type": "cluster",
            "childs": [
                {
                    "name": "domain",
                    "type": "namespace",
                    "childs": [{"name": "svc", "type": "workload", "childs": []}],
                }
            ],
        },
        {
            "name": "acme-gj-prod-ekscluster",
            "type": "cluster",
            "childs": [
                {
                    "name": "domain",
                    "type": "namespace",
                    "childs": [{"name": "svc", "type": "workload", "childs": []}],
                }
            ],
        },
    ]
    locations = find_workload_locations(hierarchy, "svc")
    try:
        choose_cluster(locations, cluster=None, namespace=None)
        raise AssertionError("expected KubesenseError")
    except KubesenseError as exc:
        assert "Multiple clusters" in str(exc)


def test_choose_cluster_explicit():
    locations = find_workload_locations(HIERARCHY, "autodebit-service")
    loc = choose_cluster(locations, cluster="acme-neo-prod-eks-cluster", namespace=None)
    assert loc.cluster == "acme-neo-prod-eks-cluster"


def test_build_spl_query_includes_filters():
    query = build_spl_query("autodebit-service", "ERROR", "domain", 10)
    assert 'workload = "autodebit-service"' in query
    assert 'level = "ERROR"' in query
    assert 'namespace = "domain"' in query
    assert "| limit 10" in query


def test_build_spl_query_escapes_embedded_quotes():
    # A workload value containing `"` must not be able to close the string
    # literal early and inject additional SPL clauses.
    query = build_spl_query('svc" or workload != "x', "ERROR", None, 10)
    assert 'workload = "svc\\" or workload != \\"x"' in query
    # The vulnerable, unescaped form (early-closed literal) must not appear.
    assert 'workload = "svc" or workload != "x"' not in query


def test_build_spl_query_escapes_backslashes():
    query = build_spl_query('svc\\', "ERROR", None, 10)
    assert 'workload = "svc\\\\"' in query


def test_spl_rows_to_logs_maps_columns():
    spl_data = {
        "columns": ["timestamp", "workload", "level", "body", "pod_name", "namespace"],
        "rows": [
            [
                "2026-07-01T09:44:57.001Z",
                "autodebit-service",
                "ERROR",
                json.dumps({"message": "downstream failure"}),
                "autodebit-service-abc",
                "domain",
            ]
        ],
    }
    logs = spl_rows_to_logs(spl_data)
    assert len(logs) == 1
    assert logs[0].timestamp.endswith("Z")
    assert logs[0].message == "downstream failure"
    assert logs[0].pod_name == "autodebit-service-abc"


def test_build_evidence_fragment_maps_error_signal():
    spl_data = {
        "columns": ["timestamp", "workload", "level", "body", "pod_name", "namespace"],
        "rows": [
            [
                "2026-07-01T09:44:57.001Z",
                "autodebit-service",
                "ERROR",
                json.dumps({"message": "timeout"}),
                "pod-a",
                "domain",
            ],
            [
                "2026-07-01T09:44:56.998Z",
                "autodebit-service",
                "ERROR",
                json.dumps({"message": "timeout"}),
                "pod-b",
                "domain",
            ],
        ],
    }
    logs = spl_rows_to_logs(spl_data)
    fragment = build_evidence_fragment(
        logs,
        service="autodebit-service",
        from_time="2026-07-01T09:40:00Z",
        to_time="2026-07-01T09:45:00Z",
        cluster="acme-neo-prod-eks-cluster",
        namespace="domain",
        limit=10,
    )
    signal = fragment["error_signals"][0]
    assert signal["source"] == "kubesense-spl"
    assert signal["sample_messages"] == ["timeout"]
    assert "kubesense-spl:" in fragment["query_references"][0]
