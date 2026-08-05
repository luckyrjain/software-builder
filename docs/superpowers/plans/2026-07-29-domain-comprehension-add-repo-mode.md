# Domain Comprehension `ADD_REPO` Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `ADD_REPO` delivery_mode to the `domain-comprehension` skill so one new repo can be onboarded into an *existing* engagement's shared domain map, with a conflict gate before merging its claims into shared deliverables.

**Architecture:** Pure documentation change to the skill's workflow/reference/template files (new delivery_mode described exactly like `DELTA`/`COMPLIANCE_RETROFIT` already are) plus one new content-validation check in the existing Python manifest validator (`scripts/validate_manifest_yaml.py`) that enforces the conflict gate.

**Tech Stack:** Markdown (skill instructions), Python 3 + PyYAML + pytest (`scripts/validate_manifest_yaml.py`, `tests/test_validate_manifest.py`).

## Global Constraints

- Skill source of truth is `/Users/luckyjain/Projects/ai-skills/domain-comprehension/` (git-tracked project repo) — **not** `~/.claude/skills/domain-comprehension/` (a separately-installed runtime copy; do not edit it, it's out of scope for this plan).
- No manifest **schema** field/enum changes. Reuse existing `status: in_progress` for "phase not yet complete due to open conflict" — do not introduce a new phase-status enum value.
- Follow the spec exactly: `docs/superpowers/specs/2026-07-29-domain-comprehension-add-repo-mode-design.md`.
- Every markdown edit must keep `scripts/lint-dangling-md-links.sh` clean (run from repo root) — no dangling relative links or anchors introduced.
- `workflow_version` in `workflow/inputs.md` bumps `1.4` → `1.5` (this plan touches its procedure).

---

### Task 1: `workflow/inputs.md` — `ADD_REPO` delivery mode + procedure

**Files:**
- Modify: `domain-comprehension/workflow/inputs.md`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: the `ADD_REPO` delivery_mode name and its procedure text — Tasks 3 and 4 reference this mode by name (`ADD_REPO`) and by the phrase "owning phase (`p0`/`p1`) at `status: in_progress`"; keep that exact phrasing since Task 4's validator error message quotes it.

- [ ] **Step 1: Bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.4
```
to:
```
workflow_version: 1.5
```

- [ ] **Step 2: Add `new_repo_path` input field**

In the input table (after the `memory_bank.export_mode` row, i.e. immediately before the `## Workspace layout detection` heading), add:

```markdown
| `new_repo_path` | Only for `ADD_REPO` | Ask if ambiguous |
```

So the table reads (last three rows):
```markdown
| `domain_pack` | No | e.g. `fintech-payout` — see [domain-packs](../reference/domain-packs/README.md) |
| `memory_bank.export_mode` | No | From `domain-config.yaml`; override in user message (`never` \| `optional` \| `p5`) |
| `new_repo_path` | Only for `ADD_REPO` | Ask if ambiguous |
```

- [ ] **Step 3: Add `ADD_REPO` row to the Delivery mode table**

Find:
```markdown
| `DELTA` | Re-run phases for repos whose HEAD SHA changed since last manifest |
| `COMPLIANCE_RETROFIT` | Normalize split deliverables + `manifest.yaml` from an existing first pass **without** re-analyzing code |
```

Replace with:
```markdown
| `DELTA` | Re-run phases for repos whose HEAD SHA changed since last manifest |
| `ADD_REPO` | Onboard one repo not currently in `manifest.repos[]` into an existing engagement; full-rigor P0–P1 for that repo, then re-run downstream phases per the DELTA affected-phases rules, gated by a merge-conflict check |
| `COMPLIANCE_RETROFIT` | Normalize split deliverables + `manifest.yaml` from an existing first pass **without** re-analyzing code |
```

- [ ] **Step 4: Insert the `ADD_REPO` procedure section**

Insert a new section immediately after the end of `### DELTA mode — procedure` (its last line is `\`engagement.last_updated\` and \`engagement.next_action\`.`) and before the `## Required outputs` heading:

```markdown
### ADD_REPO mode — procedure

Requires `manifest.yaml` at `workspace_root` with `schema_version: 2` and `engagement.status` of
`IN_PROGRESS` or `FIRST_PASS_COMPLETE`. `new_repo_path` must resolve to a repo **not** present in
`manifest.repos[]` (match by `name`) — if it is present, stop and tell the user to use `DELTA` instead.

1. Classify the new repo ([repo-classification.md](../reference/repo-classification.md)), assign
   provisional tier.
2. Add a `manifest.repos[]` entry: `inventory: pending`, `understand: pending`, `deep_dive: pending`.
3. Run, scoped to the new repo only, at the same evidence/confidence bar as `FULL`:
   - P0 (inventory) — append repo census row, tech stack, config surface, repo relationships
   - P0.25 (contracts) — append this repo's producer/consumer rows to `API_CATALOG.md` /
     `EVENT_CATALOG.md`
   - P0.5 (mechanical) — run `/understand --full` for the new repo, merge into the existing
     `.understand-anything/domain-graph.json` via `/understand-domain` (do not regenerate other repos'
     graphs)
   - P1 (deep dive) — per-repo deep dive subsection, ownership card, initial smells
   - Session 0b squad enrichment — append one row to `SQUAD_MAP.md` for the new repo only
4. **Merge gate.** Before writing any P0/P1 row into a shared deliverable (`BOUNDED_CONTEXTS.md`,
   `DATA_OWNERSHIP.md`, `API_CATALOG.md`, `EVENT_CATALOG.md`), check the new repo's claim against
   existing rows for the same entity/context/path:
   - **No overlap** → append normally.
   - **Overlap** (two repos both claim authoritative ownership of a table; a bounded context gains a
     repo that contradicts its existing definition; an API path has a different producer than already
     recorded) → do **not** merge that row. Instead:
     - Add a row to `RISK_MAP.md` § Merge Conflicts with both claims + evidence + confidence,
       `Status: open`
     - Add the same conflict to `UNKNOWNS.md`
     - Leave the owning phase (`p0` or `p1`) at `status: in_progress` in `manifest.yaml` — do **not**
       mark it `complete` while any `RISK_MAP.md` § Merge Conflicts row is `Status: open`
     - **Stop.** Report the conflict to the user; do not proceed to step 5 for the affected deliverable
       until it's resolved
5. Once new-repo P0–P1 merge is clean (no open conflicts, or the user explicitly accepts leaving them
   open), determine downstream re-synthesis using the **DELTA mode affected-phases rules above**,
   treating the new repo as the changed set of one:
   - P2 reruns if new repo is Tier 0/1
   - P2b reruns if P2 reran and Datadog ✅
   - P3 reruns if new repo is Tier 0/1
   - P3b reruns if P3 reran
   - P4, P5 **always** rerun
6. Run `validate_manifest_yaml.py --workspace-root <workspace_root> --check-content`; update
   `engagement.last_updated` and `engagement.next_action`.

**Do not:** re-run P0–P1 for repos already in `manifest.repos[]` (that's `DELTA`'s job if their SHA
changed); regenerate other repos' `/understand` graphs, only merge the new one in.

**Required outputs:**

| Output | Location | Required fields |
|--------|----------|-----------------|
| New repo entry | `manifest.repos[]` | name, branch, sha, tier, classification |
| Merge conflicts (if any) | `RISK_MAP.md` § Merge Conflicts | Both claims, evidence, confidence, status |
| Re-synthesized exec summary | `EXEC_SUMMARY.md` | Five questions + overall confidence recomputed including new repo |
```

- [ ] **Step 5: Verify with grep**

Run:
```bash
grep -n "ADD_REPO" domain-comprehension/workflow/inputs.md
```
Expected: matches at the input-field table, delivery-mode table, and the new `### ADD_REPO mode — procedure` heading (at least 4 lines).

- [ ] **Step 6: Link-check the file**

Run:
```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/inputs.md
```
Expected: no output, exit code 0 (the new `../reference/repo-classification.md` link must resolve — confirm the target file exists first: `test -f domain-comprehension/reference/repo-classification.md && echo exists`).

- [ ] **Step 7: Commit**

```bash
git add domain-comprehension/workflow/inputs.md
git commit -m "feat(domain-comprehension): add ADD_REPO delivery mode procedure"
```

---

### Task 2: `templates/RISK_MAP.md` — Merge Conflicts section

**Files:**
- Modify: `domain-comprehension/templates/RISK_MAP.md`

**Interfaces:**
- Consumes: nothing new
- Produces: the `## Merge Conflicts (ADD_REPO mode)` heading text — Task 4's validator matches on this heading (case-insensitively, matching on `"## merge conflicts"` prefix), so the heading must start with exactly `## Merge Conflicts`.

- [ ] **Step 1: Append the new section**

The file currently ends with:
```markdown
## Change risk

| Repo / context | Risk | Fan-out | Runtime critical? | Test signal | Owner clarity | Evidence |
|----------------|------|---------|-------------------|-------------|---------------|----------|
```

Append, with one blank line separating it from the existing content:

```markdown

## Merge Conflicts (ADD_REPO mode)

| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Status |
|----------|-----------------|-----------|----------------------|----------------------|-----------------|--------|

`Status` values: `open` (blocked, awaiting resolution) \| `resolved` (note which claim won and why, in a
follow-up row or by editing in place) \| `accepted-both` (user explicitly chose to keep both, e.g.
legitimate dual-write).
```

- [ ] **Step 2: Verify**

```bash
grep -n "^## Merge Conflicts" domain-comprehension/templates/RISK_MAP.md
tail -10 domain-comprehension/templates/RISK_MAP.md
```
Expected: heading found; tail shows the new table + Status legend as the last lines of the file.

- [ ] **Step 3: Commit**

```bash
git add domain-comprehension/templates/RISK_MAP.md
git commit -m "feat(domain-comprehension): add Merge Conflicts section to RISK_MAP template"
```

---

### Task 3: Cross-references — `manifest-schema.md`, `SKILL.md`, `phase-index.md`

**Files:**
- Modify: `domain-comprehension/reference/manifest-schema.md:110-115`
- Modify: `domain-comprehension/SKILL.md:83-90,152-156`
- Modify: `domain-comprehension/reference/phase-index.md:24-31`

**Interfaces:**
- Consumes: `ADD_REPO` name from Task 1, `RISK_MAP.md` § Merge Conflicts heading from Task 2.
- Produces: nothing new consumed by later tasks — pure discoverability/reference updates.

- [ ] **Step 1: `manifest-schema.md` — Agent update rules**

Find (current lines 110–115):
```markdown
## Agent update rules

1. **Session 0** — copy [templates/manifest.yaml](../templates/manifest.yaml); set `engagement.*`, all artifacts `stub`
2. **End of phase** — phases, artifacts, diagrams, `evidence_summary`, `overall_confidence`; run validator
3. **Skip phase** — `skipped` + `skip_reason`; optional artifacts `n_a` or `waived`
4. **FIRST_PASS_COMPLETE** — validator `--strict`
```

Replace with:
```markdown
## Agent update rules

1. **Session 0** — copy [templates/manifest.yaml](../templates/manifest.yaml); set `engagement.*`, all artifacts `stub`
2. **End of phase** — phases, artifacts, diagrams, `evidence_summary`, `overall_confidence`; run validator
3. **Skip phase** — `skipped` + `skip_reason`; optional artifacts `n_a` or `waived`
4. **FIRST_PASS_COMPLETE** — validator `--strict`
5. **`ADD_REPO`** — add new `repos[]` entry at start; on merge conflict leave the owning phase at
   `status: in_progress` (do not mark `complete` while `RISK_MAP.md` § Merge Conflicts has an `open`
   row); run validator with `--check-content` same as end-of-phase
```

- [ ] **Step 2: `SKILL.md` — deliverables table**

Find:
```markdown
| **DELTA** | Changed files only + updated `manifest.yaml` + `PROGRESS.md` | Unchanged deliverables |
| **COMPLIANCE_RETROFIT** | `manifest.yaml`, normalize existing artifacts to schema | Do not re-analyze code |
```

Replace with:
```markdown
| **DELTA** | Changed files only + updated `manifest.yaml` + `PROGRESS.md` | Unchanged deliverables |
| **ADD_REPO** | New repo's P0–P1 outputs merged (or conflict-flagged) into existing split deliverables; re-run `EXEC_SUMMARY.md`, `RISK_MAP.md`, and any phase downstream per the DELTA affected-phases table | `E2E_FLOW.md` update only if P2 reran |
| **COMPLIANCE_RETROFIT** | `manifest.yaml`, normalize existing artifacts to schema | Do not re-analyze code |
```

- [ ] **Step 3: `SKILL.md` — Begin section delivery_mode list**

Find:
```markdown
1. [workflow/inputs.md](workflow/inputs.md) — set `delivery_mode` (`FULL` \| `RESUME` \| `DELTA` \| `COMPLIANCE_RETROFIT`)
```

Replace with:
```markdown
1. [workflow/inputs.md](workflow/inputs.md) — set `delivery_mode` (`FULL` \| `RESUME` \| `DELTA` \| `ADD_REPO` \| `COMPLIANCE_RETROFIT`)
```

- [ ] **Step 4: `phase-index.md` — Quick paths table**

Find:
```markdown
| Resume multi-session | Inputs → read `PROGRESS.md` → continue from Next action |
| Mechanical graphs only | Session 0 → P0.5 (requires prior inventory or seed list) |
```

Replace with:
```markdown
| Resume multi-session | Inputs → read `PROGRESS.md` → continue from Next action |
| Mechanical graphs only | Session 0 → P0.5 (requires prior inventory or seed list) |
| Onboard one new repo into existing map | Inputs (`ADD_REPO`) → P0/P0.25/P0.5/P1 for new repo → merge gate → affected downstream phases per DELTA table |
```

- [ ] **Step 5: Verify**

```bash
grep -n "ADD_REPO" domain-comprehension/reference/manifest-schema.md domain-comprehension/SKILL.md domain-comprehension/reference/phase-index.md
```
Expected: at least one match per file (manifest-schema.md: rule 5; SKILL.md: table row + Begin line; phase-index.md: Quick paths row).

- [ ] **Step 6: Link-check all three**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/manifest-schema.md domain-comprehension/SKILL.md domain-comprehension/reference/phase-index.md
```
Expected: no output, exit code 0.

- [ ] **Step 7: Commit**

```bash
git add domain-comprehension/reference/manifest-schema.md domain-comprehension/SKILL.md domain-comprehension/reference/phase-index.md
git commit -m "docs(domain-comprehension): cross-reference ADD_REPO mode from SKILL.md, manifest-schema.md, phase-index.md"
```

---

### Task 4: Validator — merge-conflict completion gate

**Files:**
- Modify: `domain-comprehension/scripts/validate_manifest_yaml.py`
- Modify: `domain-comprehension/tests/test_validate_manifest.py`

**Interfaces:**
- Consumes: `RISK_MAP.md` § Merge Conflicts heading text (`"## Merge Conflicts"` prefix, case-insensitive) from Task 2; `phases.p0`/`phases.p1` status from the existing manifest schema.
- Produces: `_validate_merge_conflicts_gate(workspace_root: Path, *, phases: dict[str, Any] | None) -> list[str]`, wired into `validate_manifest(..., check_content=True)` alongside the existing `_validate_p2b_runtime_gate` call. No other task depends on this function directly (it's the terminal enforcement task).

- [ ] **Step 1: Write the failing tests**

Append to `domain-comprehension/tests/test_validate_manifest.py` (after the last existing test,
`test_check_content_p2b_e2e_supplement_with_link`):

```python
def test_check_content_merge_conflict_open_blocks_p0_p1_complete(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    data["phases"]["p1"]["status"] = "complete"
    data["phases"]["p1"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | open |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert any("phases.p0 must not be complete" in e for e in errors)
    assert any("phases.p1 must not be complete" in e for e in errors)


def test_check_content_merge_conflict_resolved_allows_complete(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    (tmp_path / "RISK_MAP.md").write_text(
        "## Merge Conflicts (ADD_REPO mode)\n\n"
        "| New repo | Existing claim | New claim | Entity/Context/Path | Evidence (existing) | Evidence (new) | Status |\n"
        "|----------|-----------------|-----------|----------------------|----------------------|-----------------|--------|\n"
        "| svc-b | svc-a owns `users` table | svc-b owns `users` table | users table | svc-a/Repo.java:12 | svc-b/Repo.java:9 | resolved |\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("Merge Conflicts" in e for e in errors)


def test_check_content_no_risk_map_skips_merge_conflicts_gate(tmp_path: Path) -> None:
    data = _minimal_manifest()
    data["phases"]["p0"]["status"] = "complete"
    data["phases"]["p0"]["completed_at"] = "2026-07-29T00:00:00Z"
    (tmp_path / "EXEC_SUMMARY.md").write_text(
        "## Evidence summary\n## Engineering Leader Summary\n## Section confidences\n",
        encoding="utf-8",
    )
    errors = validate_manifest(data, workspace_root=tmp_path, check_content=True)
    assert not any("Merge Conflicts" in e for e in errors)
```

- [ ] **Step 2: Run the new tests to verify they fail**

```bash
cd domain-comprehension
python3 -m pytest tests/test_validate_manifest.py -k merge_conflict -v
```
Expected: `test_check_content_merge_conflict_open_blocks_p0_p1_complete` FAILS (no error raised, `_validate_merge_conflicts_gate` doesn't exist yet, gate is a no-op); the other two pass trivially (they assert absence of an error) — that's fine, they're not meant to fail red, only the positive-gate test must fail here. Confirm by reading the failure: `AssertionError: assert False` on the `"phases.p0 must not be complete"` line.

- [ ] **Step 3: Implement `_validate_merge_conflicts_gate`**

In `domain-comprehension/scripts/validate_manifest_yaml.py`, add a new constant near the other heading
constants (after `E2E_FLOW_RUNTIME_HEADING = "runtime validation"`):

```python
MERGE_CONFLICTS_HEADING = "## merge conflicts"
```

Add the function immediately after `_validate_p2b_runtime_gate` (before `def validate_manifest(`):

```python
def _validate_merge_conflicts_gate(
    workspace_root: Path,
    *,
    phases: dict[str, Any] | None,
) -> list[str]:
    errors: list[str] = []
    risk_map_path = workspace_root / "RISK_MAP.md"
    if not risk_map_path.is_file():
        return errors
    try:
        text = risk_map_path.read_text(encoding="utf-8")
    except OSError:
        return errors

    in_section = False
    has_open_conflict = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped.lower().startswith(MERGE_CONFLICTS_HEADING)
            continue
        if in_section and stripped.startswith("|") and "---" not in stripped:
            cells = [c.strip().lower() for c in stripped.strip("|").split("|")]
            if cells and cells[-1] == "open":
                has_open_conflict = True

    if not has_open_conflict or not isinstance(phases, dict):
        return errors

    for key in ("p0", "p1"):
        entry = phases.get(key)
        if isinstance(entry, dict) and entry.get("status") == "complete":
            errors.append(
                f"check-content: RISK_MAP.md has an open Merge Conflicts row — phases.{key} must not be complete"
            )
    return errors
```

Wire it into `validate_manifest`'s `check_content` block — find:
```python
            if check_content:
                errors.extend(
                    _validate_exec_summary_content(workspace_root / "EXEC_SUMMARY.md")
                )
                errors.extend(
                    _validate_p2b_runtime_gate(
                        workspace_root,
                        map_file=map_file,
                        phases=phases if isinstance(phases, dict) else None,
                        runtime_validation=runtime if isinstance(runtime, dict) else None,
                    )
                )
```

Replace with:
```python
            if check_content:
                errors.extend(
                    _validate_exec_summary_content(workspace_root / "EXEC_SUMMARY.md")
                )
                errors.extend(
                    _validate_p2b_runtime_gate(
                        workspace_root,
                        map_file=map_file,
                        phases=phases if isinstance(phases, dict) else None,
                        runtime_validation=runtime if isinstance(runtime, dict) else None,
                    )
                )
                errors.extend(
                    _validate_merge_conflicts_gate(
                        workspace_root,
                        phases=phases if isinstance(phases, dict) else None,
                    )
                )
```

Also update the `--check-content` CLI help string to mention the new gate — find:
```python
        help="Verify EXEC_SUMMARY.md sections and P2b runtime validation gate (requires --workspace-root)",
```
Replace with:
```python
        help="Verify EXEC_SUMMARY.md sections, P2b runtime validation gate, and RISK_MAP.md merge-conflicts gate (requires --workspace-root)",
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd domain-comprehension
python3 -m pytest tests/test_validate_manifest.py -k merge_conflict -v
```
Expected: all 3 new tests PASS.

- [ ] **Step 5: Run the full existing test suite to check for regressions**

```bash
cd domain-comprehension
python3 -m pytest tests/test_validate_manifest.py -v
```
Expected: all tests PASS (the 9 pre-existing + 3 new = 12 total), no regressions from the new gate touching unrelated fixtures (pre-existing tests never write `RISK_MAP.md`, so `_validate_merge_conflicts_gate` no-ops for them via the `is_file()` check).

- [ ] **Step 6: Commit**

```bash
git add domain-comprehension/scripts/validate_manifest_yaml.py domain-comprehension/tests/test_validate_manifest.py
git commit -m "feat(domain-comprehension): validator gate blocking p0/p1 complete while a RISK_MAP merge conflict is open"
```

---

### Task 5: Full-suite smoke check

**Files:** none modified — verification only.

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: nothing (terminal task).

- [ ] **Step 1: Run the complete domain-comprehension test suite**

```bash
cd domain-comprehension
python3 -m pytest tests/ -v
```
Expected: all tests pass (includes `test_validate_manifest.py` and `test_validate_sub_agent_merge.py`).

- [ ] **Step 2: Validate the template manifest itself still passes**

```bash
cd domain-comprehension
python3 scripts/validate_manifest_yaml.py templates/manifest.yaml
```
Expected: `ok: templates/manifest.yaml`.

- [ ] **Step 3: Repo-wide dangling-link check on every file this plan touched**

```bash
cd /Users/luckyjain/Projects/ai-skills
bash scripts/lint-dangling-md-links.sh \
  domain-comprehension/workflow/inputs.md \
  domain-comprehension/templates/RISK_MAP.md \
  domain-comprehension/reference/manifest-schema.md \
  domain-comprehension/SKILL.md \
  domain-comprehension/reference/phase-index.md
```
Expected: no output, exit code 0.

- [ ] **Step 4: Confirm no unintended files changed**

```bash
git status --short domain-comprehension/
```
Expected: clean (everything from this plan already committed in Tasks 1–4; only pre-existing unrelated
modifications from before this plan started, if any, remain — do not touch those).

No commit for this task — it's verification-only.
