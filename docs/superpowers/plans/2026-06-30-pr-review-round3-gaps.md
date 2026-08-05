# pr-review Round 3 Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close 4 gaps from the Round 3 gap analysis for the pr-review skill: revert MR detection (P1-4), mixed bot+human MR handling (P2-4), CODEOWNERS approval enforcement (P2-5), and OpenAPI/Protobuf spec change detection (P3-3).

**Architecture:** All changes are targeted additions to existing workflow and reference files. Task order: P1-4 (revert detection — phase-1 + phase-2), P2-4 (mixed bot — phase-1 + fast-path), P2-5 (CODEOWNERS — phase-5), P3-3 (spec detection — phase-2).

**Tech Stack:** Markdown skill documents under `pr-review/`.

## Global Constraints

- All files are under `pr-review/`
- Pressure tests file is `reference/pressure-tests.md`
- Changes are purely additive — do not restructure or rewrite existing content
- New phase-2 dimensions follow the `§NN Name` numbering convention (§18 is currently the last)
- Bot-dependency fast path logic lives in both `workflow/phase-1.md` and `reference/fast-path.md`

---

### Task 1: P1-4 — Revert MR Detection

**Files:**
- Modify: `pr-review/workflow/phase-1.md` (add revert detection in step 1, after bot-authored check)
- Modify: `pr-review/workflow/phase-2.md` (add §19 Revert completeness conditional dimension)
- Modify: `pr-review/reference/pressure-tests.md` (add 2 revert MR pressure test rows)

**Interfaces:**
- Produces: `capability_profile.revert_mr: true`, `capability_profile.revert_target_sha` (when extractable)
- Consumes: MR `title`, `description`, and diff net LOC from Phase 1 step 1 + 2

- [ ] **Step 1: Add revert MR pressure test rows**

  Read `pr-review/reference/pressure-tests.md` to find the table. Append:

  ```markdown
  | MR title = "Revert auth-service deploy #1483"; diff = 95% deletions | Detect revert MR; apply §19 Revert completeness review; check (a) completeness, (b) intervening deps, (c) schema gap |
  | Revert MR detected; agent applies standard feature-MR review checklist | **Wrong** — must switch to §19 revert-specific checks when `capability_profile.revert_mr: true` |
  ```

- [ ] **Step 2: Add revert detection to `pr-review/workflow/phase-1.md` step 1**

  Read the file. The bot-authored detection block in step 1 ends with:
  ```
  Note at Phase 2 start: *"Bot-authored MR detected — applying dependency-review profile."*
  ```

  After that sentence, append the revert detection block (still within step 1):

  ```markdown

  **Revert MR detection:** after the bot-authored check, also detect revert MRs. Match any of:

  | Signal | Pattern |
  |--------|---------|
  | Title prefix | Starts with `"Revert "` (case-sensitive, with trailing space) |
  | Description body | Contains the phrase `"This reverts commit "` (standard Git revert message) |
  | Net LOC | Deletions are > 60% of max(additions, deletions) across the full diff boundary |

  When any signal matches:
  - Set `capability_profile.revert_mr: true`.
  - Extract the reverted commit SHA or MR IID from the title/description and record as
    `capability_profile.revert_target_sha` (leave null if not identifiable).
  - Announce: *"Revert MR detected — applying revert-specific review (§19)."*
  - Phase 2 will apply §19 Revert completeness instead of the standard architecture/performance
    passes on the reverted hunks. Do **not** set bot-dependency profile for a revert authored by a
    human — the two are independent.
  ```

- [ ] **Step 3: Add §19 Revert completeness to `pr-review/workflow/phase-2.md`**

  Read the file. The §18 AI-generated code block ends with:
  ```
  Apply §18 regardless of fast path when triggered. Prefix findings `ai ·`. Do not suppress §18 findings via stop-search thresholds — complete the §18 pass before stopping.
  ```

  After that block, append §19:

  ```markdown

  **§19 Revert completeness** — when `capability_profile.revert_mr: true`:

  Apply regardless of fast path. Prefix findings `revert ·`. Complete §19 before stop-search fires.

  | Check | What to look for | Severity |
  |-------|-----------------|----------|
  | **(a) Completeness** | Does the diff undo ALL original changes? Compare against `revert_target_sha` diff when `git show <sha>` is accessible — flag any original hunk missing from this revert | High |
  | **(a) Config / migration steps** | Original MR may have included config changes, DB migrations, or feature-flag updates outside the code diff — were those also reverted? Check MR description and commit message of the target SHA | High |
  | **(b) Intervening dependencies** | Were new packages, schema columns, or service calls added AFTER the original MR (between original merge and this revert) that depend on the reverted change? Use `git log <revert_target_sha>..HEAD -- <changed_paths>` or check MR timeline | Medium |
  | **(c) Data / schema gap** | Does the revert drop a DB column, index, or table that has already received writes in production? If schema objects are reverted without a forward-migration companion, flag as High | High |
  | **(c) Forward fix needed** | If a data gap is identified, is there a companion migration MR or forward fix planned? Absence → emit finding | Medium |
  ```

