# Assessment metadata footer (squad-map)

Machine-readable YAML emitted at Phase 1 closeout. Normative shared shape:
[review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md) §8.4.

Owner confidence bands: [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md) §2.3 ·
reconciliation: [squad-mapping.md](squad-mapping.md).

## When to emit

Append a fenced ` ```yaml ` block after `SQUAD_MAP.md` is written. Include in chat completion summary.
Optional in the markdown file under **Appendix — machine metadata**.

| Block | When |
|-------|------|
| **Core** (`workspace_root`, `assessment_complete`) | Every complete mapping |
| **`precision`** | Always — repo counts and per-band tallies |
| **`history`** | Re-run when prior `assessment_metadata` on same workspace parseable |
| **`investigation_quality`** | When MCP profile and coverage computable |

`precision.confidence_*` counts are per-row owner bands — not mysql P0/P1 risk tiers.

Omit `history` on first mapping with no prior footer.
