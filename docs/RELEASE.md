# Release policy

software-builder uses a single repository-level semantic version in `VERSION`. Installed skill
packages record `distribution_version` and `source_sha` in `.software-builder-manifest.json`.

## Installing a tagged release

```bash
git checkout v1.4.0
bash scripts/install.sh --agent cursor
```

Or download a checksummed bundle from GitHub Releases:

```bash
python3 scripts/package_release.py --output-dir dist
shasum -c dist/software-builder-1.4.0.sha256
tar -xzf dist/software-builder-1.4.0.tar.gz
cd software-builder-1.4.0
bash scripts/install.sh
```

## Release contract

`scripts/release_contract.yaml` is the machine-readable policy a release must satisfy: the tag
shape a `VERSION` value must produce, the canonical release artifact names, the registry/host-contract
schema versions a release is compatible with, and the provenance fields every release manifest must
carry. `scripts/release_contract.py` validates the repository against it (`make validate-release-contract`,
also wired into `make validate-registry`/`make lint`), so a `VERSION` bump or a `skills.yaml`/
`host_contracts.yaml` schema change that would break release compatibility fails closed before a tag
is ever cut.

## Release bundle and manifest

`scripts/package_release.py` builds a release bundle from exactly the Git-tracked regular files at
the repository root -- untracked files (caches, build output, local secrets) never enter a release,
and a tracked symlink is rejected rather than silently dereferenced. Given the same Git tree, the
resulting `.tar.gz` is byte-for-byte reproducible.

Each bundle embeds `RELEASE-MANIFEST.json` at its root with:

- `distribution_version` and `source_sha` -- exact provenance, matching `VERSION` and the Git commit
  the bundle was built from.
- `registry_schema_version` and `host_contract_schema_version` -- the schema versions the bundle is
  compatible with.
- `files` -- a SHA-256 digest for every other file in the bundle.

The outer `.sha256` (archive checksum) and `.files.sha256` (per-file checksums) assets are still
produced alongside the archive for compatibility with existing verification tooling.

## Verifying a release bundle

`scripts/verify_release_bundle.py` independently re-derives what `RELEASE-MANIFEST.json` claims:
it extracts the archive into an isolated directory (rejecting path traversal and other unsafe tar
members), then checks that every provenance field is present and well-formed and that the manifest's
file list and hashes exactly match the bundle contents -- nothing missing, nothing extra, nothing
tampered.

```bash
python3 scripts/verify_release_bundle.py dist/software-builder-1.4.0.tar.gz
```

`.github/workflows/release.yml` runs both the release-contract validator and the bundle verifier
after packaging and before uploading release assets, so a bundle that fails either check is never
published.

## Verifying an install

```bash
bash scripts/install.sh --verify ~/.cursor/skills/pr-review
python3 scripts/doctor.py --available gitlab.get_merge_request,gitlab.get_merge_request_diffs
```

## Upgrading and rolling back

- Upgrading: `git checkout vNEW.VERSION` (or download and extract the newer bundle) and re-run
  `bash scripts/install.sh`; `scripts/doctor.py` and `--verify` compare the installed
  `.software-builder-manifest.json` against the running `VERSION`/source SHA to confirm the upgrade
  landed.
- Rolling back: check out the previous tag the same way and reinstall -- `scripts/install.sh` keeps
  the previous package on install failure (see `scripts/tests/test_install_rollback.py`) so a bad
  install doesn't leave a skill half-upgraded.
- A major-version bump (see below) is the signal that an upgrade or rollback may need manual
  migration steps; check `CHANGELOG.md` first.

## Breaking changes

- Increment the major version in `VERSION` when registry schema, install packaging, or a skill's
  workflow contract changes incompatibly.
- Ship migration notes in `CHANGELOG.md` and the per-skill changelog when applicable.
- Behavioral eval regressions (`make validate-evals`) gate releases once CI is wired to tagged builds.
- Tagged releases: push `vMAJOR.MINOR.PATCH` matching `VERSION`; `.github/workflows/release.yml` runs
  `make lint`, packages checksummed bundles, validates the release contract, verifies the built
  bundle, and publishes GitHub Release assets.
- Compatibility matrix: `generated/catalogue/compatibility-matrix.md` (regenerate with `make generate`).
