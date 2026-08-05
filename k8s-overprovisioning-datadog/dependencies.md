# External dependencies — k8s-overprovisioning-datadog

## Required — Datadog MCP

Primary data source for COLLECT. Configure per [SETUP.md](SETUP.md).

## Optional — Git MCP

Manifest/Helm path discovery for `delivery_pointer.path` (INV-12). When absent, use `verified: false`
and best-guess path from deployment metadata.

## Skill pin file

[skills-lock.json](skills-lock.json) — empty `skills` object by design (no vendored skills). Bump
`version` when adding optional skill dependencies.
