# Domain Comprehension Round 3 Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 2 gaps found by a third deep re-verification audit — validation-annotation fallback (P0.25) and fully unconditional BFF/gateway base-URL capture (P2), decoupled from the `api_tooling.export_mode` flag it was incorrectly gated behind.

**Architecture:** Pure documentation change — one grep-recipe fallback addition, and removing an incorrect conditional from 3 files (the required-output row, the template section, and its normative mirror — closed proactively this time, not caught by a subsequent review).

**Tech Stack:** Markdown only. No code, no new tests.

## Global Constraints

- Skill source of truth is `/Users/luckyjain/Projects/ai-skills/domain-comprehension/` inside this worktree (`/Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/`) — use ABSOLUTE paths for every file operation. A task in an earlier round on this branch misread a file from a stale checkout; do not repeat that.
- `workflow_version` bumps: `workflow/phase-0-25.md` `1.9` → `1.10`, `workflow/phase-2.md` `1.6` → `1.10`. **Both must land on `1.10` to match the changelog row that documents them** — NOT an independent per-file increment. This exact discipline has now held for two consecutive rounds after two earlier rounds got it wrong; keep it holding. Before setting these values, run `grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md | tail -1` yourself and confirm the last row really is `1.9` — if it isn't, use the actual next integer and say so in your report rather than guessing.
- `reference/phase-outputs.md` and `templates/DEPENDENCY_GRAPH.md` get no version bump — neither is a `workflow/*.md` phase file with its own `workflow_version` header.
- Every markdown edit must keep `scripts/lint-dangling-md-links.sh` clean (run from repo root).

---

### Task 1: Validation-annotation fallback (P0.25)

**Files:**
- Modify: `domain-comprehension/workflow/phase-0-25.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: Bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.9
```
to:
```
workflow_version: 1.10
```

- [ ] **Step 2: Add the fallback note to the HTTP / REST recipe**

Find:
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

- [ ] **Step 3: Verify**

```bash
grep -n "No OpenAPI/Swagger spec found" domain-comprehension/workflow/phase-0-25.md
```
Expected: 1 match.

- [ ] **Step 4: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-0-25.md
```
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```bash
git add domain-comprehension/workflow/phase-0-25.md
git commit -m "feat(domain-comprehension): add validation-annotation fallback recipe to P0.25"
```

---

### Task 2: Unconditional base-URL capture (P2)

**Files:**
- Modify: `domain-comprehension/workflow/phase-2.md`
- Modify: `domain-comprehension/templates/DEPENDENCY_GRAPH.md`
- Modify: `domain-comprehension/reference/phase-outputs.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: `workflow/phase-2.md` — bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.6
```
to:
```
workflow_version: 1.10
```

- [ ] **Step 2: `workflow/phase-2.md` — remove the conditional from the Deployment graph row**

Find:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config; when `api_tooling.export_mode` != `never`, also per-env base URL (BFF + direct ingress) | Phase incomplete — UNKNOWN allowed with reason |
```

Replace with:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config, plus per-env base URL (BFF + direct ingress) | Phase incomplete — UNKNOWN allowed with reason |
```

- [ ] **Step 3: `templates/DEPENDENCY_GRAPH.md` — make the Base URLs section unconditional**

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

- [ ] **Step 4: `reference/phase-outputs.md` — mirror the Deployment graph row (proactive fix — this file never had a Base URLs mirror at all, conditional or not)**

Find:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config |
```

Replace with:
```markdown
| Deployment graph | `DEPENDENCY_GRAPH.md` § Deployment | Service → placement from config, plus per-env base URL (BFF + direct ingress) |
```

- [ ] **Step 5: Verify**

```bash
grep -n "Base URLs" domain-comprehension/templates/DEPENDENCY_GRAPH.md
grep -n "per-env base URL" domain-comprehension/workflow/phase-2.md domain-comprehension/reference/phase-outputs.md
grep -n "api_tooling.export_mode" domain-comprehension/workflow/phase-2.md domain-comprehension/templates/DEPENDENCY_GRAPH.md
```
Expected: first two greps show matches in all files; the third grep (checking the old conditional is
gone) should show NO matches in either file.

- [ ] **Step 6: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-2.md domain-comprehension/templates/DEPENDENCY_GRAPH.md domain-comprehension/reference/phase-outputs.md
```
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add domain-comprehension/workflow/phase-2.md domain-comprehension/templates/DEPENDENCY_GRAPH.md domain-comprehension/reference/phase-outputs.md
git commit -m "fix(domain-comprehension): decouple base-URL capture from api_tooling.export_mode, make it unconditional"
```

---

### Task 3: workflow-changelog.md row + full-suite smoke check

**Files:**
- Modify: `domain-comprehension/reference/workflow-changelog.md`

**Interfaces:**
- Consumes: Tasks 1, 2 (must run after both, to list their combined file set accurately).
- Produces: nothing (terminal task).

- [ ] **Step 1: Confirm the last changelog row's version**

```bash
grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md | tail -1
```
Expected: the last row is `1.9`. If it is not, use the actual next integer for the new row (and for Tasks
1/2's `workflow_version` values, if you're re-running those tasks) instead of `1.10` — note the discrepancy
in your report rather than silently adjusting.

- [ ] **Step 2: Add the changelog row**

Find the table's last row (`1.9`) and the `## Versioning rule` heading right after it — insert a new
`1.10` row between them:

```markdown
| 1.10 | 2026-07-31 | phase-0-25.md, phase-2.md, DEPENDENCY_GRAPH.md, phase-outputs.md | Validation-annotation grep fallback for P0.25 when no OpenAPI spec exists; decoupled BFF/gateway base-URL capture from `api_tooling.export_mode` — now always attempted in P2, UNKNOWN with reason if not discoverable, matching every other artifact's convention |
```

- [ ] **Step 3: Verify the changelog table stays well-formed**

```bash
grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md
```
Expected: one row per version, no broken pipe count (each row exactly 4 `|`-delimited columns).

- [ ] **Step 4: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 5: Confirm no version collisions**

```bash
grep -n "workflow_version" domain-comprehension/workflow/*.md
```
Expected: `phase-0-25.md` and `phase-2.md` both show `1.10`; no other workflow file shows `1.10`.

- [ ] **Step 6: Full-suite regression check**

```bash
cd domain-comprehension && python3 -m pytest tests/ -v
```
Expected: all 45 tests still pass (this whole plan adds zero code, zero new tests).

- [ ] **Step 7: Template manifest still valid**

```bash
python3 domain-comprehension/scripts/validate_manifest_yaml.py domain-comprehension/templates/manifest.yaml
```
Expected: `ok:`.

- [ ] **Step 8: Repo-wide link check on everything this plan touched**

```bash
bash scripts/lint-dangling-md-links.sh \
  domain-comprehension/workflow/phase-0-25.md \
  domain-comprehension/workflow/phase-2.md \
  domain-comprehension/templates/DEPENDENCY_GRAPH.md \
  domain-comprehension/reference/phase-outputs.md \
  domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 9: Commit**

```bash
git add domain-comprehension/reference/workflow-changelog.md
git commit -m "docs(domain-comprehension): backfill workflow-changelog.md for validation-fallback/base-url changes"
```
