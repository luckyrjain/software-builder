# ONBOARDING_TOUR.md format

**Normative.** The exact structure [workflow/run-tour.md](../workflow/run-tour.md) § 4 must produce.
Written to `tour_output_dir` (default `{workspace_root}/../onboarding-tours/<slug>/`), **outside**
individual source repos — alongside links into domain-comprehension's workspace-level deliverables at
`workspace_root`, not instead of them.

## Structure (order fixed)

```markdown
# Onboarding tour — <new_hire.name>

**Squad:** <new_hire.squad> · **Role:** <new_hire.role, or omit line if not given> · **Start:**
<new_hire.start_date, or omit line if not given>

## Your repos

| Repo | Purpose | Confidence |
|------|---------|------------|
| <repo> | <one-line purpose, cited from domain-comprehension's P0 census / EXEC_SUMMARY.md — not invented here> | <HIGH \| MEDIUM \| LOW \| UNKNOWN> |

## Squad contacts

<Pulled from SQUAD_MAP.md's row(s) for this squad — GitLab namespace, Datadog team, any Conflicts-table
entry for these repos surfaced as-is, not resolved or hidden.>

## Go deeper

- Full domain map: [EXEC_SUMMARY.md](EXEC_SUMMARY.md)
- Squad ownership detail: [SQUAD_MAP.md](SQUAD_MAP.md)
- <any other domain-comprehension deliverable actually produced this run — link, don't restate>

## Notes

<Only present when relevant: zero-match resolution note if the squad initially matched nothing and the
user confirmed it owns no repos yet; any squad-map Conflicts-table row touching one of these repos,
surfaced plainly rather than silently resolved.>
```

## Rules

- **Curate and link, never restate wholesale.** The repo purpose line is a one-sentence pointer, not a
  copy of domain-comprehension's per-repo deep dive — someone who wants the full evidence trail follows
  the link into `EXEC_SUMMARY.md` / `{map_file}`.
- **Every purpose line and confidence value must be traceable to domain-comprehension's own output for
  that run** (P0 census entry, or `EXEC_SUMMARY.md` if P1 ran) — never invented by this skill, and never
  upgraded from what domain-comprehension itself recorded (an `UNKNOWN` purpose stays `UNKNOWN` here, it
  is not guessed into something more confident-sounding for a "friendlier" tour).
- **Squad contacts come from `SQUAD_MAP.md` as-is**, including any conflict flag — do not pick one side of
  a GitLab-vs-Datadog disagreement to present a cleaner answer than squad-map itself gave.
- **`## Your repos` is never empty** — if step 2's zero-match path is reached and the user confirms the
  squad genuinely owns no repos yet, say so plainly in `## Notes` instead of rendering an empty table with
  no explanation.
