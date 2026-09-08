# ONBOARDING_TOUR.md format

**Normative.** The exact structure [workflow/run-tour.md](../workflow/run-tour.md) § 4 must produce.
Written to `tour_output_dir` (default `{workspace_root}/../onboarding-tours/<slug>/`), **outside**
individual source repos — alongside links into domain-comprehension's workspace-level deliverables at
`workspace_root`, not instead of them.

## Safe rendered-output boundary

`<new_hire.name>`, `<new_hire.squad>`, `<new_hire.role>`, and `<new_hire.start_date>` are caller-supplied
data ([prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md)); `<repo>` and the
Squad contacts fields (GitLab namespace, Datadog team, Conflicts entries) come from `SQUAD_MAP.md`; the
per-repo purpose line is cited from domain-comprehension's own census, itself built by reading repository
content (READMEs, source) — none of these are skill-authored text. `<new_hire.name>` in particular is
rendered into the document's own **H1 title** — the single most sensitive position in the file. Before
rendering `ONBOARDING_TOUR.md`, for every one of these fields:

1. **Structurally escape or fence newlines, leading `#`/`>`/`-`, table `|` delimiters, and unbalanced
   triple-backtick fences, always** — a raw newline in `<new_hire.name>` simply ends the H1 title line
   early and lets the rest of the value render as separate document content, including a spoofed heading
   of its own; the same applies to `<new_hire.squad>`/`<new_hire.role>`/`<new_hire.start_date>` in the
   metadata line and to the purpose line in the table.
2. **Then**, for the short, identifier-shaped fields — `<new_hire.name>`, `<new_hire.squad>`,
   `<new_hire.role>`, `<new_hire.start_date>`, `<repo>`, and the Squad contacts identifiers — also wrap
   the (already-escaped) value in an inline code span, first **removing** any backtick already in it
   ([safe-output.md](../../docs/skill-framework/shared/safe-output.md) Rule 4). A backslash before the
   backtick does **not** work — CommonMark code-span delimiters are matched before backslash escapes are
   resolved. Strip the character entirely. The per-repo purpose line is not a short identifier — render
   it as a plain escaped/fenced excerpt instead of a code span.
3. **Redact** plausible secrets, tokens, and PII from the per-repo purpose line before including it —
   it's cited from domain-comprehension's own census, itself built by reading repository content
   (READMEs, source), the same class of evidence backlog-runner's escalation-report excerpt and
   pr-review's finding descriptions already redact — noting when redaction was applied.

## Structure (order fixed)

```markdown
# Onboarding tour — `<new_hire.name>`

**Squad:** `<new_hire.squad>` · **Role:** `<new_hire.role>` (omit this line entirely if not given) ·
**Start:** `<new_hire.start_date>` (omit this line entirely if not given)

## Your repos

| Repo | Purpose | Confidence |
|------|---------|------------|
| `<repo>` | <one-line purpose, escaped/fenced per above, cited from domain-comprehension's P0 census / EXEC_SUMMARY.md — not invented here> | <HIGH \| MEDIUM \| LOW \| UNKNOWN> |

## Squad contacts

<Pulled from SQUAD_MAP.md's row(s) for this squad — GitLab namespace, Datadog team, any Conflicts-table
entry for these repos, each escaped/fenced and code-span-wrapped per above, surfaced as-is, not resolved
or hidden.>

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
