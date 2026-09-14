# Signed Releases, SBOM, and SLSA Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sign all four release artifacts (tarball, sb wheel, plugin bundle, and a new SBOM)
keylessly via Sigstore/cosign, generate a CycloneDX SBOM for the sb wheel, and generate SLSA Build
Level 3 provenance for the release — closing the audit's Phase 5 gap with zero key-custody burden.

**Architecture:** Extend `.github/workflows/release.yml`'s existing single `release` job with three
new steps (SBOM generation, cosign install+sign, provenance-hash computation) and add a second
`provenance` job that calls GitHub's official `slsa-framework/slsa-github-generator` reusable
workflow. `docs/RELEASE.md` documents verification with the standard external tools (`cosign`,
`slsa-verifier`) — no new Python code, no new dependency, no new custom verifier.

**Tech Stack:** GitHub Actions YAML + shell; three new third-party actions, all SHA-pinned per this
repo's existing `scripts/check_pinned_actions.py` convention (already resolved below, not left for
the implementer to guess).

## Global Constraints

- Every new `uses:` reference (action or reusable workflow) must be a 40-character commit SHA with a
  `# vX.Y.Z` comment, exactly like every existing reference in this repo's workflows —
  `make lint`/`scripts/check_pinned_actions.py` fails closed on anything less. The exact SHAs below
  were resolved live against each project's actual latest release at plan-writing time
  (2026-09-14) — do not substitute a different version without re-resolving its real commit SHA the
  same way (`gh api repos/<owner>/<repo>/commits/<tag> --jq '.sha'`).
  - `sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6` (v4.1.2)
  - `anchore/sbom-action@3ad7283483fc7af8ff2b4ea19663c2d5ca935e26` (v0.24.2)
  - `slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a` (v2.1.0)
- Signing covers all four final artifacts uniformly (tarball, wheel, plugin bundle, SBOM). The SBOM
  itself covers only the wheel — not the tarball or plugin bundle (neither has an installable
  dependency graph; see design spec).
- `scripts/release_contract.yaml`, `scripts/verify_release_bundle.py`, and
  `scripts/package_release.py` are untouched — this plan is purely additive to the CI pipeline, and
  follows the same "new release-side artifact, not enumerated in release_contract.yaml" precedent
  the sb wheel and plugin bundle already established.
- No custom Python signature/provenance verifier — `docs/RELEASE.md` documents the standard `cosign`/
  `slsa-verifier` commands directly.
- This is CI-only work that cannot be exercised end-to-end until a real tag is pushed (the same
  honest testing constraint `sb update`'s and the plugin bundle's own release-side changes already
  documented) — verification here means: the workflow YAML is valid and internally consistent, every
  action reference is pinned, and the shell logic is correct by inspection/dry-run where possible,
  not a live cut release.

---

### Task 1: Add SBOM generation, cosign signing, and SLSA provenance to the release workflow

**Files:**
- Modify: `.github/workflows/release.yml`
- Modify: `docs/RELEASE.md`

**Interfaces:**
- Consumes: the existing `release` job's final artifact set on disk at the point this task's new
  steps run (`dist/software-builder-<version>.tar.gz`, the sb wheel path,
  `dist/software-builder-plugin-<version>.tar.gz`).
- Produces: a `hashes` output on the `release` job (`outputs: hashes: ${{ steps.hash.outputs.hashes }}`),
  consumed by the new `provenance` job.

- [ ] **Step 1: Export the wheel path so later steps can reference it**

The existing "Build and upload sb wheel" step (around line 95-104) computes `WHEEL_PATH` as a local
shell variable, invisible to later steps. Add one line exporting it to `$GITHUB_ENV` so the new SBOM
and signing steps (which run later in the same job) can read it as `${{ env.WHEEL_PATH }}`. Change:

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

to:

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
          echo "WHEEL_PATH=$WHEEL_PATH" >> "$GITHUB_ENV"
```

- [ ] **Step 2: Add the SBOM generation step**

Add directly after the existing "Build and upload plugin bundle" step (the last step in the current
file):

```yaml
      - name: Generate SBOM for sb wheel
        uses: anchore/sbom-action@3ad7283483fc7af8ff2b4ea19663c2d5ca935e26 # v0.24.2
        with:
          file: ${{ env.WHEEL_PATH }}
          format: cyclonedx-json
          output-file: dist/sb-wheel/software-builder-cli.cdx.json
          upload-artifact: false
          upload-release-assets: false
```

`upload-artifact`/`upload-release-assets` are both set `false` because this repo's convention is
explicit `gh release upload` calls (every other artifact in this workflow is uploaded that way) —
the SBOM gets uploaded in Step 4 below, alongside its own signature, not by this action itself.

- [ ] **Step 3: Install cosign and sign all four artifacts**

Add directly after the SBOM step:

```yaml
      - name: Install cosign
        uses: sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6 # v4.1.2

      - name: Sign and upload release artifacts
        env:
          GH_TOKEN: ${{ github.token }}
          RELEASE_TAG: ${{ steps.tag.outputs.name }}
        run: |
          VERSION="${RELEASE_TAG#v}"
          ARTIFACTS=(
            "dist/software-builder-${VERSION}.tar.gz"
            "${WHEEL_PATH}"
            "dist/software-builder-plugin-${VERSION}.tar.gz"
            "dist/sb-wheel/software-builder-cli.cdx.json"
          )
          BUNDLES=()
          for artifact in "${ARTIFACTS[@]}"; do
            cosign sign-blob --yes --bundle "${artifact}.cosign.bundle" "$artifact"
            BUNDLES+=("${artifact}.cosign.bundle")
          done
          gh release upload "$RELEASE_TAG" \
            "dist/sb-wheel/software-builder-cli.cdx.json" \
            "${BUNDLES[@]}" \
            --clobber
