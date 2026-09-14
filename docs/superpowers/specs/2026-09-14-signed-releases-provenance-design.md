# Signed Releases, SBOM, and SLSA Provenance — Design

**Status:** Approved (user-approved in brainstorming dialogue 2026-09-14)
**Date:** 2026-09-14
**Type:** CI/release-pipeline addition (additive, security-sensitive)
**Target:** `luckyrjain/software-builder`
**Spec path:** `docs/superpowers/specs/2026-09-14-signed-releases-provenance-design.md`

## Goal

Close the audit's Phase 5 gap ("supply-chain trust incomplete"). Today every release artifact
(`software-builder-<version>.tar.gz`, `software_builder_cli-<version>-py3-none-any.whl`,
`software-builder-plugin-<version>.tar.gz`) ships with a SHA-256 checksum only — proof against
corruption in transit, not proof of who actually built it. This spec adds cryptographic signing, an
SBOM for the one artifact with a real dependency graph, and SLSA build provenance, closing that gap
without introducing any key-custody burden for a single-maintainer project.

## Decisions made in brainstorming (all explicitly approved, not defaulted)

1. **Signing: Sigstore keyless via GitHub Actions OIDC.** No private key is generated, stored, or
   rotated by this repository or its maintainer. Each CI run signs using its own short-lived,
   workflow-scoped OIDC identity; the public Sigstore transparency log (Rekor) is the trust anchor,
   not a secret. This is the standard, GitHub-recommended pattern for individual-maintainer open
   source (the same trust model npm/PyPI's own "trusted publishing" rollouts use). A maintainer-held
   GPG/age key was explicitly considered and rejected: it adds real, ongoing operational burden
   (secure storage, rotation, and an unrecoverable trust break if the key is ever lost or
   compromised) for no corresponding benefit over keyless signing in this context.
2. **SBOM: CycloneDX via `syft`, scoped to the `sb` wheel only.** The main tarball and the plugin
   bundle are skill-content archives — markdown/YAML — with no installable dependency graph of their
   own; there is nothing meaningful for an SBOM to describe there. `software-builder-cli` (the `sb`
   wheel, `cli/pyproject.toml`) is the one release artifact that is actually installable software
   with a real dependency (`PyYAML>=6.0.3` today), so it is the one artifact that gets an SBOM.
3. **Provenance: SLSA Build Level 3 via `slsa-framework/slsa-github-generator`'s official reusable
   workflow.** Not custom-built — this is GitHub's own maintained, widely-adopted generator,
   reusing the same OIDC identity the signing step already established. Its documented design
   requires the provenance-generation step to run as a separate job with its own minimal permission
   set (isolated from the build job's broader token scope) — this is a structural requirement of the
   tool, not a design choice made here.

## Scope: the three existing release artifacts, covered consistently

`software-builder-<version>.tar.gz`, `software_builder_cli-<version>-py3-none-any.whl`, and
`software-builder-plugin-<version>.tar.gz` — the three artifacts `.github/workflows/release.yml`
already builds and uploads today (the last two added by two prior, already-merged phases of this
same audit). Signing and provenance cover all three uniformly; the SBOM covers only the wheel, per
decision 2 above.

`scripts/release_contract.yaml`'s `artifact_name_templates` already excludes the sb wheel and the
plugin bundle (confirmed: it enumerates only the original tarball's three assets) — this is existing,
established precedent from the two prior phases, not a gap this spec introduces or needs to fix. The
new signature/SBOM/provenance files follow that same precedent: real, checked, uploaded release
assets that are not enumerated in `release_contract.yaml`'s schema.

## Workflow shape

### Job 1 (`release`, existing — extended)

Two new steps added near the end, after every artifact currently built by this job exists in `dist/`:

**Sign every artifact.** Install `cosign` (`sigstore/cosign-installer`, SHA-pinned per this repo's
`scripts/check_pinned_actions.py` convention — exact current release SHA resolved at implementation
time, not guessed here), then for each of the three primary artifacts:

```bash
cosign sign-blob --yes --bundle "$ARTIFACT.cosign.bundle" "$ARTIFACT"
```

`--yes` skips the interactive confirmation prompt (this is a non-interactive CI run); `--bundle`
produces cosign's modern single-file bundle format (signature + certificate + transparency-log
inclusion proof in one file), the artifact a downloader verifies against with
`cosign verify-blob --bundle`. Each `.cosign.bundle` is uploaded to the release alongside its
artifact and existing `.sha256` sidecar.

**Generate the SBOM.** Install `syft` (`anchore/sbom-action` or the `syft` CLI directly, SHA-pinned),
run against the built wheel:

```bash
syft "$WHEEL_PATH" -o cyclonedx-json="dist/sb-wheel/software_builder_cli-${VERSION}.cdx.json"
```

Uploaded to the release as its own asset. It is signed too (decision 1 applies uniformly to every
artifact this job produces, including the SBOM itself — a downloader should be able to verify the
SBOM's authenticity the same way as everything else).

**Emit the provenance subject list.** A final step in this job computes a base64-encoded
`sha256sum`-format digest list covering the three primary artifacts plus the SBOM, and exposes it as
a job `output` (`outputs: hashes: ${{ steps.hash.outputs.hashes }}`) — the documented input contract
`slsa-github-generator`'s reusable workflow expects.

This job's `permissions` block gains `id-token: write` (required for both the cosign OIDC signing
step and, later, the provenance job's own OIDC use) alongside the existing `contents: write`.

### Job 2 (`provenance`, new)

```yaml
  provenance:
    needs: release
    permissions:
      actions: read
      id-token: write
      contents: write
    uses: slsa-framework/slsa-github-generator/.github/workflows/generator_generic_slsa3.yml@<pinned-sha> # vX.Y.Z
    with:
      base64-subjects: ${{ needs.release.outputs.hashes }}
      upload-assets: true
```

This is GitHub's own official reusable workflow, called (not vendored/reimplemented) — it handles its
own signing, transparency-log submission, and release-asset upload for the resulting
`.intoto.jsonl` provenance attestation. The exact version to pin is resolved at implementation time
against the generator's real current release, following this repo's existing
SHA-pin-with-version-comment convention for every other third-party action.

## Verification: document the standard tools, don't reimplement them

`docs/RELEASE.md` gains a new section showing how a downloader verifies what this spec adds, using
the standard external tools (`cosign`, `slsa-verifier`) directly — not a new custom Python verifier.
Rolling a hand-written verifier for cryptographic signatures/provenance would be reinventing exactly
the kind of security-sensitive logic that belongs in a widely-audited, purpose-built tool, not a
repository-local script:

```bash
cosign verify-blob --bundle software-builder-1.4.0.tar.gz.cosign.bundle \
  --certificate-identity-regexp 'https://github.com/luckyrjain/software-builder/.github/workflows/release.yml@.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  software-builder-1.4.0.tar.gz

slsa-verifier verify-artifact software-builder-1.4.0.tar.gz \
  --provenance-path multiple.intoto.jsonl \
  --source-uri github.com/luckyrjain/software-builder \
  --source-tag v1.4.0
```

`scripts/verify_release_bundle.py` (which independently re-derives the existing tarball's
`RELEASE-MANIFEST.json` claims) is untouched — it already does its job for the tarball's own content
integrity; signing and provenance are an orthogonal, additive layer on top, not a replacement for it.

## Testing

- This is CI-workflow YAML plus shell commands invoking external tools — there is no meaningful unit
  test for "does `cosign sign-blob` work," the same honest constraint `sb update`'s and the plugin
  bundle's own release-side design specs already stated for their CI-only changes.
- What CAN be verified without cutting a real release: the workflow YAML parses and its structure is
  correct (two jobs, correct `needs`/`permissions`/`with` wiring) — reviewed by hand and with
  `yaml.safe_load`, the same check the plugin-bundle branch's final review already used for its own
  new step.
- `scripts/check_pinned_actions.py` (existing, already wired into `make lint`) fails closed on any
  unpinned new action reference — this is real, automated enforcement, not just a review checklist
  item.
- Once the user cuts the first real tagged release with this workflow active, a follow-up manual
  verification (not a new coding task) confirms `cosign verify-blob`/`slsa-verifier` actually succeed
  against the real published artifacts — mirroring the exact honesty pattern `sb update`'s design
  spec already used for its own untestable-until-a-real-tag release-side change.

## Explicitly deferred

- SBOM for the main tarball or the plugin bundle (decision 2 — neither has a meaningful dependency
  graph to describe).
- A maintainer-held signing key as a fallback/alternative signing path.
- Extending `scripts/release_contract.yaml`'s schema to enumerate the new signature/SBOM/provenance
  assets — follows the same precedent the sb wheel and plugin bundle already established.
- A custom Python signature/provenance verifier — `cosign`/`slsa-verifier` are the correct tools,
  documented rather than reimplemented.
- SLSA Build Level 4 (hermetic, reproducible builds with two-person review) — Level 3 is what
  `slsa-github-generator`'s generic workflow provides out of the box; Level 4 would require
  additional build-hermeticity work this spec does not scope.

## Self-review

- **Placeholder scan:** no TBD/TODO; the one deliberately-unresolved detail (exact action SHAs to
  pin) is explicitly named as "resolved at implementation time," not glossed over — this repo's own
  `check_pinned_actions.py` makes an unpinned reference a hard CI failure, so it cannot silently ship
  unresolved.
- **Internal consistency:** the "SBOM only for the wheel" scoping is justified by a concrete,
  verified fact (the wheel's `pyproject.toml` has a real dependency; the other two artifacts don't),
  not asserted without basis.
- **Scope check:** one coherent unit (signing + SBOM + provenance, all landing in one workflow change
  plus docs) — no further decomposition needed for a single implementation plan, though the two-job
  restructure is real enough that the implementation plan should treat job-2's wiring as its own
  careful step.
- **Ambiguity check:** "which artifacts get signed" (all three, uniformly) vs. "which gets an SBOM"
  (wheel only) are stated as two explicitly different scopes rather than left to reader inference.
