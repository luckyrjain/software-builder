"""The one redaction table incident-rca and prd-architect both redact through.

Both skills used to carry a private regex family. These tests are the cross-check that was
missing: every pattern either family started with is still in the shared table and still matches,
each skill still selects the profile its output contract needs, and a corpus of realistic log
lines and PRD sentences stays untouched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # Registered the way a real import would be: these scripts declare dataclasses, which resolve
    # their string annotations through sys.modules at class-creation time.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def redaction():
    return _load(ROOT / "docs/skill-framework/shared/redaction.py", "shared_redaction_under_test")


@pytest.fixture(scope="module")
def kubesense():
    return _load(ROOT / "incident-rca/scripts/kubesense_logs.py", "kubesense_logs_under_test")


@pytest.fixture(scope="module")
def prd():
    return _load(ROOT / "prd-architect/scripts/prd_safe_output.py", "prd_safe_output_under_test")


def _by_name(patterns) -> dict[str, object]:
    return {entry.name: entry for entry in patterns}


# One sample per pattern the incident-rca family carried before the two families were merged.
LOG_FAMILY_SAMPLES = {
    "authorization_json": '{"Authorization": "Basic QUJDREVGR0g="}',
    "bearer_quoted": '{"header": "Bearer abcdefghijkl"}',
    "authorization_straggler": "Authorization=[REDACTED] LEFTOVERTOKENVALUE",
    "authorization_kv": "Authorization=SECRETTOKENVALUE",
    "basic_credentials": "Basic QUJDREVGR0g=",
    "api_key_json": '{"x-api-key": "sk_live_abcdef1234567890"}',
    "api_key_kv": "X-API-KEY=sk_live_abcdef1234567890",
    "password_json": '{"password": "hunter2superSecret"}',
    "password_kv": "pwd=hunter2superSecret",
    "pem_block": "-----BEGIN CERTIFICATE-----\nMIIabc\n-----END CERTIFICATE-----",
}

# One sample per pattern the prd-architect family carried.
DOCUMENT_FAMILY_SAMPLES = {
    "pem_private_key": "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----",
    "github_pat": "github_pat_" + "a" * 22,
    "github_ghp": "ghp_" + "b" * 36,
    "bearer_token": "Bearer abcdefghijkl",
    "jwt": "a" * 16 + "." + "b" * 16 + "." + "c" * 16,
    "openai_sk": "sk-" + "d" * 20,
    "aws_akia": "AKIA" + "E" * 16,
    "client_secret_kv": "client_secret=0123456789abcdef",
    "quoted_secret_assignment": 'api_key: "abcdefghijklmnop"',
    "unquoted_secret_assignment": "password=hunter2superSecret",
    "email": "person@example.com",
}

# Realistic Kubernetes/incident log lines. None of these carries a credential, and each one is
# something an incident responder reads for diagnosis -- including the service-account identity,
# which is email-shaped by design.
LOG_FALSE_POSITIVES = (
    "2026-03-04T10:15:22Z INFO pod payments-api-7d9f8c6b4-x2k9m restarted in namespace payments",
    "serviceaccount deployer@payments-prod.iam.gserviceaccount.com denied get on pods",
    "pulled image registry.example.com/payments/api@sha256:"
    "9f1c2d3e4a5b60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f9",
    "GET /v2/accounts/1234567890 200 in 431ms trace_id=0af7651916cd43dd8448eb211c80319c",
    "node ip-10-0-14-233.eu-west-1.compute.internal went NotReady for 45s",
    "configmap payments-api-config updated: featureFlags.apiKeyRotationEnabled=false",
    "passwordResetRequired=true and apiKeyRotationEnabled=false in the feature flags",
    "helm upgrade payments-api to chart version 4.12.0-rc.3 succeeded",
    "OOMKilled container=api memory limit 512Mi request 256Mi restartCount=7",
    "connected to payments-api.cluster-abc.eu-west-1.rds.amazonaws.com:5432 in 12ms",
    "p99 latency 1234.5678ms across 3 replicas, error budget 99.95% intact",
    "reflector.go:138 failed to watch *v1.Pod: context deadline exceeded",
)

# Realistic PRD sentences: they name credential fields without carrying one, and they carry the
# structured numerics (dates, versions, order ids) the phone heuristic must leave alone.
DOCUMENT_FALSE_POSITIVES = (
    "The service must rotate its API key every 90 days.",
    "The password policy requires at least 12 characters and one symbol.",
    "Release 4.12.0 ships on 2026-03-04 behind a feature flag.",
    "Order ID 1234567890 must appear on the emailed receipt.",
    "The gateway rate limit is 1000 requests per second per tenant.",
    "Client secret rotation moves to a quarterly cadence in phase two.",
    "token: TBD",
    "api_key = ${API_KEY}",
    "password: changeme",
    "Trace ID 1234567890123 links the request to its span in the tracing UI.",
    "The cache key is derived from tenant, locale, and currency.",
    "Latency budget is 250 ms at p99, measured over a 5 minute window.",
)


def _names(patterns) -> list[str]:
    return [entry.name for entry in patterns]


def test_both_skills_redact_through_the_shared_table(redaction, kubesense, prd) -> None:
    # Each fixture executes its module separately, so this compares the selected profile by
    # content rather than by identity.
    assert _names(kubesense.REDACTION_PROFILE) == _names(redaction.LOG_PATTERNS)
    assert _names(prd.REDACTION_PROFILE) == _names(redaction.DOCUMENT_PATTERNS)


def test_pattern_names_are_unique_and_categorised(redaction) -> None:
    names = [entry.name for entry in redaction.REDACTION_PATTERNS]
    assert len(names) == len(set(names))
    assert {entry.category for entry in redaction.REDACTION_PATTERNS} <= set(redaction.CATEGORIES)
    assert set(names) == {
        entry.name for entry in redaction.LOG_PATTERNS + redaction.DOCUMENT_PATTERNS
    }


@pytest.mark.parametrize(("name", "sample"), sorted(LOG_FAMILY_SAMPLES.items()))
def test_every_log_family_pattern_survived_the_merge(redaction, name, sample) -> None:
    entry = _by_name(redaction.LOG_PATTERNS)[name]
    assert entry.pattern.search(sample), f"{name} no longer matches its own sample"


@pytest.mark.parametrize(("name", "sample"), sorted(DOCUMENT_FAMILY_SAMPLES.items()))
def test_every_document_family_pattern_survived_the_merge(redaction, name, sample) -> None:
    entry = _by_name(redaction.DOCUMENT_PATTERNS)[name]
    assert entry.pattern.search(sample), f"{name} no longer matches its own sample"


@pytest.mark.parametrize("sample", sorted(LOG_FAMILY_SAMPLES.values()))
def test_log_family_samples_are_still_redacted_end_to_end(kubesense, sample) -> None:
    assert kubesense.redact_secrets(sample) != sample


@pytest.mark.parametrize("sample", sorted(DOCUMENT_FAMILY_SAMPLES.values()))
def test_document_family_samples_are_still_redacted_end_to_end(prd, sample) -> None:
    _rendered, redacted = prd.normalize_untrusted_markdown(sample)
    assert redacted


@pytest.mark.parametrize("name", sorted(DOCUMENT_FAMILY_SAMPLES))
def test_vendor_token_patterns_are_shared_by_both_profiles(redaction, name) -> None:
    """The merge's whole point: a token pattern one family had now serves both."""
    shared = {entry.name for entry in redaction.LOG_PATTERNS} & {
        entry.name for entry in redaction.DOCUMENT_PATTERNS
    }
    adopted = {
        "github_pat",
        "github_ghp",
        "bearer_token",
        "jwt",
        "openai_sk",
        "aws_akia",
        "client_secret_kv",
    }
    assert shared == adopted
    if name in adopted:
        assert _by_name(redaction.LOG_PATTERNS)[name] is _by_name(redaction.DOCUMENT_PATTERNS)[name]


