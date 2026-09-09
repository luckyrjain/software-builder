# Fast-path decision tree (cost optimization)

Classify each MR **once** after Phase 1 step 2 (review boundary built). Record **`fast_path`** flags
and skip expensive work — even with lazy loading, avoid MCP calls and deep checklist passes when the
diff cannot benefit.

Load in **Phase 1** after step 2 (`workflow/phase-1.md`). Honor flags in Phase 2, Phase 5, and persona
auto-detect.

**User override:** `full review`, `exhaustive review`, or `no fast path` → ignore all skips below except
lockfile secret scan and grounding rules.

**Precedence:** repo `review-rules.yaml` `always_review` and
`reference/finding-gates.md#non-negotiable-checks-pipeline-step-6` **beat**
fast-path skips when they conflict (`reference/precedence.md`).

## Decision tree

Evaluate **top to bottom** — first matching **exit** or **profile** wins, then apply **modifiers**.

```
Review boundary (changed files)
        │
        ▼
┌─ ALL files lockfile/generated? ──YES──► EXIT: lockfile-only (mechanical)
│   (*.lock, poetry.lock, package-lock.json, yarn.lock, go.sum,
│    Gemfile.lock, pnpm-lock.yaml, shrinkwrap, vendor/cache only)
│   NO ──► continue
        ▼
┌─ ALL files docs/markdown? ──YES──► PROFILE: docs-only
│   (.md, .mdx, docs/**, README*, CHANGELOG*, *.rst, *.adoc)
│   NO ──► continue
        ▼
┌─ ALL files markdown? ──YES──► PROFILE: markdown-only
│   (subset: every changed file ends in .md / .mdx)
│   NO ──► continue
        ▼
┌─ ALL files test/fixture/config? ──YES──► PROFILE: test-only
│   (test_*, *_test.go, *.spec.*, fixtures/, __snapshots__/, .github/workflows only)
│   NO ──► continue
        ▼
        PROFILE: standard (default)
        │
        ▼
┌─ Bot-authored MR? ──YES──► PROFILE: bot-dependency (Renovate/Dependabot/codegen)
│   (author login renovate|dependabot|*bot*, or branch renovate/*, dependabot/*,
│    or title "Bump …" / "Update …" from automation)
│   NO ──► continue
        ▼
MODIFIERS (stack on profile):
  • file_count ≤ 5        → skip §16 Architecture Lens
  • file_count ≤ 3        → skip §17 Rollback (unless migration/IaC in diff)
  • no production code    → skip §4 Performance, §9 Observability, §8 test quality
  • user: full review     → clear all skips
```

## Profiles — what to skip

| Profile | Phase 1 skips | Phase 2 skips | Phase 5 skips |
|---------|---------------|---------------|---------------|
| **lockfile-only** (EXIT) | Jira AC deep dive optional; **CI step 4** — note head pipeline status only if cheap, no failure analysis; no full-file reads | All checklist except **dependency/CVE** spot-check on manifest if present in diff; no §4/§8/§9/§16/§17 | Production risk + Architectural summary — use **mechanical** executive summary only |
| **docs-only** | **CI step 4** — skip pipeline fetch/heuristics; record *"CI skipped — docs-only MR"* | §2 Security deep pass; §4/§8/§9/§16/§17; still **scan for secrets** in changed text | Production risk + Architectural summary omitted |
| **markdown-only** | Same as docs-only for CI | §2 Security checklist (**still scan diff for pasted secrets/tokens**); §4/§8/§9/§16/§17 | Same as docs-only |
| **test-only** | CI as normal | §16 unless >5 files; §17 unless migration touched; deprioritize observability | Architectural summary optional (brief) |
| **bot-dependency** | Jira AC optional; CI step 4 — dependency scan + pipeline status | **Dependency/CVE focus** — run [finding-gates.md](finding-gates.md) CVE row (CI → Snyk MCP → OSV); skip §4/§8/§9/§16 style/architecture deep pass | Mechanical executive summary — verify bump safe, breaking changelog |
| **standard** | None by default | Apply **modifiers** only | Full closeout unless modifier |

> **Mixed bot+human MR:** when `capability_profile.bot_has_human_commits: true`, the
> `bot-dependency` fast-path profile applies **only to diff hunks from bot commits**. Diff
> hunks from human commits (`human_commit_shas`) use the **standard** profile — §16 architecture,
> style, §8 test quality, and §9 observability all run on those hunks. Announce the split at
> Phase 2 start.

## Modifiers (stack)

