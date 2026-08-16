# Release lifecycle contract

This document is the normative human-readable companion to the Batch 5 release/distribution contract.
The machine-readable policy is `scripts/registry/release_contracts.yaml`.

A release must be derived from one immutable Git revision. Release packaging may consume only tracked,
regular files from that revision; arbitrary working-tree additions and symlinks are never release inputs.
The same revision and policy must produce a byte-identical archive.

Every release archive carries `RELEASE-MANIFEST.json` with the distribution version, exact source SHA,
registry and host-contract schema versions, supported-host metadata, registered skill versions, and a
SHA-256 for every packaged file other than the manifest itself. The manifest is evidence, not a claim:
an independent verifier recomputes these values from the extracted artifact before publication.

Release verification fails closed on unsafe archive paths or member types, missing/extra files, hash
mismatches, malformed provenance, and broken local package references. GitHub release publication must
run the repository release-contract validator and the built-artifact verifier before upload.

Compatibility follows semantic versioning. Patch releases preserve machine-readable schemas and runtime
contracts; minor releases may add backwards-compatible skills, capabilities, hosts, fields, or aliases;
major releases are required for incompatible registry, packaging, handoff, authorization, or runtime
contract changes. Migration/deprecation guidance belongs in `CHANGELOG.md` and `docs/RELEASE.md`.
