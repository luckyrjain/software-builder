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

1. **Check for a fresh existing `SQUAD_MAP.md`** at `workspace_root` (if provided). If it exists and
   already has a row matching `query` (exact or single unambiguous fuzzy match — see squad-map's own
   alias-matching rules in [squad-mapping.md](../../squad-map/reference/squad-mapping.md)), use that row
   and skip to Step 3. This avoids a full re-query for a name squad-map has already resolved.

2. **Otherwise, invoke squad-map** scoped to a single repo — equivalent to a user asking squad-map "who
   owns `<query>`?" (squad-map's own single-repo Inputs path, [inputs.md](../../squad-map/workflow/inputs.md)
   § Repo scope). Let squad-map run its own Inputs → Phase 0 → Phase 1 for that one repo. If squad-map's
   config resolution HARD STOPs (missing `squad_path_segment` and no config file), do not block the Slack
   reply waiting on an interactive answer nobody can give in a single-shot context — return the
   **Unknown** shape with a note that ownership config is missing, per
   [reference/slack-format.md](../reference/slack-format.md) § Unknown.

3. **Classify the result** using squad-map's own confidence band and conflict flag — do not
   re-derive or override it:

   | squad-map result | Shape |
   |-------------------|-------|
   | Exactly one row, HIGH or MEDIUM confidence, no conflict flag | Resolved |
   | Multiple matching rows, or a row with a conflict flag (GitLab squad ≠ Datadog team) | Ambiguous |
   | No matching row, or matching row is UNKNOWN/LOW confidence | Unknown |

   **LOW confidence counts as Unknown, not Resolved** — a single-shot Slack reply has no room for a
   confidence caveat the way an interactive squad-map session does; stating a LOW-confidence squad as
   fact would read as more certain than it is.

4. **Format** per [reference/slack-format.md](../reference/slack-format.md) and reply. Do not write any
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
