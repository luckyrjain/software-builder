"""Tests for cli/sb/_update.py -- mocked-GitHub-API unit tests, plus one real-network
plumbing check clearly separated from the mocked ones (see its own docstring)."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import MagicMock, patch

import pytest

from sb._update import (
    UpdateCheckResult,
    UpdateError,
    check_for_update,
    install_update,
    run_update,
)

_FAKE_RELEASE_NEWER = {
    "tag_name": "v9.9.9",
    "assets": [
        {
            "name": "software_builder_cli-9.9.9-py3-none-any.whl",
            "browser_download_url": "https://example.invalid/wheel",
        },
        {
            "name": "software_builder_cli-9.9.9-py3-none-any.whl.sha256",
            "browser_download_url": "https://example.invalid/checksum",
        },
    ],
}


def _mock_urlopen_json(payload: dict):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(payload).encode("utf-8")
    mock_response.__enter__.return_value = mock_response
    mock_response.__exit__.return_value = False
    return mock_response


def test_unsupported_channel_is_rejected() -> None:
    with pytest.raises(UpdateError, match="unsupported channel"):
        check_for_update(channel="nightly")


def test_check_for_update_reports_available_update(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sb._update.urllib.request.urlopen",
        lambda *a, **k: _mock_urlopen_json(_FAKE_RELEASE_NEWER),
    )
    monkeypatch.setattr("sb._update._installed_version_or_unknown", lambda: "1.0.0")

    result = check_for_update(channel="stable")

    assert result.current_version == "1.0.0"
    assert result.latest_version == "9.9.9"
    assert result.update_available is True
    assert result.wheel_url == "https://example.invalid/wheel"
    assert result.checksum_url == "https://example.invalid/checksum"


def test_check_for_update_reports_no_update_when_already_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sb._update.urllib.request.urlopen",
        lambda *a, **k: _mock_urlopen_json(_FAKE_RELEASE_NEWER),
    )
    monkeypatch.setattr("sb._update._installed_version_or_unknown", lambda: "9.9.9")

    result = check_for_update(channel="stable")

    assert result.update_available is False


def test_check_for_update_missing_wheel_asset_reports_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "sb._update.urllib.request.urlopen",
        lambda *a, **k: _mock_urlopen_json({"tag_name": "v9.9.9", "assets": []}),
    )
    monkeypatch.setattr("sb._update._installed_version_or_unknown", lambda: "1.0.0")

    result = check_for_update(channel="stable")

    assert result.wheel_url is None
    assert result.checksum_url is None


def test_install_update_rejects_checksum_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    wheel_bytes = b"not a real wheel"
    wrong_checksum = "0" * 64

    def fake_download(url: str, **kwargs):
        if url == "https://example.invalid/wheel":
            return wheel_bytes
        return f"{wrong_checksum}  software_builder_cli-9.9.9-py3-none-any.whl\n".encode()

    monkeypatch.setattr("sb._update._download", fake_download)

    result = UpdateCheckResult(
        current_version="1.0.0",
        latest_version="9.9.9",
        update_available=True,
        wheel_url="https://example.invalid/wheel",
        checksum_url="https://example.invalid/checksum",
    )
    with pytest.raises(UpdateError, match="checksum mismatch"):
        install_update(result)


def test_install_update_runs_pip_install_upgrade_on_checksum_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wheel_bytes = b"not a real wheel, just bytes for the checksum test"
    real_checksum = hashlib.sha256(wheel_bytes).hexdigest()

    def fake_download(url: str, **kwargs):
        if url == "https://example.invalid/wheel":
            return wheel_bytes
        return f"{real_checksum}  software_builder_cli-9.9.9-py3-none-any.whl\n".encode()

    monkeypatch.setattr("sb._update._download", fake_download)

    result = UpdateCheckResult(
        current_version="1.0.0",
        latest_version="9.9.9",
        update_available=True,
        wheel_url="https://example.invalid/wheel",
        checksum_url="https://example.invalid/checksum",
    )
    with patch("sb._update.subprocess.run") as mock_run:
        install_update(result)
    mock_run.assert_called_once()
    called_args = mock_run.call_args.args[0]
    assert called_args[:4] == [
        __import__("sys").executable,
        "-m",
        "pip",
        "install",
    ]
    assert "--upgrade" in called_args


def test_run_update_check_only_does_not_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sb._update.urllib.request.urlopen",
        lambda *a, **k: _mock_urlopen_json(_FAKE_RELEASE_NEWER),
    )
    monkeypatch.setattr("sb._update._installed_version_or_unknown", lambda: "1.0.0")
    with patch("sb._update.install_update") as mock_install:
        exit_code = run_update(channel="stable", check_only=True)
    assert exit_code == 0
    mock_install.assert_not_called()


def test_run_update_unsupported_channel_exits_two() -> None:
    exit_code = run_update(channel="nightly", check_only=True)
    assert exit_code == 2


@pytest.mark.slow
def test_real_github_api_plumbing_only() -> None:
    """This is NOT a test that sb update's full flow works end-to-end -- this repo has never
    cut a real GitHub Release (confirmed during design: `gh release list` was empty), so
    there is no real sb wheel asset to actually download and install yet. This test only
    proves the plumbing: a real, unauthenticated GET to GitHub's real API for this repo
    succeeds and returns the JSON shape the code expects (a dict with a "tag_name" key and
    an "assets" list) -- or, just as validly, a clear 404 if no release exists at all yet,
    which this test also accepts rather than treating as a plumbing failure.
    """
    import urllib.error

    from sb._update import RELEASES_LATEST_URL, fetch_latest_release

    assert "luckyrjain/software-builder" in RELEASES_LATEST_URL
    try:
        release = fetch_latest_release()
    except UpdateError as exc:
        # A 404 (no release exists yet) is an expected, valid outcome given this repo's
        # current state -- not a plumbing failure. Any other UpdateError is a real failure.
        assert "404" in str(exc), f"unexpected fetch failure: {exc}"
        return
    assert isinstance(release, dict)
    assert "tag_name" in release
    assert "assets" in release
