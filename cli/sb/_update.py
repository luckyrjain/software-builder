"""sb update: check GitHub Releases for a newer software-builder-cli wheel and upgrade in
place. Sb-only -- unlike scripts/install_engine.py, this inspects sb's own installed pip
package and calls pip to upgrade it, which has no equivalent need for a checkout user, so it
is not vendored via scripts/ and needs no snapshot/registry data at all.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pip_installed_version
from pathlib import Path

# GitHub's own /releases/latest semantics (excludes prereleases and drafts) is already the
# correct definition of a "stable" channel -- no filtering logic to invent. No other channel
# is implemented; see docs/superpowers/specs/2026-09-12-sb-update-channel-design.md for why.
RELEASES_LATEST_URL = "https://api.github.com/repos/luckyrjain/software-builder/releases/latest"
SUPPORTED_CHANNELS = ("stable",)
_WHEEL_NAME_PREFIX = "software_builder_cli-"


class UpdateError(Exception):
    """Raised for any sb update failure, with a message meant to be shown to the user directly."""


@dataclass(frozen=True)
class UpdateCheckResult:
    current_version: str
    latest_version: str
    update_available: bool
    wheel_url: str | None
    checksum_url: str | None


def _installed_version_or_unknown() -> str:
    try:
        return _pip_installed_version("software-builder-cli")
    except PackageNotFoundError:
        return "0.0.0"


def _version_tuple(version: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        raise UpdateError(f"could not parse version {version!r}") from exc


def fetch_latest_release(*, timeout: float = 10.0) -> dict:
    """Fetch the latest stable release's JSON payload from GitHub's API."""
    request = urllib.request.Request(
        RELEASES_LATEST_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "sb-update"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub API request failed: {exc.code} {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"could not reach GitHub API: {exc.reason}") from exc


def _find_asset(release: dict, *, suffix: str) -> dict | None:
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if name.startswith(_WHEEL_NAME_PREFIX) and name.endswith(suffix):
            return asset
    return None


def check_for_update(*, channel: str = "stable") -> UpdateCheckResult:
    if channel not in SUPPORTED_CHANNELS:
        raise UpdateError(
            f"unsupported channel {channel!r} -- only {', '.join(SUPPORTED_CHANNELS)} is "
            "supported today"
        )
    release = fetch_latest_release()
    tag_name = release.get("tag_name", "")
    if not tag_name.startswith("v"):
        raise UpdateError(f"unexpected tag_name from GitHub: {tag_name!r}")
    latest_version = tag_name[1:]
    current = _installed_version_or_unknown()

    wheel_asset = _find_asset(release, suffix=".whl")
    checksum_asset = _find_asset(release, suffix=".whl.sha256")

    return UpdateCheckResult(
        current_version=current,
        latest_version=latest_version,
        update_available=_version_tuple(latest_version) > _version_tuple(current),
        wheel_url=wheel_asset.get("browser_download_url") if wheel_asset else None,
        checksum_url=checksum_asset.get("browser_download_url") if checksum_asset else None,
    )


def _download(url: str, *, timeout: float = 30.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "sb-update"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"download failed: {exc.code} {exc.reason} ({url})") from exc
    except urllib.error.URLError as exc:
        raise UpdateError(f"could not download {url}: {exc.reason}") from exc


def install_update(result: UpdateCheckResult) -> None:
    if result.wheel_url is None or result.checksum_url is None:
        raise UpdateError(
            f"no sb wheel found in the latest release (tag v{result.latest_version}) -- "
            "has a release with this asset ever been cut?"
        )
    wheel_bytes = _download(result.wheel_url)
    checksum_line = _download(result.checksum_url).decode("utf-8")
    checksum_parts = checksum_line.split()
    if not checksum_parts:
        raise UpdateError(f"malformed checksum file at {result.checksum_url}")
    expected_checksum = checksum_parts[0].strip()
    actual_checksum = hashlib.sha256(wheel_bytes).hexdigest()
    if actual_checksum != expected_checksum:
        raise UpdateError(
            f"checksum mismatch for downloaded wheel: expected {expected_checksum}, got "
            f"{actual_checksum}"
        )
    with tempfile.TemporaryDirectory() as tmp_dir:
        wheel_path = Path(tmp_dir) / f"{_WHEEL_NAME_PREFIX}{result.latest_version}-py3-none-any.whl"
        wheel_path.write_bytes(wheel_bytes)
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", str(wheel_path)],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            raise UpdateError(
                f"pip install failed (exit {exc.returncode}) -- sb may be partially upgraded; "
                "re-run 'sb update' or reinstall manually"
            ) from exc


def run_update(*, channel: str, check_only: bool) -> int:
    try:
        result = check_for_update(channel=channel)
    except UpdateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not result.update_available:
        print(f"ok: already up to date (sb {result.current_version})")
        return 0

    if check_only:
        print(f"update available: {result.current_version} -> {result.latest_version}")
        return 0

    print(f"updating: {result.current_version} -> {result.latest_version}")
    try:
        install_update(result)
    except UpdateError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"ok: updated to {result.latest_version}")
    return 0
