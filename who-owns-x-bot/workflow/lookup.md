---
workflow_version: 1.0
phase: lookup
produces:
  - slack_reply
consumes:
  - query
  - workspace_root
---

# Lookup — delegate to squad-map, format for Slack

**Goal:** Get an ownership answer for `query` from squad-map and return exactly one Slack-formatted
message. No new ownership logic here — see [SKILL.md](../SKILL.md) Non-goals.

## Steps

1. **who-owns-x-bot itself must be installed alongside squad-map** — if squad-map is not installed at
   all (no `squad-map/SKILL.md` reachable), this is a setup error, not a lookup outcome: return
   **Unknown** with the note "squad-map not installed" per
   [reference/slack-format.md](../reference/slack-format.md) § Unknown, and stop — do not attempt any of
   the steps below. (`make install-who-owns-x-bot` always installs squad-map alongside it, so this should
   only happen from a broken manual install.)

2. **Check for a fresh existing `SQUAD_MAP.md`** at `workspace_root` (if provided).
   - **Exact match:** exactly one row's `Repo` column equals `query` → use that row, skip to Step 4.
   - **Substring/prefix match:** no exact match, but `query` is a substring or prefix of one or more
     `Repo` values (e.g. `query: ledger` against rows `legacy-ledger`, `ledger-service`) → if exactly one
     row matches, use it; if more than one row matches, that **is** the "matches more than one repo"
     Ambiguous case — go straight to Step 4 with those candidate rows, do not run Step 3.
   - **No match at all** → go to Step 3.

3. **Otherwise, invoke squad-map** scoped to a single, exact repo name (`query`) — equivalent to a user
   asking squad-map "who owns `<query>`?" (squad-map's own single-repo Inputs path,
   [inputs.md](../../squad-map/workflow/inputs.md) § Repo scope). Let squad-map run its own
   Inputs → Phase 0 → Phase 1 for that one repo. **This path resolves to at most one project** — squad-map's
   own GitLab/Datadog lookup (`get_project` / `search_datadog_services` on an exact name, per
   [squad-mapping.md](../../squad-map/reference/squad-mapping.md)) does not itself return multiple
   candidate repos the way a substring match against an existing table can; "matches more than one repo"
   can only arise from Step 2's substring match, never from this step. If squad-map's config resolution
   HARD STOPs (missing `squad_path_segment` and no config file), do not block the Slack reply waiting on
   an interactive answer nobody can give in a single-shot context — return the **Unknown** shape with a
   note that ownership config is missing, per [reference/slack-format.md](../reference/slack-format.md)
   § Unknown.

4. **Classify the result** using squad-map's own confidence band and conflict flag — do not
   re-derive or override it. A "conflict flag" is any row squad-map placed in its own Conflicts table —
   per [squad-mapping.md § Reconciliation](../../squad-map/reference/squad-mapping.md#reconciliation) and
   § Datadog mapping, that includes **both** GitLab squad ≠ Datadog team **and** one Datadog service
   tagged with multiple `team` values (squad-map caps that case at MEDIUM too, for the same reason —
   don't silently pick one team):

   | squad-map result | Shape |
   |-------------------|-------|
   | Exactly one row, HIGH or MEDIUM confidence, **not** in squad-map's Conflicts table | Resolved |
   | Step 2 substring match returned multiple candidate rows | Ambiguous |
   | Single row, but squad-map placed it in its own Conflicts table (GitLab ≠ Datadog, or one service with
     multiple team tags) | Ambiguous |
   | No matching row, or matching row is UNKNOWN/LOW confidence | Unknown |

   **LOW confidence counts as Unknown, not Resolved** — a single-shot Slack reply has no room for a
   confidence caveat the way an interactive squad-map session does; stating a LOW-confidence squad as
   fact would read as more certain than it is.

5. **Format** per [reference/slack-format.md](../reference/slack-format.md) and reply. Do not write any
   file — the reply text is the only output of this skill (squad-map may still have written or updated
   `SQUAD_MAP.md` as its own side effect in Step 2; that is squad-map's artifact, not this skill's).

## Read-only boundary

No GitLab writes, no Datadog mutations, no Slack messages beyond the single reply, no deploys, no
application source changes.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| `slack_reply` | Returned to caller | shape (Resolved/Ambiguous/Unknown), body text | Lookup incomplete |

## Completion summary (chat)

When run inside an interactive agent session (e.g. for testing), also state in chat: query, shape
chosen, squad-map confidence used.
