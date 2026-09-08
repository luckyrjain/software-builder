# External dependencies — k8s-overprovisioning-datadog

## Evidence sources — capability-dependent

Prefer a read-only Kubernetes MCP for live cluster state and use Datadog per missing capability and
for unique historical/operational telemetry. Either can support a run when it supplies sufficient
evidence for the requested decision. Configure per [SETUP.md](SETUP.md).

## Optional — Git MCP

Manifest/Helm path discovery for `delivery_pointer.path` (INV-12) when Kubernetes MCP cannot expose
the running configuration. A Git-observed or explicitly user-confirmed path uses `verified: true`.
Keep an unconfirmed candidate only on a `DEFERRED` recommendation with `verified: false`; never invent
a best-guess path.

## Skill pin file

[skills-lock.json](skills-lock.json) — empty `skills` object by design (no vendored skills). Bump
`version` when adding optional skill dependencies.