- [ ] **Step 4: Verify additions**

  ```bash
  grep -n "Revert MR detection\|revert_mr\|revert_target_sha\|§19\|Revert completeness" \
    /Users/luckyjain/Projects/ai-skills/pr-review/workflow/phase-1.md \
    /Users/luckyjain/Projects/ai-skills/pr-review/workflow/phase-2.md \
    /Users/luckyjain/Projects/ai-skills/pr-review/reference/pressure-tests.md
  ```
  Expected: hits in all three files.

- [ ] **Step 5: Commit**

  ```bash
  git add \
    pr-review/workflow/phase-1.md \
    pr-review/workflow/phase-2.md \
    pr-review/reference/pressure-tests.md
  git commit -m "feat(pr-review): P1-4 — revert MR detection and §19 completeness review"
  ```

---

### Task 2: P2-4 — Mixed Bot+Human MR Handling

**Files:**
- Modify: `pr-review/workflow/phase-1.md` (add commit-level human detection in step 5)
- Modify: `pr-review/reference/fast-path.md` (update bot-dependency profile note)
- Modify: `pr-review/reference/pressure-tests.md` (add 2 mixed-MR pressure test rows)

**Interfaces:**
- Produces: `capability_profile.bot_has_human_commits: true`, `capability_profile.human_commit_shas: [...]`
- Consumes: `capability_profile.bot_dependency: true` (from step 1), commit list from step 5

- [ ] **Step 1: Add mixed-MR pressure test rows**

  Append to `pr-review/reference/pressure-tests.md` table:

  ```markdown
  | Renovate-authored MR; human engineer pushes 1 commit to resolve a version conflict | `bot_has_human_commits: true`; architecture/style review applies to human commit hunks; CVE/changelog focus still applies to Renovate diff |
  | Bot MR with human commits; agent skips §16 architecture on all hunks | **Wrong** — §16 must run on hunks from human commits even when outer MR is bot-dependency |
  ```

- [ ] **Step 2: Add human commit detection to `pr-review/workflow/phase-1.md` step 5**

  Read the file. Step 5 currently reads:
  ```
  5. `get_merge_request_commits` → baseline for incremental re-review.
  ```

  Expand it to:

  ```markdown
  5. `get_merge_request_commits` → baseline for incremental re-review.

     **Mixed bot+human detection (when `capability_profile.bot_dependency: true`):**
     Scan the commit list for commits whose `author.username` differs from `mr.author.username`:

     ```
     human_commits = commits.filter(c => c.author.username !== mr.author.username
                                      && c.author.username not in known_bot_usernames)
     ```

     `known_bot_usernames` = any username ending in `[bot]`, or matching the bot patterns from step 1.

     If `human_commits` is non-empty:
     - Set `capability_profile.bot_has_human_commits: true`.
     - Record `capability_profile.human_commit_shas` = list of short SHAs.
     - Announce: *"Mixed MR: bot-authored base + N human commit(s) [<shas>] — dependency fast
       path applies to bot hunks; standard review applies to human hunks."*
  ```

- [ ] **Step 3: Update `reference/fast-path.md` bot-dependency profile**

  Read the file. In the `## Profiles — what to skip` table, the bot-dependency row currently reads:
  ```
  | **bot-dependency** | Jira AC optional; CI step 4 — dependency scan + pipeline status | **Dependency/CVE focus**; skip §4/§8/§9/§16 style/architecture deep pass | Mechanical executive summary — verify bump safe, breaking changelog |
  ```

  After the bot-dependency row, add a note paragraph (outside the table) immediately after the table:

  ```markdown

  > **Mixed bot+human MR:** when `capability_profile.bot_has_human_commits: true`, the
  > `bot-dependency` fast-path profile applies **only to diff hunks from bot commits**. Diff
  > hunks from human commits (`human_commit_shas`) use the **standard** profile — §16 architecture,
  > style, §8 test quality, and §9 observability all run on those hunks. Announce the split at
  > Phase 2 start.
  ```

  Also update the `## Bot-authored PR fast path` section. After the final "Announce:" line, add:

  ```markdown

  **Mixed MR exception:** when `bot_has_human_commits: true`, the Phase 2 review engine splits the
  boundary by commit author. Only skip §4/§8/§9/§16 for files **exclusively** changed by bot commits.
  Files touched by human commits (even if also touched by the bot) receive standard review.
  ```

