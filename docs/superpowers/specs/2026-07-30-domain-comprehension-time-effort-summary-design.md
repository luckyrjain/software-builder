# Domain Comprehension — Time & Effort Summary

**Date:** 2026-07-30
**Skill:** `domain-comprehension`

---

## Problem statement

The org's `Extract Service Knowledge Base` prompt has a Phase 10 cost-analysis pass (time, tokens, cost,
make-it-work overhead) logged per run to an external tracker. `domain-comprehension` has no equivalent —
after `ADD_REPO` (single-repo onboarding) and `api_tooling` (runnable Postman/curl export) closed the other
two gaps identified against that prompt, this is the last one.

Full parity isn't feasible or desirable: token counts and dollar cost generally aren't introspectable by
the agent mid-session (harness-dependent), and the prompt's version is written to an org-specific external
tracker (`cost_analysis/COST_EVAL_TRACKER.xlsx`) this skill has no equivalent of and shouldn't invent one
for. What **is** free: every phase already writes a `completed_at` timestamp to `manifest.yaml` — the
elapsed time between phases is sitting in data the skill already collects and has never surfaced.

---

## Scope

**In:** a "Time & Effort" subsection in `EXEC_SUMMARY.md`, computed from existing `manifest.yaml` phase
timestamps + existing `evidence_summary` counters, refreshed every phase end. One new optional
`engagement.model_used` field.

**Out:** token counts, dollar cost, an external tracker integration, a new `export_mode` config flag, a new
dedicated deliverable file. This is deliberately lighter machinery than the `memory_bank`/`api_tooling`
P5-export pattern — always-on, not optional, because it costs nothing to compute (pure derivation from data
already being written) and every engagement benefits from seeing where its time went, not just ones that
opted in.

---

## Decision: fold into `EXEC_SUMMARY.md`, not a new export

Considered and rejected: a `time_tracking.export_mode: never|optional|p5` flag mirroring the two precedents.
Rejected because unlike Memory Bank / `api_tooling` (genuinely optional, non-trivial generated artifacts
someone has to ask for), this section has zero marginal cost to populate — the underlying timestamps are
already mandatory (`phases.*.completed_at` is validator-enforced whenever a phase is `complete`) — and
gating it behind a flag would just mean most engagements never see it for no reason. YAGNI cuts the other
way here: don't add a flag when "always on" is free and strictly more useful.

---

## Data model — no new state to collect

**Per-phase elapsed time:** computed at render time, not stored. Walk `phases` in canonical order
(`session_0, session_0b, p0, p0_25, p0_5, p1, p2, p2b, p3, p3b, p4, p5`), skip any phase with
`status: skipped` (no `completed_at`), and for each phase with `status: complete`, elapsed = its
`completed_at` minus the previous non-skipped completed phase's `completed_at`. First phase's elapsed is
`completed_at` minus `engagement.created_at` if such a field existed — it doesn't, so the first phase's row
reads "—" (no prior anchor) rather than a fabricated duration.

**Caveat, stated explicitly in the rendered section, not left implicit:** this is wall-clock time between
phase completions, not active-work time — a `RESUME` run that picks back up three days later will show a
multi-day "elapsed" for whatever phase happens to complete next. Label the column
"Elapsed since previous phase (wall-clock, includes any RESUME gaps)", not "Time spent."

**Size proxy (not cost):** reuse `evidence_summary.repos_scanned` and `evidence_summary.files_inspected` —
already-collected counters — displayed alongside the time table for context ("12 repos, 340 files
inspected"). No new counters.

**One new optional field:** `engagement.model_used` (string, nullable, default `null`) — set at Session 0
if the agent can identify its own model name in that harness (e.g. from system/session context); otherwise
left `null` and rendered as `UNKNOWN`. This is the only new persisted state in this whole feature.

---

## Section 1 — `templates/EXEC_SUMMARY.md`

Insert a new section immediately after the existing "## Evidence summary" table (before "## Overall
confidence"):

```markdown
## Time & Effort

**Model:** UNKNOWN

| Phase | Completed | Elapsed since previous phase (wall-clock, includes any RESUME gaps) |
|-------|-----------|------------------------------------------------------------------|

**Size proxy:** 0 repos scanned, 0 files inspected — see Evidence summary above.
```

The `**Model:**` line and the table body are populated/refreshed from `manifest.yaml` every phase end (see
Section 3 for the rule). The table has no fixed row count — one row per completed phase, appended/refreshed
as phases complete; a phase's row is only written once that phase reaches `status: complete`.

---

## Section 2 — `reference/manifest-schema.md` + `templates/manifest.yaml`

### `reference/manifest-schema.md`

In the `## \`engagement\`` field table, add one row after `next_action`:

```markdown
| `model_used` | string \| null — model name if the agent can introspect it, else `null` |
```

### `templates/manifest.yaml`

In the `engagement:` block, add:

```yaml
  model_used: null
```

No validator changes needed — `model_used` is an extra optional key on an already-permissive `engagement`
object; `validate_manifest_yaml.py`'s `REQUIRED_ENGAGEMENT` tuple only checks for missing *required* keys,
it does not reject unlisted ones, so this field needs no code change to pass validation either present or
absent.

---

## Section 3 — `reference/phase-outputs.md` — one new cross-cutting rule

Find the existing cross-cutting rule 6:

```markdown
6. **Evidence summary** — update `manifest.evidence_summary` every phase end.
```

Add rule 7 immediately after it:

```markdown
7. **Time & Effort** — refresh `EXEC_SUMMARY.md` § Time & Effort every phase end: append/update that
   phase's row from `manifest.phases.<key>.completed_at`, and set `engagement.model_used` at Session 0 if
   knowable (leave `null`/`UNKNOWN` otherwise — never guess).
```

This single rule covers all 12 phases the same way rule 6 already covers `evidence_summary` — no per-phase
workflow file needs its own edit, matching the existing precedent exactly.

---

## Open items for implementation plan

- None — this feature has no code component. All three file edits are mechanical (template stub, one
  schema table row, one cross-cutting rule sentence) and require no new tests, since there's no new
  validator logic and no new script.
