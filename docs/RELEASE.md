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

`scripts/install.sh` requires one of these two flows: a `.git` checkout (`git clone`/`git checkout`), or an
extracted bundle produced by `scripts/package_release.py` (which carries `RELEASE-MANIFEST.json`).
Provenance recording fails closed, so a directory that has neither -- e.g. GitHub's auto-generated
"Source code (zip/tar.gz)" download attached to every tag/release, or a plain copy of the tree with
`.git/` stripped out -- cannot install: `distribution_version`/`source_sha` are required, not
best-effort, so there is no third, degraded path.

## Release contract

`scripts/release_contract.yaml` is the machine-readable policy a release must satisfy: the tag
shape a `VERSION` value must produce, the canonical release artifact names, the registry/host-contract
schema versions a release is compatible with, and the provenance fields every release manifest must
carry. `scripts/release_contract.py` validates the repository against it (`make validate-release-contract`,
also wired into `make validate-registry`/`make lint`), so a `VERSION` bump or a `skills.yaml`/
`host_contracts.yaml` schema change that would break release compatibility fails closed before a tag
is ever cut.

## Release bundle and manifest

`scripts/package_release.py` builds a release bundle from the Git-tracked regular files at the
repository root, minus repo-development tooling that has nothing to do with installing a skill
(`.cursor/`, `.kiro/`, `.agents/`, `.claude-plugin/`, `.codex-plugin/`, `.gitignore`, and any
`__pycache__`/`.pytest_cache`/`node_modules`/`dist` that ended up tracked) -- untracked files
(caches, build output, local secrets) never enter a release, and a tracked symlink is rejected
rather than silently dereferenced. Given the same Git tree, the resulting `.tar.gz` is
byte-for-byte reproducible -- guaranteed within a single Python interpreter/zlib build (which is
what `.github/workflows/release.yml`'s own verify step checks), not necessarily across different
interpreters or zlib versions, since gzip compression output can vary there even though the
decompressed tar payload and every `RELEASE-MANIFEST.json` file hash do not. A third party
independently rebuilding a release on a different machine should compare the manifest's per-file
SHA-256 digests (`scripts/verify_release_bundle.py`), not raw archive bytes, to confirm an
untampered release. The archive and its sidecar checksum files are written atomically
(built to a temp file, then renamed into place only once complete), so a failed build never
corrupts or destroys a prior successful artifact left over in the same output directory.

Each bundle embeds `RELEASE-MANIFEST.json` at its root with:

- `distribution_version` and `source_sha` -- exact provenance, matching `VERSION` and the Git commit
  the bundle was built from.
- `registry_schema_version` and `host_contract_schema_version` -- the schema versions the bundle is
  compatible with.
- `supported_hosts` -- every host declared in `scripts/registry/host_contracts.yaml`.
- `skill_versions` -- each skill's normalized `skill_version` from its `SKILL.md` frontmatter.
- `executable_files` -- every bundled path that must be executable (its Git index mode had the
  executable bit set).
- `files` -- a SHA-256 digest for every other file in the bundle.

The outer `.sha256` (archive checksum) and `.files.sha256` (per-file checksums) assets are still
produced alongside the archive for compatibility with existing verification tooling.

## Verifying a release bundle

`scripts/verify_release_bundle.py` independently re-derives what `RELEASE-MANIFEST.json` claims:
it extracts the archive into an isolated directory (rejecting path traversal and other unsafe tar
members), then checks that every provenance field is present and well-formed and that the manifest's
file list, hashes, and executable bits exactly match the bundle contents -- nothing missing, nothing
extra, nothing tampered. Every summary field is also cross-checked against the bundle's own bundled
source (`distribution_version` against the bundled `VERSION`, `registry_schema_version`/
`host_contract_schema_version` against the bundled `skills.yaml`/`host_contracts.yaml` and the
bundled `scripts/release_contract.yaml`'s compatibility policy, `supported_hosts`/`skill_versions`
against the bundled `host_contracts.yaml`/`skills.yaml`+`SKILL.md`), not just checked for being
well-typed -- a manifest that fabricates or drifts on any of those fields, even with every
individual file hash still matching, is rejected.

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
