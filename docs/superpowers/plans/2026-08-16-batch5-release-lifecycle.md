# Batch 5 — Release lifecycle implementation plan

## Goal

Complete platform-backlog items 36–39 as the release/distribution lifecycle layer that follows Batch 4 host portability. Preserve the existing release workflow and packaging entry points, but make their guarantees executable and fail-closed.

## Scope

1. **Release/version contract** — one machine-readable policy validates repository semantic version, tag shape, release artifact names, compatibility policy, and required provenance fields.
2. **Reproducible release bundle** — release inputs come only from Git-tracked regular files; archives use normalized ordering, timestamps, ownership and modes; untracked files, symlinks, caches, build output and credential-like material cannot enter a release.
3. **Compatibility + provenance manifest** — each release contains a machine-readable manifest with distribution version, exact source SHA, registry/host contract versions, supported hosts, skill versions, and per-file SHA-256 hashes.
4. **Independent release verification** — a verifier extracts a release artifact into an isolated directory and validates archive safety, manifest/file hashes, provenance, compatibility metadata, and portable references before GitHub upload. The release workflow must run this gate.

## TDD slices

### Slice 1 — Contract and deterministic inputs

- Add failing tests for invalid/missing repository VERSION and release-contract shape.
- Add failing tests proving arbitrary untracked files and tracked symlinks cannot enter release inputs.
- Add failing tests proving two builds from the same Git tree are byte-identical.

### Slice 2 — Release manifest

- Add failing tests for required provenance fields and exact file-hash coverage.
- Generate `RELEASE-MANIFEST.json` inside the archive from canonical registry/host metadata.
- Keep the existing outer archive checksum and per-file checksum assets for compatibility.

### Slice 3 — Independent verifier

- Add failing tests for path traversal, unsafe tar members, missing/extra files, hash mismatch, bad source/version provenance and broken portable references.
- Implement `scripts/verify_release_bundle.py` with a fail-closed CLI.

### Slice 4 — CI/release integration

- Add a repository contract validator and wire it into normal lint/registry validation.
- Make `.github/workflows/release.yml` run release-contract and built-bundle verification before upload.
- Update `docs/RELEASE.md` to document compatibility, verification, upgrade and rollback expectations.

## Exit gate

- Full CI/security suite green on the exact final head.
- Release bundle is reproducible from the same tracked Git tree.
- Release manifest has exact source/version/host/skill/file provenance.
- A tampered or unsafe bundle is rejected before publish.
- Two consecutive independent deep code reviews return zero actionable findings on one unchanged head.
