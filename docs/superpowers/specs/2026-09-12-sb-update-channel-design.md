# `sb update --channel` — Design

**Status:** Approved (user-approved in brainstorming dialogue 2026-09-12)
**Date:** 2026-09-12
**Type:** Architectural (new distribution + client capability)
**Target:** `luckyrjain/software-builder`
**Spec path:** `docs/superpowers/specs/2026-09-12-sb-update-channel-design.md`

## Goal

Give the standalone `sb` CLI a real `sb update [--channel stable] [--check]` command that checks
GitHub Releases for a newer `software-builder-cli` wheel and upgrades in place — closing the last
item on the audit's Phase 4 deferred list. Since no release-channel concept exists anywhere in this
repo today, this spec defines the minimal one that's actually needed, rather than a speculative
multi-channel system with no real usage to build against.

## Why this needs a release-side change too, and why that change is small

`docs/RELEASE.md` states plainly: *"there is no CI/release-automation wiring for building or
publishing the `sb` wheel yet."* There is nothing for `sb update` to fetch. Rather than design a
client against a hypothetical future publish mechanism (speculative, untestable), this spec adds
the minimal real publish step: `.github/workflows/release.yml`'s existing tagged-release job
(`vMAJOR.MINOR.PATCH` tags, already builds/verifies/uploads the tarball + its `.sha256`/
`.files.sha256` sidecars via `gh release upload`) gains one more asset — the `sb` wheel plus a
`.whl.sha256` sidecar, built the same way `docs/RELEASE.md`'s existing "sb CLI" section already
documents (`scripts/build_sb_snapshot.py` then `python -m build cli/`), uploaded via the exact same
`gh release upload ... --clobber` / `gh release create` fallback pattern already in that workflow.
This is additive to the existing job, not a new one — the tarball release path is untouched.

## What "channel" means here (the minimal real definition)

GitHub's `GET /repos/{owner}/{repo}/releases/latest` API endpoint already excludes prereleases and
drafts by construction — that is already the correct definition of a "stable" channel, with zero
new filtering logic to invent. `sb update --channel stable` (the default) queries exactly that
endpoint. No other channel is implemented: `--channel beta`/`--channel nightly`/anything else
prints a clear "not supported yet" error and exits 2, rather than silently behaving like `stable`
or inventing a tag-naming convention (`v1.4.0-beta.1` or similar) this repository has never actually
used. A future channel needs its own design once there's a real publishing pattern to design
against — this spec does not pre-build unused branches for it.

## Client design: `cli/sb/_update.py` (new, sb-only — not vendored via `scripts/`)

This logic is inherently specific to a pip-installed `sb`: it inspects `sb`'s own installed version
via `importlib.metadata.version("software-builder-cli")` and calls `pip` to upgrade itself. A
checkout user has no equivalent need (they use `git`/`install.sh`), so unlike `install_engine.py`
this does not belong in `scripts/` and does not need the vendoring/snapshot mechanism at all — it's
a new file directly under `cli/sb/`, using only stdlib (`urllib.request` for the HTTPS GET,
`json`, `hashlib.sha256`, `subprocess` for the `pip install --upgrade` call) — no new dependency.

**Flow:**
1. `GET https://api.github.com/repos/luckyrjain/software-builder/releases/latest` (stdlib
   `urllib.request.urlopen`, a plain unauthenticated GET — public repo, no token needed; GitHub's
   anonymous rate limit is generous enough for a manually-invoked CLI command).
2. Parse `tag_name` (`vX.Y.Z`) and the `assets` list; find the asset whose name matches
   `software_builder_cli-*.whl` and its sidecar `*.whl.sha256`. Missing either → clear error
   ("no sb wheel found in the latest release — has a release with this asset ever been cut?").
3. Compare the tag's version to `importlib.metadata.version("software-builder-cli")` using
   `packaging`-free plain tuple comparison (semver is already validated by the release pipeline's
   own `SEMVER_RE`, so a simple `tuple(int(p) for p in version.split("."))` comparison is sufficient
   here — no need for the `packaging` library).
4. `--check`: print current vs. latest and whether an update is available; exit 0 either way, no
   download, no install.