@pytest.mark.parametrize("name", sorted({"github_pat", "github_ghp", "openai_sk", "aws_akia"}))
def test_log_output_now_masks_vendor_tokens_it_used_to_emit(kubesense, name) -> None:
    sample = DOCUMENT_FAMILY_SAMPLES[name]
    assert kubesense.redact_secrets(f"upstream rejected credential {sample}") != sample


@pytest.mark.parametrize("line", LOG_FALSE_POSITIVES)
def test_ordinary_log_lines_are_left_byte_for_byte(kubesense, line) -> None:
    assert kubesense.redact_secrets(line) == line


@pytest.mark.parametrize("sentence", DOCUMENT_FALSE_POSITIVES)
def test_ordinary_prd_sentences_report_no_redaction(prd, sentence) -> None:
    _rendered, redacted = prd.normalize_untrusted_markdown(sentence)
    assert not redacted


def test_redact_reports_which_patterns_acted(redaction) -> None:
    text = "ghp_" + "b" * 36 + " and " + "AKIA" + "E" * 16
    masked, hits = redaction.redact(text, patterns=redaction.LOG_PATTERNS)
    assert masked == "[REDACTED] and [REDACTED]"
    assert [(hit.name, hit.category, hit.count) for hit in hits] == [
        ("github_ghp", "token", 1),
        ("aws_akia", "token", 1),
    ]


def test_a_declined_predicate_match_is_not_a_hit(redaction) -> None:
    """`password: changeme` names a field; the placeholder guard declines it."""
    masked, hits = redaction.redact(
        "password: changeme",
        patterns=redaction.DOCUMENT_PATTERNS,
        marker=redaction.SECRET_MARKER,
    )
    assert masked == "password: changeme"
    assert hits == []


def test_extra_passes_catch_a_value_the_first_pass_exposed(redaction) -> None:
    """Masking an Authorization value leaves the marker the straggler pattern needs."""
    text = "requestHeaders={Authorization=abcdef MDEzMUEyRDBDNkY0NEQ0Qg==, x-merchantid=acme}"
    once, _ = redaction.redact(text, patterns=redaction.LOG_PATTERNS, passes=1)
    thrice, _ = redaction.redact(text, patterns=redaction.LOG_PATTERNS, passes=3)
    assert "MDEzMUEy" in once
    assert "MDEzMUEy" not in thrice
