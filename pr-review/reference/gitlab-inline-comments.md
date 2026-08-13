# GitLab Inline Comment Positions

Load this file only when posting inline comments (`create_merge_request_thread` or equivalent) in
**full** posting mode.

Immediately before every thread call, rebuild and sanitize/redact its body at the provider write
boundary in `workflow/posting.md`. Apply the same final boundary independently to every GitLab summary
note; a body being safe in chat or in a prior render does not make later embedding safe.
As the last GitLab-specific pass, encode the leading slash of an untrusted newline-leading `/approve`,
`/merge`, `/close`, `/ready`, or `/run_pipeline` control line as `&#47;`. Apply the same pass when the
finding moves to a summary/general note, fallback, or any newly built body; preserve authored template
structure.

## Position object

Build from `diff_refs` captured in Phase 1:

```json
{
  "position_type": "text",
  "base_sha":  "<diff_refs.base_sha>",
  "start_sha": "<diff_refs.start_sha>",
  "head_sha":  "<diff_refs.head_sha>",
  "old_path":  "<file old path>",
  "new_path":  "<file new path>",
  "new_line":  <line in new file, or null>,
  "old_line":  <line in old file, or null>
}
```

## Line-number rules

Parse the hunk header `@@ -oldStart,oldCount +newStart,newCount @@` and count lines in the hunk:

| Target line type | `new_line` | `old_line` |
|------------------|------------|------------|
| Added (`+`) | set | `null` |
| Removed (`-`) | `null` | set |
| Unchanged/context | set both | set both |

For renamed files: `old_path` = original path, `new_path` = new path.

Prefer `scripts/diff-to-positions.py` when anchoring many findings — it is more reliable than manual
counting. Pass `--base-sha`, `--start-sha`, and `--head-sha` from the **fresh** `diff_refs` after the
Phase 4 re-fetch (§SHA staleness) — SHAs from Phase 1 step 1 alone will produce rejected positions.
Use `--line N` for an added or context line; use `--old-line N` for a purely **removed** (`-`) line
(emits `old_line` set with `new_line: null`). Renamed files: pass `--old-path <old> --path <new>`.

## Preparing diff input for diff-to-positions.py

The script accepts two diff shapes:

- **Standard unified diff** with `diff --git` / `+++ b/<path>` headers (e.g. `git diff`, or a
  `get_merge_request_file_diff` call with `unidiff: true` when the server supports it). It walks only
  the hunks for `--path`.
- **GitLab MCP headerless hunks.** `get_merge_request_diffs` returns, per file, a `diff` string that is
  just bare `@@ … @@` hunks with **no `diff --git` and no `+++ b/path` header**. The script treats a
  headerless input as belonging entirely to `--path`, so you can pipe one file's `diff` straight in.

**When passing multiple files at once** (or to be unambiguous), wrap each file's hunks with a synthetic
header so the `+++ b/<path>` token matches `--path`:

```
diff --git a/<old_path> b/<new_path>
--- a/<old_path>
+++ b/<new_path>
<paste the file's hunk(s) here>
```

For a single file, the simplest path is: take that file's `diff` from `get_merge_request_diffs`, pass
it via `--diff-text "<hunk>"` (or stdin) with `--path <new_path>`, and let headerless mode handle it.

## Running the script (end-to-end)

Installed path: `~/.cursor/skills/pr-review/scripts/diff-to-positions.py` (or
`.cursor/skills/pr-review/scripts/` for a project install). **SHAs are required** for a position GitLab
will accept — use the **fresh** `diff_refs` from the Phase 4 re-fetch.

1. **Fetch** the MR diff: `get_merge_request_diffs` → each entry has `old_path`, `new_path`, `diff`.
2. **Run** the script on the file containing the finding (headerless `diff` via `--diff-text`):

   ```bash
   python3 ~/.cursor/skills/pr-review/scripts/diff-to-positions.py \
     --path src/foo.py --line 42 \
     --diff-text "$FILE_DIFF" \
     --base-sha "$BASE" --start-sha "$START" --head-sha "$HEAD"
   ```

   Output:

   ```json
   {
     "position_type": "text",
     "old_path": "src/foo.py",
     "new_path": "src/foo.py",
     "new_line": 42,
     "old_line": null,
     "base_sha": "BASE",
     "start_sha": "START",
     "head_sha": "HEAD"
   }
   ```
3. **Post:** pass that object as the `position` argument to `create_merge_request_thread`, with the
   comment `body` from `reference/comment-templates.md`.

**Batch many findings in one call** (avoids 15 separate invocations) — pipe a JSON array on stdin with
`--batch`; the diff still comes from `--diff-text`/`--diff-file`:

```bash
echo '[{"path":"src/foo.py","line":42},{"path":"src/bar.py","old_line":7}]' \
  | python3 …/diff-to-positions.py --batch --diff-file mr.diff \
      --base-sha "$BASE" --start-sha "$START" --head-sha "$HEAD"
# → a JSON array of position objects, in input order
```

(For `--batch` the diff must contain headers for every referenced file, or be a single headerless file
that all items target.)

### Batch partial failure (exit 1)

`--batch` never aborts on a single bad finding: it emits a position
object for every resolvable item **and** an `{"error": ...}` entry (echoing `path` + `line`/`old_line`)
for each one it could not map, in input order, then exits **1**. On exit 1, **post threads for the
entries without an `error` field**, and record the `error` entries (with their `file:line`) in the
summary's **Posting notes** — never drop them. A clean batch exits 0.

