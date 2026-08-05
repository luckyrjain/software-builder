# Assessment metadata footer (domain-comprehension)

Machine-readable YAML emitted at P5 closeout. Normative shared shape:
[review-metadata-schema.md](../../docs/skill-framework/shared/review-metadata-schema.md) §8.3.

Confidence bands: [confidence-bands.md](../../docs/skill-framework/shared/confidence-bands.md) §2.1 ·
rubric: [confidence-rubric.md](confidence-rubric.md).

## When to emit

Append a fenced ` ```yaml ` block under **Appendix — machine metadata** after final `EXEC_SUMMARY.md`
delivery. Include in chat when delivering the full engagement. **Strip** from executive-only paste blocks.

| Block | When |
|-------|------|
| **Core** (`domain`, `workspace_root`, `overall_confidence`, `delivery_mode`) | Every complete P5 |
| **`history`** | Re-run on same domain/workspace when prior footer parseable |
| **`precision`** | Every complete engagement with repo census |
| **`investigation_quality`** | When computable; omit on partial/stopped runs |

`overall_confidence` MUST match `EXEC_SUMMARY.md` § Overall confidence (minimum propagation rule).

Omit `history` on first engagement with no prior footer.
