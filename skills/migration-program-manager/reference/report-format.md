# MIGRATION_PROGRAM_REPORT.md + migration_program_rollup.json format

**Normative.** The exact structure [workflow/run-rollup.md](../workflow/run-rollup.md) § 3 must produce.

## Safe rendered-output boundary

`<service>`, `<workspace_root>`, `<squad name>`, `<mr_url>`, `<notes>`, and the Workspace gaps table's
`Reason` column (which can itself embed `<workspace_root>`/`squad_map_path`, e.g. "No SQUAD_MAP.md at
`<path>`") all come from `program_manifest`, from `MIGRATION_STATUS.yaml`'s own free-text fields, or —
for `<squad name>` — from `SQUAD_MAP.md`'s own `GitLab squad`/`Datadog team` columns (external,
org-configured metadata this skill never generates itself) — untrusted content per
[prompt-injection.md](../../docs/skill-framework/shared/prompt-injection.md) and
[safe-output.md](../../docs/skill-framework/shared/safe-output.md).
`scripts/aggregate_migration_status.py` only computes structured data and a stderr gap log — it never
writes this Markdown file itself, so none of this sanitization happens there; it's this rendering step's
own responsibility. **All six need the same first step, no exceptions:**

1. **Structurally escape or fence newlines, leading `#`/`>`/`-`, table `|` delimiters, and unbalanced
   triple-backtick fences in every one of them, always** — a Markdown table splits rows at the line level
   *before* any inline formatting (including a code span) is parsed, so wrapping a value in backticks
   does **not** stop an embedded raw newline from breaking out of the cell and rendering the rest of the
   value as a new heading or row. `<squad name>` is rendered as an actual `## <squad name>` heading, not
   a table cell — the same newline risk applies there too: a real newline in the value simply ends that
   heading line early and lets the rest render as separate content, including a spoofed
   `## Fake Squad Name` heading of its own. An unbalanced ` ``` ` in `<notes>` is a distinct risk from
   the others: it opens an unterminated code fence that swallows every following squad section and table
   into one literal code block, rather than breaking structure locally. Newline/heading/pipe/fence
   escaping is the actual defense; treat it as required for `<service>`, `<workspace_root>`, and
   `<squad name>` too, not just the visibly-freer-text fields.
2. **Then**, for the three short, identifier-shaped fields — `<service>`, `<workspace_root>`, and
   `<squad name>` — also wrap the (already-escaped) value in an inline code span (backtick, value,
   backtick — the same treatment applies inside the `<squad name>` heading, wrapping just the value
   after the `## ` prefix), first **removing** any backtick already in the value (safe-output.md Rule 4)
   so it can't close the span early. A backslash before the backtick does **not** work — CommonMark
   code-span delimiters are matched before backslash escapes are resolved, so putting a backslash in
   front of an embedded backtick still lets that backtick close the span early, exposing the rest of the
   value as live Markdown. Strip the character entirely; don't try to escape it in place. This signals
   "this is data" to a human reader; it is a second, cosmetic layer on top of step 1, never a substitute
   for it. `<mr_url>`, `<notes>`, and the gap `Reason` text are not short identifiers — render them as a
   plain escaped/fenced excerpt instead of a code span.
3. **Redact** plausible secrets, tokens, and PII from `<notes>` (a migration note can itself contain a
   pasted credential or connection string), noting when redaction was applied.

## `MIGRATION_PROGRAM_REPORT.md` structure (order fixed)

```markdown
# Migration program — <date>

**Workspaces:** <N scanned, M with gaps> · **Services:** <total> · **Blocked:** <count> · **Stalled:** <count>

## `<squad name>`

### Blocked

| Service | Workspace | Failing gate | MR | Notes |
|---------|-----------|--------------|-----|-------|
| `<service>` | `<workspace_root>` | scan_gate \| shadow_compare \| config_cutover | <mr_url, escaped/fenced per above, or —> | <notes, escaped/fenced per above> |

### Stalled (unchanged ≥ <staleness_threshold_days> days)

| Service | Workspace | Staleness | Current gates | MR |
|---------|-----------|-----------|-----------------|-----|
| `<service>` | `<workspace_root>` | <N> days | <scan_gate>/<shadow_compare>/<config_cutover> | <mr_url, escaped/fenced per above, or —> |

### In progress

| Service | Workspace | Gates | MR |
|---------|-----------|-------|-----|
| `<service>` | `<workspace_root>` | <scan_gate>/<shadow_compare>/<config_cutover> | <mr_url, escaped/fenced per above, or —> |

### Done

| Service | Workspace |
|---------|-----------|
| `<service>` | `<workspace_root>` |

<Repeat per squad, in any stable order. Squads with nothing in one sub-section omit that sub-section
(never render an empty table), but a squad with at least one service always gets its own heading.>

## UNKNOWN squad

<Same four sub-sections, for every service that couldn't be joined to a squad — always rendered last,
never silently merged into a named squad.>

## Workspace gaps

| Workspace | Reason |
|-----------|--------|
| `<workspace_root>` | MIGRATION_STATUS.yaml not found — run mysql-to-postgres-sql first |
| `<workspace_root>` | No SQUAD_MAP.md at <squad_map_path, escaped/fenced per above> — run squad-map directly |
```

## `migration_program_rollup.json` shape

A flat JSON array of `org_rollup_item` objects (per
[org-rollup-schema.md](../../docs/skill-framework/shared/org-rollup-schema.md)), each with an added
`staleness_days` field (this skill's own computed value, not part of the shared schema's base shape —
schemas can be extended per-consumer as long as the base fields stay intact). Written so
[weekly-squad-digest](../../weekly-squad-digest/SKILL.md) can read this file directly instead of
re-running the aggregator.

## Rules

- **Each service appears in exactly one of the four sub-sections (Blocked/Stalled/In progress/Done),
  chosen by its persisted `status` field from `migration_program_rollup.json` — never by independently
  re-checking `value.scan_gate`/`value.shadow_compare`/`value.config_cutover` for `fail` or
  `staleness_days` against `staleness_threshold_days` while rendering.** `status` is already mutually
  exclusive (`blocked` always wins over staleness — see [workflow/run-rollup.md](../workflow/run-rollup.md)
  § 2); a blocked service's `staleness_days` can independently exceed the threshold too (its failing gate
  just hasn't changed in a while), which would otherwise put the same service in both the Blocked and
  Stalled tables.
- **Every `program_manifest` entry appears** — either contributing services to the per-squad sections, or
  as a row in Workspace gaps (or both, if some services parsed and others in the same workspace didn't).
- **`squad: UNKNOWN` services are never dropped and never guessed into a named squad** — their own section,
  always last.
- **A blocked service always names which gate failed** — not just "blocked," the specific
  `scan_gate`/`shadow_compare`/`config_cutover` value that's `fail`.
- **Staleness is this skill's own computed value** (see [SKILL.md](../SKILL.md) § Staleness tracking in
  the design spec) — never claim `MIGRATION_STATUS.yaml` itself records a timestamp it doesn't.