## line_code handling

`@zereight/mcp-gitlab`'s `create_merge_request_thread` marks `line_code` as **usually required** and
explicitly says **never fabricate it**. `line_code` is a server-computed hash of the file path and
line — it must come from GitLab, not be guessed.

When a thread is rejected for a missing/invalid `line_code`:

1. **Get the real value from the diff API.** `get_merge_request_diffs` (and the discussions API)
   expose `line_code` and the `line_range` (`start`/`end` with `line_code`, `type`, `old_line`,
   `new_line`) for changed lines. Read the `line_code` for your target line from that API response —
   never construct it yourself.
2. **Retry once** with `line_range` populated from those API values (and `line_code` on the position
   when the tool accepts it).
3. If it still fails, **fall back** to including the finding in the summary note with `file:line` (see
   Retry and fallback). Never fabricate `line_code` and never silently drop the finding.

**Exception:** on **renamed** files (`old_path ≠ new_path`), skip steps 1–2 — use the renamed-file
fast path in [Renamed and deleted files](#renamed-and-deleted-files) instead.

## Renamed and deleted files

- **Renamed** (`old_path ≠ new_path`, `renamed_file: true` in the diff entry): anchor with
  `--path <new_path> --old-path <old_path>`. In incremental re-reviews, map the prior finding's
  `old_path` → `new_path` when deduping (see `reference/incremental-rerun.md`).
- **Renamed-file inline fallback (fast path):** GitLab's position API is unreliable on renames —
  especially **rename-only** diffs (path change, no hunk content) and **CRLF vs LF** line-ending
  differences. For any finding on a renamed file:
  1. Try **one** inline post with `--old-path` set.
  2. On **any** rejection, **stop retrying that finding** — do not run `line_code` recovery, context-line
     dual-number retries, or multiple position variants. Move the finding to the **summary note** with
     `file:line` and tag it in **Posting notes** as *inline failed — renamed file*.
  3. Continue with remaining findings (renamed-file failure never aborts the batch).
- **Deleted-only** (`deleted_file: true`, no new file): an inline thread on a deleted file is not
  possible — record the finding in the **summary note** with the old `file:line` instead.

## Retry and fallback

Apply this **per finding**; a rejection on one thread (even the first) **never aborts the others** —
keep posting all remaining threads and collect failures (see `workflow/posting.md` §Partial-post recovery).

**Renamed files:** use the [Renamed-file inline fallback](#renamed-and-deleted-files) fast path — at
most one inline attempt, then summary. The steps below apply to **non-renamed** files only.

1. If rejected for a bad position on a context line, retry once with **both** line numbers set.
2. If still rejected, include the finding in the **summary comment** with `file:line` — never drop it.
3. After posting, re-fetch discussions/notes when the API allows; log any findings that failed to anchor
   in the summary under **Posting notes**.

## Inline comment budget

Default cap: **15 inline threads** per review (configurable — see **Configuring the thread cap**
below). Fill the budget in priority order:
1. Findings with highest **rank score (L × I)** — see `severity-rubric.md` §Ranking findings
2. Tie-break: Overall (Critical > High > Medium > Low), then `file:line`
3. Low / Nits (bundle into one thread when budget is exhausted)

If top-ranked findings alone exceed 15, all 15 slots go to the highest rank scores. Overflow findings
are included in the summary note with `file:line` references and flagged: *"N findings could not be
posted inline — see summary below."* Never silently drop a finding.

Always post the summary comment (when summary posting is available).

### Configuring the thread cap

The default **15** is a practical GitLab API / noise limit. To change it:

- **Team-wide (skill install):** edit §Configuring the thread cap in this file under
  `~/.cursor/skills/pr-review/reference/` (or your fork of the skill).
- **Per-repo under review:** add `.cursor/skills/pr-review/gitlab-inline-comments.md` in that repo with
  the new cap — takes precedence over the team-wide default when present.

The agent reads whichever override applies in Phase 4 instead of the default **15**.

## SHA staleness

**Always** re-fetch `get_merge_request` immediately before every provider write: each inline thread,
summary/general note, draft, and deterministic fallback. Compare `diff_refs.head_sha` to the SHA
captured in Phase 1 step 1 (when gathering began). If the author pushed during review:

1. Return `REVISION_MISMATCH` immediately.
2. Stop the current and all remaining provider writes in `full`, `summary-only`, `general-only`, and
   draft modes; report which earlier writes were confirmed posted and which were skipped.
3. Restart from Phase 1 against the new head before offering posting again.

Never rebuild positions, degrade to a summary, or continue any partial batch after this mismatch. The
provider invariant wins over posting convenience: no comment body prepared for the stale review may be
posted against the new revision.

## Ambiguous write response

GitLab profiles do not guarantee complete paginated discussion/note readback. If a thread or note POST
returns `timeout` or `server_error`, it may have been accepted: do not read back or retry, do not post a
fallback or summary, and stop all remaining provider writes. Report `WRITE_DELIVERY_UNCERTAIN`, the
possibly accepted body identity, confirmed earlier posts, and skipped writes. This conservative path
prevents a duplicate even when delivery cannot be proven.
