# `sb update --channel` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `sb` a real `update [--channel stable] [--check]` command that checks GitHub Releases for a newer `software-builder-cli` wheel and upgrades in place.

**Architecture:** A small additive step to the existing `.github/workflows/release.yml` tagged-release job uploads the `sb` wheel + a checksum sidecar as release assets (nothing else about that job changes). A new, sb-only `cli/sb/_update.py` module (stdlib only — `urllib.request`, `json`, `hashlib`) queries GitHub's `/releases/latest` endpoint (which already *is* the "stable" channel by construction), verifies the downloaded wheel's checksum, and shells out to `pip install --upgrade`.

**Tech Stack:** Python 3.12+ stdlib only (`urllib.request`, `json`, `hashlib`, `subprocess`, `tempfile`), `gh` CLI (already used elsewhere in `release.yml`).

## Global Constraints

- Only `--channel stable` is supported. Any other value is a clear error (exit 2), never silent fallback to stable's behavior.
- No new dependencies anywhere in this plan.
- Checksum mismatch on a downloaded wheel is a hard error — never silently ignored or downgraded to a warning.
- This repo has never cut a real GitHub Release (`gh release list` is empty, confirmed during design) — no task in this plan may claim a fully-real end-to-end test exists. Tests are: unit tests against a mocked GitHub API (the logic), plus one real-network test that only proves the plumbing (a real HTTP GET to this repo's actual API succeeds and returns the expected JSON shape) — clearly distinguished from each other in the test names/docstrings.
- `sys.executable` is always used for the `pip install --upgrade` subprocess call, never a bare `pip` on `PATH`, so the upgrade targets the same environment `sb` is running from.

---

### Task 1: Upload the `sb` wheel + checksum as a release asset

**Files:**
- Modify: `.github/workflows/release.yml`

**Interfaces:**
- Consumes: `scripts/build_sb_snapshot.py` (existing), `python -m build` (existing dev dependency, already in `requirements.lock`), `gh release upload` (existing pattern in the same workflow)
- Produces: two new release assets per tag — `software_builder_cli-<version>-py3-none-any.whl` and its `.sha256` sidecar

This task has no pytest-style test — it's a CI workflow change. Verification is: the YAML parses, the new step matches the existing tarball-upload step's structure/conventions exactly, and it runs *after* the existing "Upload release assets" step (which creates the release if it doesn't already exist via its `gh release upload ... || gh release create ...` fallback) so a plain `gh release upload --clobber` is always valid here.

- [ ] **Step 1: Read the current file to find the exact insertion point**

Run: `grep -n "Upload release assets" -A 20 .github/workflows/release.yml`
Confirm the existing step's exact structure (env vars, `VERSION="${RELEASE_TAG#v}"` pattern, the `gh release upload ... --clobber` line) before adding the new step immediately after it, so the new step matches conventions exactly rather than approximating them.

- [ ] **Step 2: Add the new step**

Insert this new step immediately after the existing "Upload release assets" step, at the same indentation level (as a sibling step in the same job):

```yaml
      - name: Build and upload sb wheel
        env:
          GH_TOKEN: ${{ github.token }}
          RELEASE_TAG: ${{ steps.tag.outputs.name }}
        run: |
          python3 scripts/build_sb_snapshot.py
          python3 -m build --wheel --outdir dist/sb-wheel cli/
          WHEEL_PATH="$(ls dist/sb-wheel/software_builder_cli-*.whl)"
          sha256sum "$WHEEL_PATH" > "${WHEEL_PATH}.sha256"
          gh release upload "$RELEASE_TAG" "$WHEEL_PATH" "${WHEEL_PATH}.sha256" --clobber
```

(`build` is already in `requirements.lock`, installed earlier in the same job by the existing `python3 -m pip install --require-hashes -r requirements.lock` step — no separate `pip install build` needed here.)

- [ ] **Step 3: Verify the YAML is well-formed**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" && echo ok`
Expected: `ok`, no exception

- [ ] **Step 4: Verify no new lint findings**

Run: `make lint-actions-security` (if `zizmor` is installed locally; otherwise note in your report that this only runs in CI and confirm no new `uses:` line was added — this step introduces no new GitHub Action, only shell commands, so `zizmor`'s pinned-action checks have nothing new to flag)
Run: `python3 scripts/check_pinned_actions.py` (this repo's own pinned-action checker — confirms no new unpinned `uses:` was introduced, which is true here since this step adds no `uses:` line at all)

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "$(cat <<'EOF'
Upload the sb wheel + checksum as a release asset

Additive to the existing tagged-release job: builds cli/ into a wheel
the same way docs/RELEASE.md's "sb CLI" section already documents,
uploads it and a sha256 sidecar alongside the existing tarball
release assets. This is the first real distribution point for sb --
the release-side prerequisite for sb update.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: `cli/sb/_update.py` core logic

**Files:**
- Create: `cli/sb/_update.py`
- Test: `cli/tests/test_sb_update.py`

**Interfaces:**
- Produces: `UpdateError` (exception), `UpdateCheckResult` (frozen dataclass: `current_version: str`, `latest_version: str`, `update_available: bool`, `wheel_url: str | None`, `checksum_url: str | None`), `check_for_update(*, channel: str = "stable") -> UpdateCheckResult`, `install_update(result: UpdateCheckResult) -> None`, `run_update(*, channel: str, check_only: bool) -> int`

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_sb_update.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && python3 -m pytest tests/test_sb_update.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'sb._update'`

- [ ] **Step 3: Write `cli/sb/_update.py`**

```python
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
    return tuple(int(part) for part in version.split("."))


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
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def install_update(result: UpdateCheckResult) -> None:
    if result.wheel_url is None or result.checksum_url is None:
        raise UpdateError(
            f"no sb wheel found in the latest release (tag v{result.latest_version}) -- "
            "has a release with this asset ever been cut?"
        )
    wheel_bytes = _download(result.wheel_url)
    checksum_line = _download(result.checksum_url).decode("utf-8")
    expected_checksum = checksum_line.split()[0].strip()
    actual_checksum = hashlib.sha256(wheel_bytes).hexdigest()
    if actual_checksum != expected_checksum:
        raise UpdateError(
            f"checksum mismatch for downloaded wheel: expected {expected_checksum}, got "
            f"{actual_checksum}"
        )
    with tempfile.TemporaryDirectory() as tmp_dir:
        wheel_path = Path(tmp_dir) / f"{_WHEEL_NAME_PREFIX}{result.latest_version}-py3-none-any.whl"
        wheel_path.write_bytes(wheel_bytes)
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", str(wheel_path)],
            check=True,
        )


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && python3 -m pytest tests/test_sb_update.py -v -m "not slow"`
Expected: PASS (all tests except the one marked `slow`)

Run: `cd cli && python3 -m pytest tests/test_sb_update.py -v` (include the slow one — this makes a real network call; expected to pass whether or not a release exists yet, per that test's own docstring)
Expected: PASS

- [ ] **Step 5: Register the `slow` marker for `cli/`'s own pytest config**

Check `cli/pyproject.toml`'s `[tool.pytest.ini_options]` — if it has no `markers` list yet, add one:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "slow: makes a real network call; not part of the default fast loop",
]
```

(If it already has other content in that section from a prior task, add the `markers` key alongside it rather than replacing the section.)

- [ ] **Step 6: Commit**

```bash
git add cli/sb/_update.py cli/tests/test_sb_update.py cli/pyproject.toml
git commit -m "$(cat <<'EOF'
Add cli/sb/_update.py: check GitHub Releases and upgrade sb in place

Stdlib-only (urllib.request/json/hashlib) -- no new dependency. Only
--channel stable is supported; GitHub's own /releases/latest
semantics already is that channel's correct definition. Checksum
mismatch on a downloaded wheel is a hard error. Tests are mocked
against a fake GitHub API response, plus one network-dependent test
that only proves the plumbing (this repo has never cut a real
release yet, so no full end-to-end proof is possible today -- stated
in that test's own docstring, not hidden).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Wire `sb update` into the CLI

**Files:**
- Modify: `cli/sb/__main__.py`
- Test: `cli/tests/test_sb_update_cli.py`

**Interfaces:**
- Consumes: `sb._update.run_update(*, channel: str, check_only: bool) -> int` (Task 2)

- [ ] **Step 1: Write the failing tests**

```python
# cli/tests/test_sb_update_cli.py
"""Tests for the `sb update` subcommand wiring in cli/sb/__main__.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

CLI_ROOT = Path(__file__).resolve().parents[1]


def _run_sb(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sb", *args],
        cwd=CLI_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_update_help_lists_channel_and_check_flags() -> None:
    result = _run_sb("update", "--help")

    assert result.returncode == 0
    assert "--channel" in result.stdout
    assert "--check" in result.stdout


def test_update_rejects_unsupported_channel() -> None:
    result = _run_sb("update", "--channel", "nightly", "--check")

    assert result.returncode == 2
    assert "unsupported channel" in result.stderr


def test_update_defaults_to_stable_channel() -> None:
    """Doesn't hit the network (unittest.mock via subprocess isn't possible across a process
    boundary) -- instead calls main() in-process with sb._update.run_update mocked, proving
    the CLI dispatch passes the right defaulted arguments through."""
    import sb.__main__ as sb_main

    with patch("sb.__main__.run_update") as mock_run_update:
        mock_run_update.return_value = 0
        exit_code = sb_main.main(["update", "--check"])

    assert exit_code == 0
    mock_run_update.assert_called_once_with(channel="stable", check_only=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd cli && python3 -m pytest tests/test_sb_update_cli.py -v`
Expected: FAIL — `update` is not a recognized subcommand yet

- [ ] **Step 3: Wire the subcommand**

In `cli/sb/__main__.py`, add the import (alongside the existing `from scripts.install_support import cmd_verify` line):

```python
from sb._update import run_update  # noqa: E402
```

In `main()`, after the `verify_parser` block (before `args = parser.parse_args(argv)`):

```python
    update_parser = subparsers.add_parser("update", help="check for and install a newer sb release")
    update_parser.add_argument(
        "--channel", default="stable", help="release channel (only 'stable' is supported today)"
    )
    update_parser.add_argument(
        "--check", action="store_true", help="only check for an update, do not install it"
    )
```

After the `if args.command == "verify":` dispatch line:

```python
    if args.command == "update":
        return run_update(channel=args.channel, check_only=args.check)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd cli && python3 -m pytest tests/test_sb_update_cli.py -v`
Expected: PASS (all 3 tests)

- [ ] **Step 5: Run the full cli/tests/ suite to confirm no regressions**

Run: `cd cli && python3 -m pytest tests/ -v -m "not slow"`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add cli/sb/__main__.py cli/tests/test_sb_update_cli.py
git commit -m "$(cat <<'EOF'
Wire sb update into the CLI

sb update [--channel stable] [--check], dispatching to
sb._update.run_update. Channel defaults to "stable"; any other value
is rejected by run_update itself (Task 2), not re-validated here.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review

**Spec coverage:** the spec's release-side addition (wheel + checksum asset), the client's channel restriction (`stable` only, clear error otherwise), the checksum-mismatch-is-a-hard-error requirement, and the stated testing constraint (mocked unit tests + one honestly-scoped real-network plumbing test) are all covered by name in Tasks 1-3. `docs/RELEASE.md`'s existing "sb CLI" section already documents the build order this plan's Task 1 reuses — no new build-order documentation needed.

**Placeholder scan:** every step has complete, runnable code. Task 1 has no pytest-style test (a CI workflow change genuinely doesn't have one) — this is stated explicitly as the real verification method (YAML parses + matches existing conventions + no new unpinned action), not silently skipped.

**Type consistency:** `UpdateCheckResult`'s field names and `run_update(*, channel: str, check_only: bool) -> int`'s signature are used identically across Task 2 (definition) and Task 3 (CLI call site and its mocked-call assertion).

**Scope check:** 3 tasks, each independently testable (Task 1 verified via YAML/lint checks, Task 2 via mocked unit tests + the honestly-scoped network test, Task 3 via CLI subprocess/mocked-dispatch tests). No further decomposition needed. Explicitly deferred items from the design spec (other channels, signed releases, automatic update-nagging, PyPI) are not smuggled into any task here.
