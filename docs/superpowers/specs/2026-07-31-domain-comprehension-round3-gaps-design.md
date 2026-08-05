# Domain Comprehension — Round 3 Gaps: Validation Annotations + Unconditional Base URLs

**Date:** 2026-07-31
**Skill:** `domain-comprehension`

---

## Problem statement

A third deep re-verification audit (after two prior rounds each found and fixed 3 gaps) found 2 more real
gaps — this time doing a substance-level check, not just a heading-level check:

1. **No fallback path for request/response validation-annotation capture.** `API_CATALOG.md` has no
   field-level schema column at all; `grep -rn '@NotBlank|@Pattern|@Size|@Valid'` returns zero hits
   anywhere in the skill. When no OpenAPI/Swagger spec is committed (common for Spring services validated
   only via Bean Validation), nothing tells the agent to read the DTOs directly.
2. **BFF/gateway base-URL capture is architecturally miscoupled.** `workflow/phase-2.md`'s Deployment graph
   row only populates the Base URLs table "when `api_tooling.export_mode` != `never`" (default `never`) —
   so by default, **zero** deployment/gateway URL evidence is ever captured, even though understanding
   gateway routing topology (BFF vs. direct ingress) is a core comprehension concern independent of wanting
   a Postman export. This was a real design mistake introduced when `api_tooling` shipped: base-URL capture
   should never have been gated behind an unrelated export flag.

---

## Scope

**In:** a narrow validation-annotation grep recipe + fallback note (P0.25), decoupling base-URL capture
from `api_tooling.export_mode` entirely (P2 + `DEPENDENCY_GRAPH.md` template + `reference/phase-outputs.md`
— which, checked while writing this spec, never had a Base URLs mirror at all, conditional or not, making
this also a fourth occurrence of the "reference/phase-outputs.md left un-mirrored" defect class, closed
proactively this time rather than caught by a subsequent review).

**Out:** a full field-level request/response schema table (considered and rejected — see Decision below).

---

## Decision: narrow fix for gap 1, not a new schema table

Considered and rejected: a genuine new per-endpoint field-level schema table in `API_CATALOG.md` (fields,
types, validation, required — matching the prompt's Phase 2 output exactly). Rejected for now as
disproportionate to the specific finding (zero validation-annotation mentions) — the narrow fix (grep
recipe + evidence note, reusing the existing Contract inventory / API catalog structure) closes the actual
gap found without inventing new required-output machinery. A full schema table remains a legitimate future
enhancement if a real engagement run surfaces the need, but isn't justified by this audit alone.

## Decision: base-URL capture becomes fully unconditional

Matches the skill's existing UNKNOWN-over-speculation convention — every other artifact in this skill is
"always attempted, `UNKNOWN` with reason if not discoverable," never gated behind an unrelated feature
flag. `api_tooling`, when enabled, now purely **consumes** this data (already true per
`reference/api-tooling-integration.md`'s existing wording — no changes needed there); it stops being what
**causes** the data to exist.

---

## Task A — Validation-annotation fallback (P0.25)

### `workflow/phase-0-25.md`

Add a fallback note to the existing "### HTTP / REST" recipe subsection — find:

```markdown
### HTTP / REST

```bash
# Find controllers and route definitions
rg -l 'swagger|openapi|@RestController|@RequestMapping|@GetMapping|@PostMapping|router\.' \
  --glob '!test*' --glob '!vendor' --glob '!node_modules' <repo>

# Find committed OpenAPI/Swagger spec files
find <repo> -name 'openapi.yaml' -o -name 'swagger.yaml' -o -name 'openapi.json' 2>/dev/null
```

### gRPC / Proto
```

Replace with:

```markdown
### HTTP / REST

```bash
# Find controllers and route definitions
rg -l 'swagger|openapi|@RestController|@RequestMapping|@GetMapping|@PostMapping|router\.' \
  --glob '!test*' --glob '!vendor' --glob '!node_modules' <repo>

# Find committed OpenAPI/Swagger spec files
find <repo> -name 'openapi.yaml' -o -name 'swagger.yaml' -o -name 'openapi.json' 2>/dev/null
```

**No OpenAPI/Swagger spec found?** Read request/response DTOs directly for validation constraints:

```bash
rg -o '@NotBlank|@NotNull|@Pattern\([^)]*\)|@Size\([^)]*\)|@Valid|@Min\([^)]*\)|@Max\([^)]*\)' \
  --glob '!test*' <repo>/**/model/request/*.java <repo>/**/dto/*Request*.java 2>/dev/null
```

Record findings as evidence notes alongside the Contract inventory row for that endpoint — do not invent a
field-level schema table; cite the DTO class + constraint found.

### gRPC / Proto
```

---

## Task B — Unconditional base-URL capture (P2)

### `workflow/phase-2.md`

Find:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config; when `api_tooling.export_mode` != `never`, also per-env base URL (BFF + direct ingress) | Phase incomplete — UNKNOWN allowed with reason |
```

Replace with:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config, plus per-env base URL (BFF + direct ingress) | Phase incomplete — UNKNOWN allowed with reason |
```

### `templates/DEPENDENCY_GRAPH.md`

Find:
```markdown
### Base URLs (api_tooling)

Populated only when `api_tooling.export_mode` != `never`. Sources: `application*.yml`, Jenkinsfile, K8s
ingress manifests.

| Env | BFF base URL | Direct ingress (debug only) | Evidence |
|-----|--------------|------------------------------|----------|
```

Replace with:
```markdown
### Base URLs

Always populated (UNKNOWN with reason if not discoverable). Sources: `application*.yml`, Jenkinsfile, K8s
ingress manifests.

| Env | BFF base URL | Direct ingress (debug only) | Evidence |
|-----|--------------|------------------------------|----------|
```

### `reference/phase-outputs.md`

The P2 Deployment graph row never had a Base URLs mirror at all (checked directly — it only ever said
"Service → placement from config"), so this is a proactive fix, not a regression. Find:

```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config |
```

Replace with:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config, plus per-env base URL (BFF + direct ingress) |
```

No other file needs changes — `reference/api-tooling-integration.md` already describes Base URLs as
something P5 export *consumes* from P2, not something it causes to exist; no wording there implies the old
conditional.

---

## Changelog

`reference/workflow-changelog.md`'s last row is currently `1.9` (verified at spec-writing time —
implementation plan must re-verify this itself before assuming). This feature's new row is `1.10`, listing:
`phase-0-25.md, phase-2.md, DEPENDENCY_GRAPH.md, phase-outputs.md`. Both bumped workflow files
(`phase-0-25.md`, currently `1.9`; `phase-2.md`, currently `1.6`) get `workflow_version: 1.10` — matching
the changelog row, not an independent per-file increment (this exact discipline has now been verified
holding for two consecutive rounds; keep it holding for a third).

---

## Open items for implementation plan

- None — both tasks are markdown-only, no code, no new tests (same shape as all prior rounds).
