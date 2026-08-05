# Domain Comprehension Time & Effort Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an always-on "Time & Effort" subsection to `EXEC_SUMMARY.md`, derived from data `domain-comprehension` already collects (phase `completed_at` timestamps, `evidence_summary` counters) — no new state, no code, no `export_mode` flag.

**Architecture:** Pure documentation change — a template stub, one manifest-schema field, and one cross-cutting rule telling the agent to refresh the stub every phase end.

**Tech Stack:** Markdown/YAML only. No Python, no tests (no new code exists to test).

## Global Constraints

- Skill source of truth is `/Users/luckyjain/Projects/ai-skills/domain-comprehension/` inside this worktree (`/Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode/domain-comprehension/`).
- No new `validate_manifest_yaml.py` changes — `model_used` is an extra optional key on `engagement`; the validator's `REQUIRED_ENGAGEMENT` tuple only checks for missing required fields, so this needs no code change. Do not add one.
- No new `export_mode` config field, no new deliverable file — this section lives inside the existing `EXEC_SUMMARY.md` template only.
- Every markdown edit must keep `scripts/lint-dangling-md-links.sh` clean (run from repo root) — this task introduces no new links, so this should be trivially true; confirm anyway.

---

### Task 1: Time & Effort subsection + model_used field + cross-cutting rule

**Files:**
- Modify: `domain-comprehension/templates/EXEC_SUMMARY.md`
- Modify: `domain-comprehension/reference/manifest-schema.md`
- Modify: `domain-comprehension/templates/manifest.yaml`
- Modify: `domain-comprehension/reference/phase-outputs.md`

**Interfaces:**
- Consumes: nothing (first and only task).
- Produces: nothing consumed by other in-flight work — this is a self-contained, all-derived feature.

- [ ] **Step 1: `templates/EXEC_SUMMARY.md` — insert the Time & Effort section**

Find:
```markdown
| Known omissions | 0 | |

## Overall confidence
```

Replace with:
```markdown
| Known omissions | 0 | |

## Time & Effort

**Model:** UNKNOWN

| Phase | Completed | Elapsed since previous phase (wall-clock, includes any RESUME gaps) |
|-------|-----------|------------------------------------------------------------------|

**Size proxy:** 0 repos scanned, 0 files inspected — see Evidence summary above.

## Overall confidence
```

- [ ] **Step 2: `reference/manifest-schema.md` — document `engagement.model_used`**

Find:
```markdown
| `next_action` | one-line string |

## `phases` keys
```

Replace with:
```markdown
| `next_action` | one-line string |
| `model_used` | string \| null — model name if the agent can introspect it, else `null` |

## `phases` keys
```

- [ ] **Step 3: `templates/manifest.yaml` — add the field**

Find:
```yaml
  next_action: "Session 0 — repo census"
```

Replace with:
```yaml
  next_action: "Session 0 — repo census"
  model_used: null
```

- [ ] **Step 4: `reference/phase-outputs.md` — add cross-cutting rule 7**

Find:
```markdown
6. **Evidence summary** — update `manifest.evidence_summary` every phase end.
```

Replace with:
```markdown
6. **Evidence summary** — update `manifest.evidence_summary` every phase end.
7. **Time & Effort** — refresh `EXEC_SUMMARY.md` § Time & Effort every phase end: append/update that
   phase's row from `manifest.phases.<key>.completed_at`, and set `engagement.model_used` at Session 0 if
   knowable (leave `null`/`UNKNOWN` otherwise — never guess).
```

- [ ] **Step 5: Verify**

```bash
cd domain-comprehension
grep -n "Time & Effort" templates/EXEC_SUMMARY.md reference/phase-outputs.md
grep -n "model_used" reference/manifest-schema.md templates/manifest.yaml
python3 -c "import yaml; yaml.safe_load(open('templates/manifest.yaml'))" && echo "manifest.yaml still valid YAML"
python3 -m pytest tests/test_validate_manifest.py -k test_minimal_template_validates -v
```
Expected: `Time & Effort` found in both files; `model_used` found in both files; YAML still parses;
`test_minimal_template_validates` still passes (the new `model_used: null` field is an extra key the
validator doesn't reject — no schema change needed for this to stay green).

- [ ] **Step 6: Link-check**

```bash
cd /Users/luckyjain/Projects/ai-skills/.claude/worktrees/domain-comprehension-add-repo-mode
bash scripts/lint-dangling-md-links.sh domain-comprehension/templates/EXEC_SUMMARY.md domain-comprehension/reference/manifest-schema.md domain-comprehension/reference/phase-outputs.md
```
Expected: no output, exit 0 (`.yaml` files are outside this script's `.md`-only pattern — no need to pass `templates/manifest.yaml`).

- [ ] **Step 7: Full-suite regression check**

```bash
cd domain-comprehension
python3 -m pytest tests/ -v
```
Expected: all tests still pass (no count change — this task adds zero new tests, since it adds zero new code).

- [ ] **Step 8: Commit**

```bash
git add domain-comprehension/templates/EXEC_SUMMARY.md domain-comprehension/reference/manifest-schema.md domain-comprehension/templates/manifest.yaml domain-comprehension/reference/phase-outputs.md
git commit -m "feat(domain-comprehension): add always-on Time & Effort summary to EXEC_SUMMARY.md"
```