- [ ] **Step 4: Verify additions**

  ```bash
  grep -n "bot_has_human_commits\|human_commit_shas\|Mixed bot\|Mixed MR" \
    /Users/luckyjain/Projects/ai-skills/pr-review/workflow/phase-1.md \
    /Users/luckyjain/Projects/ai-skills/pr-review/reference/fast-path.md \
    /Users/luckyjain/Projects/ai-skills/pr-review/reference/pressure-tests.md
  ```
  Expected: hits in all three files.

- [ ] **Step 5: Commit**

  ```bash
  git add \
    pr-review/workflow/phase-1.md \
    pr-review/reference/fast-path.md \
    pr-review/reference/pressure-tests.md
  git commit -m "feat(pr-review): P2-4 — mixed bot+human MR detection and split review profile"
  ```

---

### Task 3: P2-5 — CODEOWNERS Approval Path Enforcement

**Files:**
- Modify: `pr-review/workflow/phase-5.md` (add CODEOWNERS approval cross-check before recommendation matrix)
- Modify: `pr-review/reference/pressure-tests.md` (add 2 CODEOWNERS pressure test rows)

**Interfaces:**
- Consumes: `context_cache.codeowners_rules` (cached in Phase 1 step 7), approval list from Phase 1 step 4
- Produces: CODEOWNERS approval gap findings, optional recommendation raise

**Note:** Phase 1 step 7 already caches CODEOWNERS. Phase 1 step 4 already reads approval state. This task adds the cross-check that was never wired up between them.

- [ ] **Step 1: Add CODEOWNERS pressure test rows**

  Append to `pr-review/reference/pressure-tests.md` table:

  ```markdown
  | MR touches `src/payments/billing.rb`; CODEOWNERS: `src/payments/ @payments-team`; only `@platform-eng` has approved | Emit Medium finding: "CODEOWNERS approval gap: src/payments/ requires @payments-team — not yet given"; raise overall recommendation to at least 💬 Comment |
  | MR touches only files with no CODEOWNERS entry; agent emits CODEOWNERS finding | **Wrong** — no finding for paths not covered by CODEOWNERS |
  ```

- [ ] **Step 2: Add CODEOWNERS cross-check to `pr-review/workflow/phase-5.md`**

  Read the file. The `## Output order` section begins with step 1 "Re-review block". Before the output order list, insert a new section:

  ```markdown
  ## CODEOWNERS approval cross-check

  Run this check **before** the recommendation matrix when `context_cache.codeowners_rules` is
  populated (from Phase 1 step 7) and approval state is available (Phase 1 step 4).

  For each path in `review_boundary.changed_paths`:

  1. **Match** the path against CODEOWNERS patterns (most specific rule wins; use gitignore-style
     glob matching — a rule for `src/payments/` is more specific than `src/` which is more specific
     than `*`). Paths with no matching CODEOWNERS entry: skip — no ownership gate.

  2. **Extract** required owners (GitHub teams as `@org/team` or usernames as `@user`).

  3. **Check** whether at least one required owner for this path appears in the Phase 1 step 4
     approval list (approved users / teams).

  4. **For each path with a gap** (no required owner has approved):

     Emit a finding in the review findings list:

     ```
     CODEOWNERS approval gap: `<path>` requires [<owner>] — not yet given
     Severity: Medium
     ```

  **Recommendation raise:** if any CODEOWNERS gap exists AND the current recommendation is
  ✅ **Approve** (no Critical/High findings), raise to 💬 **Comment** and add to **Reason:**

  > *"CODEOWNERS approval pending for <N> path(s) — merge blocked until required owners approve."*

  **CODEOWNERS Approval Gaps block (in executive summary, when gaps exist):**

  ```
  ### CODEOWNERS Approval Gaps

  | Path | Required owner | Approved? |
  |------|----------------|-----------|
  | src/payments/ | @payments-team | ❌ Not yet |
  | config/auth/ | @security-team | ✅ Approved |
  ```

  Omit this block entirely when there are no gaps or when CODEOWNERS is absent.
  ```

- [ ] **Step 3: Verify additions**

  ```bash
  grep -n "CODEOWNERS approval cross-check\|CODEOWNERS Approval Gaps\|codeowners_rules" \
    /Users/luckyjain/Projects/ai-skills/pr-review/workflow/phase-5.md \
    /Users/luckyjain/Projects/ai-skills/pr-review/reference/pressure-tests.md
  ```
  Expected: hits in both files.