```

`cosign sign-blob --yes --bundle` runs keylessly: with the job's `id-token: write` permission (added
in Step 5), cosign automatically obtains a GitHub Actions OIDC token and uses it for Sigstore's
Fulcio/Rekor keyless flow — no key, no secret, no additional flag needed beyond that permission being
present at the job level. `--yes` skips the interactive confirmation prompt (non-interactive CI run).

- [ ] **Step 4: Compute and expose the provenance subject hashes**

Add directly after the signing step — this must be the LAST step to touch any of the four artifacts,
since the hash list is the exact input the provenance job signs over:

```yaml
      - name: Generate provenance subjects
        id: hash
        env:
          RELEASE_TAG: ${{ steps.tag.outputs.name }}
        run: |
          VERSION="${RELEASE_TAG#v}"
          HASHES=$(sha256sum \
            "dist/software-builder-${VERSION}.tar.gz" \
            "${WHEEL_PATH}" \
            "dist/software-builder-plugin-${VERSION}.tar.gz" \
            "dist/sb-wheel/software-builder-cli.cdx.json" \
            | base64 -w0)
          echo "hashes=$HASHES" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 5: Add job-level `id-token: write` permission and the `hashes` output**

The existing `release` job definition (around line 18) currently has no `permissions:`/`outputs:`
block of its own (it inherits the workflow-level `permissions: contents: write` at the top of the
file). Add both directly to the job:

```yaml
jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      id-token: write
    outputs:
      hashes: ${{ steps.hash.outputs.hashes }}
    steps:
```

(This makes the job's own `permissions:` block the effective one, per GitHub Actions' scoping rules —
copy the existing workflow-level `contents: write` down into it rather than relying on the top-level
block once a job-level one exists, so nothing is silently narrowed.)

- [ ] **Step 6: Add the `provenance` job**

Add as a new top-level job, after the `release` job's closing (end of file):

```yaml
  provenance:
    needs: release
    permissions:
      actions: read
      id-token: write
      contents: write
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@f7dd8c54c2067bafc12ca7a55595d5ee9b75204a # v2.1.0
    with:
      base64-subjects: ${{ needs.release.outputs.hashes }}
      upload-assets: true
```

**Open verification point, flagged honestly rather than guessed:** this repo's release workflow
supports two triggers — a real `push: tags:` event, and `workflow_dispatch` against an *existing*
tag (used to rebuild a release without re-tagging). The SLSA generic generator's `upload-assets: true`
path is documented and proven for the tag-push trigger; its behavior under this repo's
`workflow_dispatch` path (which doesn't push a new tag, just re-runs against one) is not something
this plan can verify without a live test. If the first real run via `workflow_dispatch` behaves
unexpectedly here (e.g. it can't determine which release to attach the provenance asset to), that is
a real, separate follow-up to investigate then — not something to work around speculatively now.

- [ ] **Step 7: Document verification in `docs/RELEASE.md`**

Add a new section directly after the existing "## Verifying a release bundle" section (after its
closing code fence):

```markdown
## Verifying signatures and provenance

Every release artifact (the tarball, the `sb` wheel, the plugin bundle, and the wheel's SBOM) is
signed keylessly via [Sigstore](https://www.sigstore.dev/) — no private key to trust, just GitHub
Actions' own OIDC identity and the public Rekor transparency log:

```bash
cosign verify-blob --bundle software-builder-1.4.0.tar.gz.cosign.bundle \
  --certificate-identity-regexp 'https://github.com/luckyrjain/software-builder/\.github/workflows/release\.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  software-builder-1.4.0.tar.gz
```

The release also carries [SLSA Build Level 3](https://slsa.dev/) provenance, verifiable with
[`slsa-verifier`](https://github.com/slsa-framework/slsa-verifier):

```bash
slsa-verifier verify-artifact software-builder-1.4.0.tar.gz \
  --provenance-path multiple.intoto.jsonl \
  --source-uri github.com/luckyrjain/software-builder \
  --source-tag v1.4.0
```

The `sb` wheel's dependency graph is published as a CycloneDX SBOM
(`software-builder-cli.cdx.json`), signed the same way as every other release asset.
```

- [ ] **Step 8: Validate the workflow YAML and pinning**

Run: `python3 scripts/check_pinned_actions.py`
Expected: exit 0, no unpinned-reference errors for any of the three new `uses:` lines.

Run (or the Python equivalent if `yq`/`python3 -c` is more convenient in this environment):
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))"
```
Expected: no exception — confirms the file is still valid YAML after all the edits above.

Run: `make lint` (or at minimum whatever subset covers `lint-actions-security`/zizmor and
`check_pinned_actions.py` — check `make/core.mk` for the exact target names if `make lint` is too
slow to run in full here)
Expected: no new findings attributable to this task's changes.

- [ ] **Step 9: Commit**

```bash
git add .github/workflows/release.yml docs/RELEASE.md
git commit -m "Add Sigstore signing, SBOM, and SLSA provenance to the release workflow"
```

## Self-Review

- **Placeholder scan:** no TBD/TODO; every SHA, every step body, and the docs section is complete,
  concrete text — the one explicitly-flagged open item (workflow_dispatch interaction with the SLSA
  generator) is stated as a real, honest unknown to verify on the first live run, not glossed over as
  if it were already confirmed.
- **Spec coverage:** the design spec's entire scope (signing all four artifacts, SBOM for the wheel
  only, SLSA provenance via the official generator, documented verification with standard tools) is
  covered by this single task.
- **Type consistency:** `WHEEL_PATH` is exported once (Step 1) and consumed identically in every
  later step that needs it (Steps 2, 3, 4) — one source of truth, not re-derived three different ways.