5. Otherwise, if newer: download the wheel bytes, compute `hashlib.sha256(...).hexdigest()`, compare
   against the sidecar checksum content — mismatch is a hard error, never silently ignored. On
   match, write to a temp file and run `subprocess.run([sys.executable, "-m", "pip", "install",
   "--upgrade", str(temp_wheel_path)], check=True)` — `sys.executable` ensures the upgrade targets
   the same Python environment `sb` is currently running from, not some other `pip` on `PATH`.
   If already up to date: print that and exit 0, no download attempted.

Checksum verification here is a baseline integrity check (confirms the download wasn't corrupted or
tampered with by a MITM without HTTPS, since the checksum itself travels over the same GitHub API
domain) — it is explicitly **not** a substitute for real supply-chain provenance (signed
attestations, SLSA). That is the audit's Phase 5 ("signed releases/SBOM/provenance"), tracked there,
not solved by this spec.

## CLI wiring

`cli/sb/__main__.py` gains an `update` subparser: `sb update [--channel stable] [--check]`,
dispatching to `_update.run_update(channel=args.channel, check_only=args.check)`.

## The real testing constraint (stated plainly, not glossed over)

**This repository has never cut a real GitHub Release** (`gh release list` is empty — confirmed
during design, not assumed). `release.yml` exists and is presumably correct, but has never actually
run end-to-end. This means:

- The release-side change (wheel + checksum upload) can be reviewed for correctness against the
  workflow's existing, already-proven tarball-upload pattern, but **cannot be exercised for real**
  until an actual tag is pushed — that is a one-way, publicly-visible action (creates a real GitHub
  Release, triggers real CI) that this plan does not take as a side effect of implementing a
  feature. Cutting the first real release is the user's call, separately, whenever they're ready.
- The client (`cli/sb/_update.py`) is fully unit-testable against a **mocked** GitHub API response
  (version comparison, channel rejection, checksum verification success/failure, the `pip install
  --upgrade` subprocess call mocked-not-executed) — this proves the logic is correct.
- One additional real-network test queries this repo's actual GitHub API (no auth, same endpoint
  `sb update` itself calls) and asserts the response shape is what the code expects (a JSON object,
  `tag_name` present) — this is a genuine integration check of the *plumbing* (does hitting GitHub's
  real API work, does JSON parsing handle a real response), clearly marked as network-dependent
  (same `@pytest.mark.slow`-style convention the wheel-smoke test already uses), and does **not**
  claim to prove the full update-and-install flow works, since no release with an `sb` wheel asset
  exists yet to actually download.

This gap is real and is stated in the plan rather than hidden behind mocked-everything test green
checkmarks. Once the user cuts the first real tagged release (their decision, not automated by this
work), `sb update` becomes fully exercisable for real, and a follow-up manual verification (not a
new coding task) confirms it.

## Explicitly deferred

- Any channel beyond `stable` (beta/nightly) — no real publishing pattern exists yet to design one
  against.
- Signed/attested releases (SLSA, Sigstore) — audit Phase 5, unrelated to this spec's scope.
- Automatic/background update checking (e.g., `sb doctor` nagging about an available update) — this
  spec ships an explicit, user-invoked `sb update` only.
- A PyPI-based distribution path — this repo's own `docs/RELEASE.md` already treats GitHub Releases
  as the distribution point for `sb`; PyPI is a separate, larger decision this spec does not make.

## Open questions resolved during brainstorming

1. **Build both the minimal publish step and the client, vs. client-only against a hypothetical
   mechanism, vs. park entirely?** → Build both (recommended option accepted) — matches this
   session's "prove it for real" discipline used throughout the earlier `sb` diagnostics and
   install/uninstall/verify slices.

## Self-review

- **Placeholder scan:** no TBD/TODO; every command's behavior, every new file's purpose, and the
  exact API endpoint/asset-naming convention are stated concretely.
- **Internal consistency:** the "stable channel = GitHub's own /releases/latest semantics" claim is
  backed by GitHub's documented API behavior (excludes prereleases/drafts), not asserted without
  basis; the "no other channel supported" behavior is a real, explicit error path, not silently
  falling through to stable's behavior.
- **Scope check:** this is a single coherent unit (one release-workflow addition, one new client
  module, one CLI subcommand) — no further decomposition needed for a single implementation plan.
- **Ambiguity check:** "checksum mismatch is a hard error" is explicit (never silently ignored or
  downgraded to a warning); the testing-constraint section states exactly what can and cannot be
  proven right now, rather than leaving that ambiguous.