| Modifier | When | Effect |
|----------|------|--------|
| **`skip_architecture`** | `file_count ≤ 5` OR profile is lockfile/docs/markdown/test-only | Do not load `architecture-lens.md`; skip §16 even if triggers fire; Architect persona auto-detect off |
| **`skip_ci_analysis`** | docs-only or markdown-only profile | Phase 1 step 4: do not call pipeline tools or merge-train heuristics — note *CI not evaluated (docs-only)* |
| **`skip_security_checklist`** | markdown-only or docs-only | Skip §2 dimensions; **always** run secret/credential substring scan on changed lines |
| **`skip_observability`** | no production runtime files in boundary | Skip §9 |
| **`skip_test_quality`** | test-only or docs-only | Skip §8 table |
| **`skip_rollback`** | ≤3 files and no migration/IaC/terraform in paths | Skip §17 |

Repo override in `review-rules.yaml`:

```yaml
fast_path:
  skip_architecture_below_files: 5   # default 5; set 0 to disable
  skip_ci_on_docs: true              # default true
```

## Announce

After classification, print one line in chat:

> **Fast path:** lockfile-only — mechanical review; CI/architecture/security checklists skipped.

> **Fast path:** docs-only (3 files) — CI skipped; security checklist skipped (secret scan only).

> **Fast path:** standard · 4 files — architecture lens skipped.

Record in Phase 4 summary **Notes**:

`- Fast path: markdown-only; CI skipped; sec checklist skipped`

## Change classification (automation)

After profile selection, set **`change_classification`** in `review_metrics` and announce when non-production:

| Classification | When |
|----------------|------|
| **Documentation** | All changed files are `.md`, `.mdx`, `.rst`, `docs/**`, README, CHANGELOG |
| **Templates** | Only merge request templates, issue templates, skill/workflow templates |
| **Metadata** | Lockfiles, `package.json` version-only, labels, `.gitignore`, LICENSE — no runtime source |
| **No executable runtime code** | Docs + templates + examples/JSON fixtures — nothing compiled or executed in prod |
| **Production code** | Any runtime source, migrations, service config in boundary |
| **Mixed** | More than one of the above |

Print in Phase 1 announcement and executive summary:

> **Change classification:** Documentation · no executable runtime code

Docs-only and metadata-only MRs enable fast path **and** future automation (skip security/arch tables).
When boundary is docs-only but references disagree with code **outside** the diff, classify drift per
`reference/executive-summary.md` §Documentation drift — do not inflate to High without implementation evidence.

## Lockfile-only EXIT (minimal path)

When **every** changed file is lockfile/generated:

1. Confirm no companion manifest with logic change in the **same MR** (e.g. `package.json` + lockfile →
   **not** lockfile-only — use standard with dependency focus).
2. Run **short path:** Phase 1 steps 1–2 → fast-path classify → Phase 2 spot-check (CVE/advisory on
   manifest if changed, secret scan) → Phase 5 mechanical executive summary → Phase 2→3 gate → posting
   if user wants.
3. **Recommendation:** ✅ Approve if no CVE/regression signal; 💬 Comment if pipeline failed and MR
   includes manifest version bumps worth noting.

Do **not** skip Phase 3 posting confirmation when user asked to post.

## Bot-authored PR fast path (Renovate / Dependabot / codegen)

When **bot-dependency** profile matches:

1. **Verify the bump** — semver range, single-package focus, changelog/release notes for breaking changes.
2. **Run dependency/CVE check** — non-negotiable on new versions
   (`reference/finding-gates.md#non-negotiable-checks-pipeline-step-6`).
3. **Skip** — architecture lens (§16), style nits, broad performance pass unless the bump touches runtime code paths.
4. **Codegen MRs** (OpenAPI, protobuf, graphql-codegen) — verify generated diff matches source spec change; flag manual edits inside generated folders.
5. **Recommendation:** ✅ Approve when CI green + no Critical CVE; 💬 Comment when major semver without migration notes.

Announce: *"Fast path: bot-dependency — CVE/changelog focus; architecture/style skipped."*

**Mixed MR exception:** when `bot_has_human_commits: true`, the Phase 2 review engine splits the
boundary by commit author. Only skip §4/§8/§9/§16 for files **exclusively** changed by bot commits.
Files touched by human commits (even if also touched by the bot) receive standard review.

## README-only

Treat as **docs-only** when the only changed files are `README*`, `docs/**`, or changelog markdown —
**CI skipped** per profile table.

## Security exception

**Never** skip on standard/production MRs:

- Secret/credential scan on all changed text
- Hard floors (injection, auth) when production code present
- Execution path gate and review principle

`skip_security_checklist` means skip the **full §2 rubric**, not skip reading the diff.

## Re-review

Re-classify fast path on every run from the **current** boundary — do not inherit skips from a prior
review if the new diff adds production code.
