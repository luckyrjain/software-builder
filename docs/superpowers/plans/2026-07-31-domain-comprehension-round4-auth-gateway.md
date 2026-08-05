# Domain Comprehension Round 4 Auth & Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the `api_tooling.export_mode` gate from P1's Auth & Gateway section, making it unconditional — closing the follow-up round 3's final review flagged but left explicitly out of scope.

**Architecture:** Pure documentation change — remove a conditional from two places in `workflow/phase-1.md`, add the missing `reference/phase-outputs.md` mirror (never existed, conditional or not).

**Tech Stack:** Markdown only. No code, no new tests.

## Global Constraints

- Skill source of truth is `/Users/luckyjain/Projects/ai-skills/domain-comprehension/` inside this worktree (`/Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/`) — use ABSOLUTE paths for every file operation.
- `workflow_version` bump: `workflow/phase-1.md` `1.8` → `1.11`. Must match the changelog row that documents it, not an independent increment. Before setting this value, run `grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md | tail -1` yourself and confirm the last row really is `1.10` — if it isn't, use the actual next integer and say so in your report.
- `reference/phase-outputs.md` gets no version bump — it's a `reference/` file, not a `workflow/*.md` phase file.
- Every markdown edit must keep `scripts/lint-dangling-md-links.sh` clean (run from repo root).

---

### Task 1: Unconditional Auth & Gateway (P1)

**Files:**
- Modify: `domain-comprehension/workflow/phase-1.md`
- Modify: `domain-comprehension/reference/phase-outputs.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by other tasks in this plan (independent).

- [ ] **Step 1: `workflow/phase-1.md` — bump workflow_version**

Edit line 2 from:
```
workflow_version: 1.8
```
to:
```
workflow_version: 1.11
```

- [ ] **Step 2: `workflow/phase-1.md` — remove the conditional from the required-output row**

Find:
```markdown
| Auth & Gateway (when `api_tooling.export_mode` != `never`) | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence | Phase incomplete only when export_mode requires it — otherwise skip, no note needed |
```

Replace with:
```markdown
| Auth & Gateway | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence | Phase incomplete — UNKNOWN allowed with reason |
```

- [ ] **Step 3: `workflow/phase-1.md` — remove the conditional from the section heading**

Find:
```markdown
## Investigation recipes (Auth & Gateway — only when `api_tooling.export_mode` != `never`)
```

Replace with:
```markdown
## Investigation recipes (Auth & Gateway)
```

Do not touch the Redis-OTP grep bullet inside this section (`otp.*redis|redis.*otp|OtpService|OTP_TTL`)
or any other content within it — only the two find/replace edits above.

- [ ] **Step 4: `reference/phase-outputs.md` — add the missing P1 mirror row**

Find:
```markdown
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence |

---

## P2 — Flow
```

Replace with:
```markdown
| Smells (initial) | `RISK_MAP.md` § Architectural smells | Smell, location, severity, evidence |
| Auth & Gateway | `{map_file}` § Per-Repo Deep Dives | Route-prefix → auth requirement, evidence |

---

## P2 — Flow
```

- [ ] **Step 5: Verify**

```bash
grep -n "api_tooling.export_mode" domain-comprehension/workflow/phase-1.md
grep -n "Auth & Gateway" domain-comprehension/workflow/phase-1.md domain-comprehension/reference/phase-outputs.md
```
Expected: first grep returns NO matches (conditional fully removed); second grep shows matches in both
files.

- [ ] **Step 6: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/workflow/phase-1.md domain-comprehension/reference/phase-outputs.md
```
Expected: no output, exit 0.

- [ ] **Step 7: Commit**

```bash
git add domain-comprehension/workflow/phase-1.md domain-comprehension/reference/phase-outputs.md
git commit -m "fix(domain-comprehension): decouple Auth & Gateway capture from api_tooling.export_mode, make it unconditional"
```

---

### Task 2: workflow-changelog.md row + full-suite smoke check

**Files:**
- Modify: `domain-comprehension/reference/workflow-changelog.md`

**Interfaces:**
- Consumes: Task 1.
- Produces: nothing (terminal task).

- [ ] **Step 1: Confirm the last changelog row's version**

```bash
grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md | tail -1
```
Expected: the last row is `1.10`. If it is not, use the actual next integer instead of `1.11` — note the
discrepancy in your report rather than guessing.

- [ ] **Step 2: Add the changelog row**

Find the table's last row (`1.10`) and the `## Versioning rule` heading right after it — insert a new
`1.11` row between them:

```markdown
| 1.11 | 2026-07-31 | phase-1.md, phase-outputs.md | Decoupled Auth & Gateway capture from `api_tooling.export_mode` — now always attempted in P1, UNKNOWN with reason if not discoverable, matching every other artifact's convention (same fix class as round 3's base-URL decoupling) |
```

- [ ] **Step 3: Verify the changelog table stays well-formed**

```bash
grep -n "^| 1\." domain-comprehension/reference/workflow-changelog.md
```
Expected: one row per version, each exactly 4 `|`-delimited columns.

- [ ] **Step 4: Link-check**

```bash
bash scripts/lint-dangling-md-links.sh domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 5: Confirm no version collisions**

```bash
grep -n "workflow_version" domain-comprehension/workflow/*.md
```
Expected: `phase-1.md` shows `1.11`; no other workflow file shows `1.11`.

- [ ] **Step 6: Full-suite regression check**

```bash
cd domain-comprehension && python3 -m pytest tests/ -v
```
Expected: all 45 tests still pass (this plan adds zero code, zero new tests).

- [ ] **Step 7: Template manifest still valid**

```bash
python3 domain-comprehension/scripts/validate_manifest_yaml.py domain-comprehension/templates/manifest.yaml
```
Expected: `ok:`.

- [ ] **Step 8: Repo-wide link check on everything this plan touched**

```bash
bash scripts/lint-dangling-md-links.sh \
  domain-comprehension/workflow/phase-1.md \
  domain-comprehension/reference/phase-outputs.md \
  domain-comprehension/reference/workflow-changelog.md
```
Expected: no output, exit 0.

- [ ] **Step 9: Commit**

```bash
git add domain-comprehension/reference/workflow-changelog.md
git commit -m "docs(domain-comprehension): backfill workflow-changelog.md for Auth & Gateway unconditional change"
```
