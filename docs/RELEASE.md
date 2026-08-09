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

## Verifying an install

```bash
bash scripts/install.sh --verify ~/.cursor/skills/pr-review
python3 scripts/doctor.py --available gitlab.get_merge_request,gitlab.get_merge_request_diffs
```

## Breaking changes

- Increment the major version in `VERSION` when registry schema, install packaging, or a skill's
  workflow contract changes incompatibly.
- Ship migration notes in `CHANGELOG.md` and the per-skill changelog when applicable.
- Behavioral eval regressions (`make validate-evals`) gate releases once CI is wired to tagged builds.
- Tagged releases: push `vMAJOR.MINOR.PATCH` matching `VERSION`; `.github/workflows/release.yml` runs `make lint`, packages checksummed bundles, and publishes GitHub Release assets.
- Compatibility matrix: `generated/catalogue/compatibility-matrix.md` (regenerate with `make generate`).
