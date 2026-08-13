# Phase completion gate

**Normative.** Run at end of every phase before updating `{artifact_root}/PROGRESS.md` and root
**`manifest.yaml`**.

## Checklist

```text
Phase: <name>
[ ] Every artifact in phase-outputs.md § <Phase> exists under artifact_root unless explicitly documented otherwise
[ ] manifest.yaml phases.<key>.status = complete (or skipped + skip_reason)
[ ] manifest.yaml artifact/diagram rows updated for this phase
[ ] evidence_summary counters updated
[ ] EXEC_SUMMARY.md § Time & Effort row appended for this phase
[ ] overall_confidence recalculated (when five questions touched)
[ ] python3 scripts/validate_manifest_yaml.py manifest.yaml --workspace-root <root> → exit 0
[ ] P5 FIRST_PASS_COMPLETE: manifest validator runs with --strict --check-content
[ ] P5 FIRST_PASS_COMPLETE: validate_prd.py <artifact_root>/PRD.md → exit 0
[ ] P2b complete: `{map_file}` § Runtime validation exists or map stub links to `E2E_FLOW.md` § Runtime validation
[ ] No required table is empty (UNKNOWN rows allowed with reason)
[ ] Required Mermaid diagrams present or ⚠️ in KNOWN_OMISSIONS.md / UNKNOWNS.md
[ ] Repo classification enum on all in-scope repos (P0+)
[ ] Coverage report printed
[ ] PROGRESS.md + manifest.yaml last_updated synced
```

## manifest.yaml updates (every phase)

1. Set `engagement.last_phase_completed`, `engagement.last_updated`, `engagement.next_action`.
2. Set `phases.<key>.status: complete` and `completed_at` (or `skipped` + `skip_reason`).
3. Flip `artifacts[]` / `diagrams[]` touched this phase → `ok` (or `waived`/`n_a`).
4. Update `five_questions`, `repos`, `runtime_validation`, `evidence_summary`, `overall_confidence`.
5. Run the manifest validator (schema: [manifest-schema.md](manifest-schema.md)).

```bash
python3 <skill>/scripts/validate_manifest_yaml.py "$WORKSPACE_ROOT/manifest.yaml" \
  --workspace-root "$WORKSPACE_ROOT"
```

On **P5** with `FIRST_PASS_COMPLETE`, run both validators. Resolve `ARTIFACT_ROOT` from
`manifest.yaml engagement.artifact_root`; do not assume the PRD lives at workspace root.

```bash
python3 <skill>/scripts/validate_manifest_yaml.py "$WORKSPACE_ROOT/manifest.yaml" \
  --workspace-root "$WORKSPACE_ROOT" --strict --check-content

python3 <skill>/scripts/validate_prd.py \
  "$WORKSPACE_ROOT/$ARTIFACT_ROOT/PRD.md"
```

`validate_prd.py` enforces the P5 requirement contract: functional requirements, business rules, and
NFRs must have `Observed | Inferred | Unknown` status and confidence; every `FR-*`, `BR-*`, and `NFR-*`
must have exactly one traceability row; `Observed` rows must cite evidence.

## Coverage report (required)

```text
Comprehension Phase: <name> complete | Next: <name>
Manifest: phases.<key>=complete | validator ok | schema_version=2
Five questions: Q1 … Q5 statuses | Overall confidence: <band>
Evidence: repos X/Y | files N | runtime edges A/B | unknowns U | omissions O
Phase artifacts: <list> — all present | missing: <list>
Repos: X/Y scanned (by classification: application=N, library=M, …)
Runtime edges: X/Y CONFIRMED (if P2b done)
Section confidence: <lowest> = <band>
Blockers: N in UNKNOWNS.md | Omissions: M in KNOWN_OMISSIONS.md
Top ⚠️: <one line>
```

## Blocking conditions

Do **not** advance phase if:

- `validate_manifest_yaml.py` exits non-zero
- P5 `validate_prd.py` exits non-zero
- Required artifact file missing on disk (when validator checks workspace)
- Implementation matrix uses values outside [implementation-status.md](implementation-status.md)
- Repo `classification` outside [repo-classification.md](repo-classification.md)
- HIGH confidence from README/wiki without code ([evidence-precedence.md](evidence-precedence.md))