- [ ] **Step 4: Commit**

  ```bash
  git add \
    pr-review/workflow/phase-5.md \
    pr-review/reference/pressure-tests.md
  git commit -m "feat(pr-review): P2-5 — CODEOWNERS per-path approval enforcement in Phase 5"
  ```

---

### Task 4: P3-3 — OpenAPI/Protobuf Spec Change Detection

**Files:**
- Modify: `pr-review/workflow/phase-2.md` (add §20 API spec changes conditional dimension)
- Modify: `pr-review/reference/pressure-tests.md` (add 2 spec change pressure test rows)

**Interfaces:**
- Produces: `spec ·` prefixed findings for schema validity, breaking changes, version bumps, proto field reuse
- Consumes: `review_boundary` file list (any `openapi*`, `swagger*`, `*.proto`, `asyncapi*` files)

**Note:** §19 Revert completeness was added in Task 1. This task adds §20. Numbering must be kept consistent.

- [ ] **Step 1: Add spec change pressure test rows**

  Append to `pr-review/reference/pressure-tests.md` table:

  ```markdown
  | MR modifies `openapi.yaml`: removes path `/v1/users/{id}`; `info.version` not bumped | Emit `spec · High` finding: breaking path removal without version bump |
  | MR modifies `user.proto`: field `user_id` (field number 1) deleted and field number 1 reused for `account_id` | Emit `spec · Critical` finding: proto field number 1 reused — deserialization corruption risk |
  ```

- [ ] **Step 2: Add §20 API spec changes to `pr-review/workflow/phase-2.md`**

  Read the file. The §19 Revert completeness block ends with:
  ```
  | **(c) Forward fix needed** | If a data gap is identified, is there a companion migration MR or forward fix planned? Absence → emit finding | Medium |
  ```
  (This assumes Task 1 has been applied. If §19 is absent, append after the §18 block instead.)

  After the §19 block, append:

  ```markdown

  **§20 API spec changes** — when the review boundary contains any of the following file patterns:
  - `openapi*.yaml`, `openapi*.json`, `swagger*.yaml`, `swagger*.json`
  - `*.proto` (anywhere in the diff)
  - `asyncapi*.yaml`, `asyncapi*.json`
  - Files under `**/proto/**`, `**/openapi/**`, `**/swagger/**`

  Apply §20 regardless of fast path when triggered. Prefix findings `spec ·`.

  | Check | What to look for | Severity |
  |-------|-----------------|----------|
  | **Spec validity** | Changed YAML/JSON has required top-level fields (`openapi` + `info` + `paths` for OpenAPI 3.x; `swagger` + `info` + `paths` for Swagger 2.0; `syntax`, `package`, `message` for proto) | Medium |
  | **Breaking path removal** | Existing path (URL route) removed from OpenAPI/Swagger `paths:` without deprecation marker | High |
  | **Required field dropped** | A field that was `required: true` in a request/response schema is removed or made optional — consumers expecting it will break | High |
  | **Response type changed** | A response schema's type changed (e.g. `string` → `integer`, `object` → `array`) without a new API version | High |
  | **New required request field** | A field added to a request schema with `required: true` (no default) — callers not updated will fail validation | Medium |
  | **Version bump absent** | Breaking changes detected (any High above) but `info.version` is unchanged | Low — escalate to Medium when breaking changes present |
  | **Proto field number reuse** | A proto field number that was previously assigned to a deleted field is now assigned to a new field — deserialization of existing serialized data will corrupt | Critical |
  | **AsyncAPI channel removal** | A channel (topic/queue name) removed from `channels:` — consumers will silently lose their subscription | High |
  | **Codegen drift** | Spec file changed but generated client/stub files (`**/generated/**`, `*_pb2.py`, `*.pb.go`, `**/openapi-generated/**`) were NOT updated in the same MR | Medium |
  ```

- [ ] **Step 3: Verify additions**

  ```bash
  grep -n "§20\|API spec changes\|openapi\|proto field number\|asyncapi\|spec ·" \
    /Users/luckyjain/Projects/ai-skills/pr-review/workflow/phase-2.md \
    /Users/luckyjain/Projects/ai-skills/pr-review/reference/pressure-tests.md
  ```
  Expected: hits in both files.

- [ ] **Step 4: Commit**

  ```bash
  git add \
    pr-review/workflow/phase-2.md \
    pr-review/reference/pressure-tests.md
  git commit -m "feat(pr-review): P3-3 — OpenAPI/Protobuf/AsyncAPI spec change detection (§20)"
  ```
