# System Design Spec — B6: cross-run repo-convention capture

**Readiness: Ready with open questions**

Revision 5. Implements
[2026-09-30-b6-convention-capture-architecture-review.md](2026-09-30-b6-convention-capture-architecture-review.md)
("Approved with conditions", 6 conditions).

## Revision history

**Revision 1** proposed a standalone run-log index reader, a PR-history signal reader, an aggregator, a
conflict-check, and a proposal writer that opened a PR directly against a new `learned-conventions.md` —
decoupled from `orchestrator.md`'s per-task loop, with only prose-level enforcement of the
injection-resistant synthesis rule.

**Round 1** (Security Architect, SRE, Software Architect) found: the proposal-writer bypassed this
skill's entire write-authority doctrine (no independent Reviewer check before a human saw the diff);
Condition 3's "no code check possible" framing was wrong (a deterministic similarity check is genuinely
possible here, unlike B4/B5's cases); the central reconciliation overstated its case and missed a second
existing content channel; the run-log index reader was unbuildable (no field identifies which repo a log
belongs to; real cost scales with the whole account's history); the idempotency check was self-contradictory;
no rate-limit strategy existed; the skill-identity placement was self-contradictory.

**Revision 2** fixed: routed the proposal through the ordinary Builder/Reviewer/adjudication/lifecycle-gate
pipeline instead of Orchestrator self-certification; deleted the run-log index reader, replaced with a
direct PR query; added a rate-limit/backoff strategy; corrected the idempotency key to a PR-number set;
resolved the skill-identity question (a task-generation trigger *for* `loop-task-implementer`, not a new
skill); widened the conflict-check to also cover already-accepted entries; disclosed the doctrine blind
spot honestly.

**Round 2** (Security Architect, SRE, Software Architect) confirmed the structural routing fix and the
run-log-reader deletion both hold, but converged on: the "mechanical Reviewer investigation" was asserted
without an algorithm, threshold, output field, or capability grant; the synthesized principle field lacked
untrusted-content framing and Rule 5 redaction; nothing told the Reviewer which tasks needed this special
investigation; the task-intake mechanism (how a candidate reaches task selection) was never specified; the
"this skill's own PRs" population scope was unbuildable (one shared human author, inconsistent branch
prefixes, no label mechanism).

**Revision 3** fixed: named a similarity-check algorithm (n-gram Jaccard, threshold 0.4) with an
evidence-prefix convention and a new `reviewer.md` capability grant; added untrusted-content framing plus
Rule 5 redaction for the synthesized principle, mirroring B1's `resolved_summary`; gated the Reviewer
investigation on the diff touching `learned-conventions.md`'s `## Proposed` section (a structural trigger,
no schema field); routed task-intake through a filed GitHub Issue consumed by `backlog-runner`'s existing
`tracker_query`; scoped the PR population to all of this repo's history; corrected the idempotency key to
`(category, PR-number set)`.

**Round 3** (Security Architect, SRE, Software Architect) found the deepest, most consequential defects
yet, converging on the same underlying pattern from three angles: **inventing a second new intake/dedup
mechanism reproduced the exact class of bug round 1 already found and fixed once, just moved one level
down.** Specifically:

- **SRE, the headline finding**: the `(category, PR-set)` dedup key and the "conflict-check against
  Accepted" fix, run together, reproduce the *exact* failure they claim to close — for the steady-state
  **success** case, not an edge case. A genuinely recurring, already-accepted convention keeps getting
  cited in new PRs over time; the scan window is a sliding 90-day/50-PR bound, so the cited PR set ages
  and shifts pass to pass; exact-set-equality against a stale prior key never matches again; the
  conflict-check is contradiction-detection only, which cannot recognize agreement/restatement of an
  already-accepted principle. Net effect: **an accepted, real, recurring convention would spawn a fresh
  duplicate Issue every subsequent scan pass, forever** — the opposite of "capture once."
- **Software Architect, independently**: the widened conflict-check depends on entries actually existing
  under `## Accepted` — but nothing in the entire pipeline ever writes there. The Builder's only specified
  write is to `## Proposed`; merging the PR leaves the entry under `## Proposed` permanently (a
  state-machine label, "ACCEPTED," with no corresponding file mutation). The conflict-check's new target
  is perpetually empty, so it always trivially passes — not because no conflict exists, but because there
  is nothing there to check.
- **SRE, plus Security Architect, on the Issue-filing mechanism**: GitHub Issue creation was asserted as
  "an existing capability class this skill's ecosystem already has via `backlog-runner`" — false against
  the real capability matrix, which documents `backlog-runner` only ever *reading*/*querying* tickets,
  never creating them; no Issue-creation capability, row, or degraded path exists anywhere in this
  skill-framework. Separately, even a correctly-configured `backlog-runner` deployment filters its
  `tracker_query` by a repo-specific label/filter this design never applies to the Issues it files — so a
  filed Issue could silently never match any real deployment's query, undetectably.
- **Security Architect, on the similarity check**: the comparison spec ("title/body/**review-comment**
  text") directly contradicts the capability grant actually stated ("title/body/**diff** text" — review
  comments never granted). The check as specified cannot be performed. Separately, the design's own claim
  that this "mirrors B4's own comment-content framing" is backwards: B4's actual, more conservative
  precedent deliberately **prevents** the Reviewer from ever reading raw untrusted comment text, handing it
  only a fixed, sanitized literal instead — B6 required the *opposite* (the Reviewer directly fetching and
  parsing an entire historical PR's raw text), the first time this codebase would have a Reviewer ingest
  large, attacker-influenceable freeform text as a first-class investigation input. And the Reviewer's own
  resulting finding had no redaction/framing symmetric to the fix just applied to the synthesized
  principle — to justify a "closely paraphrases" verdict to a human adjudicator, the finding's evidence
  would need to quote or closely reference the very raw text Condition 5 exists to keep out of durable
  artifacts.

**Round 4** (Security Architect, SRE, Software Architect) found revision 4's redesign real progress in two
respects — deleting the Issue-filing/`backlog-runner` dependency and separating the Reviewer from raw-text
reading both genuinely hold — but converged, **independently, three times**, on the same underlying
defect (the third occurrence of this exact bug class in this ticket's history): **the similarity-check
script's single stated signature (fetch PR review-comment text, compare against a supplied string) cannot
perform the conflict-check's actual required operation (compare two already-in-hand category labels,
no fetch)** — "one script, two callers" was false as specified. Additional convergent/complementary
findings:

- **SRE**: the category label (2–4 words, e.g. "cite-evidence-inline") is too short for reliable
  similarity matching in *either* direction — an LLM paraphrase of the same real pattern breaks nearly
  every trigram (false negative, reintroducing round 3's "recurring convention spawns duplicates forever"
  bug from a new angle), while two genuinely unrelated conventions sharing one incidental phrase can
  exceed the 0.4 threshold on a 2–3-trigram string (false positive, silently discarding a real candidate
  with zero surfaced evidence). Separately: no durable destination was ever named for the report — the
  design claimed to "genuinely mirror `architecture-review`'s own report-only model... for real," but
  `architecture-review`'s actual deliverable is a named, persistent file (`ARCHITECTURE_REVIEW_REPORT.md`)
  with stated `safe-output.md` escaping — B6's report had neither, making it structurally *worse* than
  round 3's "Issue sits unpicked" gap: an ephemeral report can be lost with no artifact left for anyone,
  including the human who ran the scan, to ever notice. And the Capacity section's "small, expected low"
  was unearned given the design's own comparison mechanism (before this revision's fix) would have made
  each of N existing-entry comparisons a live network fetch, growing unboundedly with the file's own
  lifetime size.
- **Security Architect**: the "text not reproduced here" evidence format copies B4's fixed-breadcrumb
  *format* without the property that makes B4's version sufficient — a B4 finding is self-contained (the
  Reviewer independently derives the finding's substance from its own code investigation; the citation is
  a locator, not the content), whereas a B6 similarity-check finding has *no* substance besides the bare
  score, so redacting the compared text redacts the entire finding, not a mere breadcrumb — a human cannot
  actually adjudicate "closely paraphrases" without independently reading the cited PR themselves, unlike
  `regression_gate`'s trivially re-derivable pass/fail. Separately: the script's own failure-mode output
  discipline (never leaking fetched text via an exception/log) and an explicit Reviewer-side prohibition on
  falling back to reading raw text if the script fails were both unspecified — the same "asserted vs.
  enforced" gap this codebase already found and fixed once for B4.
- **Software Architect**: task-intake was relabeled, not closed — round 2's real question ("how does a
  report row's ~4 fields become a valid 15-field `implementation_task`?") was never answered; removing the
  automatic mechanism didn't specify what a human is actually supposed to do instead, and neither of this
  skill's two real intake paths (`implementation-planner`'s evidence requirements; the "legacy bypass,"
  explicitly characterized elsewhere in this codebase as "ungoverned") was named or reconciled.

Fixed below, concretely: (1) the similarity-check script is split into two explicitly distinct functions —
a pure, local, no-fetch `score_text_pair` (two strings in, one score out) for the conflict-check, and a
separate `fetch_and_score` (PR-number list in, network fetch, scores out) for the Reviewer's
re-verification — never described as "one script" again; (2) the dedup/conflict-check comparison surface
is switched from the short category label to the full synthesized principle sentence (already present in
the file for every existing entry), giving `score_text_pair` a much richer, more stable comparison surface
that closes both the false-negative and false-positive failure modes SRE found; (3) a concrete, durable
report destination is named, following `architecture-review`'s actual precedent literally, including
`safe-output.md` escaping; (4) the evidence-quality gap is closed honestly, not by claiming false
self-containment — B6's citation-only evidence is now stated as consistent with this codebase's own
existing citation norm (a human can and should open the cited PR to verify, the same way any
externally-cited finding in this codebase already works), not claimed to be independently sufficient
without that step; (5) explicit script failure-mode and Reviewer-fallback-prohibition rules are added; (6)
the task-intake path is named concretely — the legacy `implementation_task` bypass, with an explicit
accounting of why using it here is sound despite its "ungoverned" characterization elsewhere (it only
bypasses upstream *planning* evidence, never the Builder/Reviewer/adjudication/lifecycle-gate loop, which
this design's very first structural fix already guarantees runs regardless of intake path).

**Revision 4's own redesign** (summarized here for context, then corrected further by revision 5 above)
removed two mechanisms that had each independently failed once under review — the automatic
Issue-filing/`backlog-runner` intake, and the PR-number-set/Accepted-section dedup scheme — rather than
patching them a third time. Both were replaced with simpler mechanisms reusing only what's already proven
to work:

1. **Task intake is now a pure report, not an automatic write of any kind** (no Issue, no PR, no new
   capability). The convention-scan trigger's sole output is a markdown report listing cleared, novel
   candidates — genuinely mirroring `architecture-review`'s own report-only model this time, not merely
   citing it. A human reads the report and decides whether to hand any given candidate to a
   `loop-task-implementer` invocation as its task — exactly the same way every prior gap-backlog ticket's
   own task reached this skill in the first place (a human supplied it). This needs zero new write
   capability and has no dependency on `backlog-runner` being deployed/configured at all.
2. **Dedup/duplicate-recognition for already-captured conventions no longer uses PR-number matching.**
   It reuses the *same* deterministic similarity-check primitive built for Condition 3 (see below),
   applied to a much shorter, more stable piece of text — the category label itself — against every
   existing entry already sitting in `learned-conventions.md`'s single running list. This sidesteps the
   sliding-window/exact-match problem entirely: an entry that's already in the file, however it got there,
   is checked directly; there is no separate "Accepted" section requiring a promotion step nothing ever
   performs.
3. **The similarity-check corpus is now fixed to one real, consistently-named source (PR review-comment
   text — the actual signal this design has always said it wants), and the capability grant matches it
   exactly**, closing the corpus/capability contradiction.
4. **The Reviewer never fetches or reads raw historical text at all.** The similarity check is a small,
   named, deterministic script (matching B3's `validate_repro_command` precedent, not B4's — the citation
   is corrected) that the Reviewer *runs*, scoped to the specific, already-cited PR numbers only, producing
   a bare numeric score — never open-ended reading of arbitrary PR content. This closes both the
   corpus/capability contradiction and the "this isn't really B4's precedent" finding at once: it's
   actually closer to B3's own narrow-tool precedent, correctly cited now.
5. **The Reviewer's own finding never quotes cited text**, mirroring B4's fixed-breadcrumb discipline
   exactly: the evidence is a bare score and PR reference, never a rendering of the PR's own content —
   closing the symmetric-redaction gap.

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| **Convention-scan trigger** (new — explicit invocation, report-only) | A separate, deliberately-invoked, read-only procedure producing a markdown report of cleared, novel candidate conventions | New reference doc + script; writes nothing to any repository — genuinely report-only, mirroring `architecture-review`'s own model for real (round-4 fix — no Issue, no PR, no new write capability) | Not a new skill: it produces information a human acts on, the same shape as every other report-only leaf in this skill-framework |
| **PR-history scanner** | Directly queries **all** of this repo's closed/merged PRs within the bounded scan window | Read-only, existing capability class | Unchanged from revision 3 |
| **Occurrence/diversity aggregator** | Groups findings by **category** (a short, LLM-synthesized label, e.g. "cite evidence inline"), counts distinct PRs per category; also synthesizes the candidate's full principle sentence | In-memory, same pass | The category label is **display-only** (round-5 fix, corrected from a stale round-4 line this same document's own sweep missed) — the full synthesized principle sentence, not the category label, is the actual dedup/conflict-check comparison surface; see Data model |
| **`score_text_pair`** (new, **split out as its own function, round-5 fix** — closes the script-signature contradiction all three personas independently found in round 4) | A pure, local, no-network, deterministic function: two already-in-hand text strings in, one Jaccard-overlap float out. No fetch, no PR numbers, no I/O of any kind | A real, testable, versioned function — the actual comparison core both callers below share | Used by the conflict-check, comparing a new candidate's **full synthesized principle sentence** (not the short category label — round-5 fix, see Data model) against every existing entry's own stored principle sentence, already present in the file for every entry |
| **`fetch_and_score`** (new, **split out as its own function, round-5 fix**) | Given a text and a list of PR numbers, fetches each cited PR's own **review-comment text only**, computes `score_text_pair` against each, returns a bare `{pr_number: score}` map — the only function that ever touches the network or reads untrusted PR content | The one function with fetch/rate-limit exposure; matches B3's `validate_repro_command` precedent (a narrow, deterministic tool the Reviewer *runs*), correctly distinguished now from B4's judgment-based precedent | Used only by the Reviewer's re-verification call, against the task's own already-cited PR numbers — never by the conflict-check, which needs no fetch at all |
| **Conflict-check** (**mechanism corrected, round 4, comparison surface corrected again, round 5**) | Checks a candidate against: `CONTRIBUTING.md` + implicated `SKILL.md` files (explicit-textual-contradiction, unchanged), **and** every existing entry already in `learned-conventions.md`'s single list, via `score_text_pair` comparing **full principle sentences**, not the short category label (round-5 fix — a 2–4 word label was too short for reliable matching in either direction, per SRE's round-4 finding) | Read-only, no network fetch at all | The doctrine-blind-spot residual (institutional memory not in any checked file) remains disclosed, unchanged from revision 3 |
| **Task generator** — **removed as a write-capable component (round-4 fix)**; folded into the Convention-scan trigger's own report output | A cleared, non-duplicate candidate is simply a row in the report, with the fixed template as its content | No write of any kind | Was the source of round 3's two now-fixed defects (unbuildable Issue-creation capability, unverified `tracker_query` label match) — removed by deleting the mechanism, not patching it a third time |
| **Builder** (unmodified, existing role) | When a human hands a candidate row to `loop-task-implementer` as an ordinary task, implements the literal, single-entry diff to `learned-conventions.md`'s running list, using the fixed template | Existing Builder, no changes | Ordinary task, ordinary Builder, reached the same way every other task this skill has ever executed was reached — a human supplied it |
| **Reviewer, Lens A/B** (unmodified role, investigation content corrected, round 4, failure-mode discipline added round 5) | Whenever the diff touches `learned-conventions.md` (the trigger signal, unchanged from revision 3): (a) **run** `fetch_and_score` (never read raw PR text itself) against the task's own cited PR numbers; (b) re-verify citation count/diversity against threshold; (c) ordinary general scrutiny. **New, round 5**: on `fetch_and_score` failure (rate-limited past retry, malformed response), the Reviewer must **never** fall back to fetching or reading the raw PR content itself by any other means — the finding becomes `NEEDS_EVIDENCE`, full stop (Data model) | Existing Reviewer dispatch, unmodified machinery; **`reviewer.md` "may" grant is narrow and script-scoped** — "may run `fetch_and_score` against the task's own cited PR numbers," never "may fetch and read arbitrary historical PR content"; **new explicit "may not" companion rule (round 5)**: may not read cited PR content by any path other than this one function's own return value | The Reviewer's own finding, if raised, states only the bare score and PR reference — never quotes or paraphrases the cited PR's own text. **Evidence-quality honestly stated (round 5, closes Security Architect's round-4 finding)**: this citation-only evidence is *not* independently self-verifying the way `regression_gate`'s re-runnable pass/fail is — a human wanting to fully verify a "closely paraphrases" verdict should open the cited PR themselves. This is not a unique flaw: it matches this codebase's own existing norm for any finding that cites external evidence by reference rather than reproducing it (e.g. "this violates CONTRIBUTING.md's stated rule X" also requires a human to go look) — stated explicitly here rather than left implicit or falsely claimed self-contained |
| **Adjudication + lifecycle gate** (unmodified) | Same `PROPOSED_BLOCKING`/adjudication path as any other finding; same lifecycle validator before merge | Unmodified | No new machinery |
| **Scan-lease** (reuses `task_lease.py`, corrected mixing pattern) | Prevents two concurrent scan passes | Deterministic lease id | Unchanged from revision 3 |

## APIs

New read capabilities, all named explicitly: (1) the PR-history scanner's direct closed/merged-PR query;
(2) a small, one-shot default-branch query for the scan-lease's `base_branch` argument; (3)
`fetch_and_score`'s own PR review-comment fetch — the **only** function with network/fetch capability;
`score_text_pair` (Components) is pure local computation, no capability needed at all (round-5 fix —
"one script, one capability, two callers" was false as specified; there are now two functions, only one of
which has any capability requirement). **No new write capability of any kind** (the Issue-creation
capability round 3 asserted without documentation is removed by removing the mechanism that needed it).

## Events

None new — unchanged from prior revisions. The scan trigger, aggregator, conflict-check, and both
similarity-check functions never write to any run log or repository file. A human-initiated task, once
handed to `loop-task-implementer`, produces ordinary events exactly like any other task.

## Data model

**Scan window**: unchanged — `min(50 most recent closed/merged PRs, PRs within the last 90 days)`,
scoped to all of this repo's PR history.

**Occurrence/diversity threshold**: unchanged — at least 3 occurrences across at least 3 distinct PRs.

**Central reconciliation**: unchanged from revision 3 (prose convention, not code-enforced impossibility;
`backlog-runner`'s morning summary explicitly considered and ruled out as a signal source, correctly
described as a status table, not verbatim rebuttal content).

**`learned-conventions.md`'s structure**: a single running list — no `## Proposed`/`## Accepted` split.
Merging a task's PR *is* the acceptance signal, exactly like every other PR this skill produces. Each entry
carries its own category label (for human readability/browsing only, **no longer the dedup key — round-5
fix**) and its full principle sentence (the actual dedup comparison surface, round-5 fix):

```markdown
# Learned conventions

Cross-run patterns proposed by loop-task-implementer's convention-capture procedure (gap-backlog B6).
Every entry below was implemented as an ordinary task, reviewed, and merged — the same discipline as any
other change in this repository.

### <one-sentence, Orchestrator-synthesized principle — never verbatim historical text>

**Category:** <short label, e.g. "cite-evidence-inline"> — for human browsing only; not used for
duplicate-recognition (round-5 fix — see Conflict-check below)
**Evidence:** <PR #, PR #, PR #> (3 distinct PRs)
**Scope:** <the skill(s)/area this pattern was observed in>
```

**Conflict-check against existing entries, comparison surface corrected (round-5 fix, closes the
convergent round-4 finding from all three personas)**: for a new candidate, run `score_text_pair` — a
pure, local, no-fetch comparison — between the candidate's **full synthesized principle sentence** and
every existing entry's own stored principle sentence (not the short category label, round-4's choice,
found by SRE to be too short — 2–4 words, 0–2 trigrams — for reliable matching in either direction: an
independent paraphrase of the same real pattern could fall below threshold, false-negative, recreating
round 3's "duplicates forever" bug from a new angle; two unrelated conventions sharing one incidental
short phrase could exceed threshold, false-positive, silently discarding a genuinely novel candidate with
no surfaced evidence). A full principle sentence is long enough to give the trigram-Jaccard comparison a
stable, meaningful surface in both directions. If the score against any existing entry exceeds 0.4, treat
the candidate as already-captured and discard it (bare count only). This is real, local, and network-free
— `score_text_pair` never fetches anything, closing SRE's round-4 Capacity finding too (see Capacity).

**Textual-contradiction check** (unchanged mechanism): `CONTRIBUTING.md` + implicated `SKILL.md` files
only, explicit contradiction only. The doctrine-blind-spot residual is disclosed identically to prior
revisions.

**The two similarity-check functions, concretely specified and now genuinely distinct (round-5 fix, closes
the script-signature contradiction all three personas independently found in round 4)**:

- **`score_text_pair(text_a: str, text_b: str) -> float`** — pure, local, deterministic, no network, no
  fetch. Algorithm, fully pinned: word-level trigrams, lowercase-folded, common markdown boilerplate
  (checkbox syntax, HTML comments, template headers) stripped before tokenizing, Jaccard overlap of the
  trigram sets. Used by the conflict-check (full principle sentence vs. full principle sentence, above).
- **`fetch_and_score(text: str, pr_numbers: list[int]) -> dict[int, float]`** — the only function that
  touches the network: fetches each cited PR's own **review-comment text only** (never title/body/diff —
  those aren't where a recurring Reviewer-finding/rebuttal pattern actually lives), then calls
  `score_text_pair(text, fetched_comment_text)` per PR, returning a bare `{pr_number: score}` map — the
  text itself is never returned to the caller. Used only by the Reviewer's re-verification, against the
  task's own already-cited PR numbers.
- **Threshold**: 0.4 for both functions, still an explicitly unvalidated starting point (Open questions) —
  the same number, but now applied to two comparably-sized text inputs (full sentences on both sides in
  both call sites), not one long text against one short label as round 4 had.
- **Evidence-prefix convention** (unchanged mechanism, evidence-quality honestly reframed — round 5): a
  Reviewer finding raised from `fetch_and_score` has its `evidence` field begin with the literal prefix
  `"convention_capture_similarity: "`, followed **only** by the bare score and PR reference (e.g.
  `"convention_capture_similarity: overlap 0.52 against PR #123 exceeds 0.4 threshold — see PR #123
  directly for context, text not reproduced here"`) — never a quotation or paraphrase of the PR's own text.
  **This is not claimed to be independently self-verifying** (round-5 correction of round 4's overclaim,
  per Security Architect's finding): unlike `regression_gate`'s trivially re-runnable pass/fail, a human
  fully verifying "closely paraphrases" needs to open the cited PR themselves — stated honestly as
  consistent with this codebase's existing norm for any citation-based finding, not a new or unique gap.
- **`reviewer.md` capability grant, narrow and script-scoped**: "may run `fetch_and_score` against the
  task's own cited PR numbers" — never "may fetch and read arbitrary historical PR content." Correctly
  cited against B3's `validate_repro_command` precedent (a narrow, deterministic tool the Reviewer *runs*),
  not B4's open-ended-judgment precedent.
- **New companion "may not" rule (round 5, closes Security Architect's round-4 finding)**: the Reviewer may
  **not** read cited PR content by any path other than `fetch_and_score`'s own return value — no fallback
  to manual fetching if the function fails or errors.
- **Script failure-mode discipline (new, round 5, closes Security Architect's round-4 finding)**:
  `fetch_and_score`'s own implementation must never include fetched text in an exception message, log line,
  or any other output besides the documented `{pr_number: score}` return value — the same "never leak the
  compared content" discipline applied to its normal return path must also hold on its failure path.
- **Rate-limit/fail-closed** (unchanged): retry-with-backoff; on repeated failure, `NEEDS_EVIDENCE`, never
  silently skipped, and never triggering the prohibited manual-fallback path above.

**Untrusted-content framing for the synthesized principle** (unchanged from revision 3): Rule 5 redaction
before the principle is embedded anywhere, mirroring `resolved_summary`'s precedent.

**Scan-lease**: unchanged from revision 3 — `derive_lease_id(repo, base_branch,
f"convention-capture-scan:{scan_window_end_date}")`, matching B1's real mixing pattern.

**Rate-limit/backoff for the PR-history scanner**: unchanged from revision 3, with the bare skip-count
observability signal.

## State machines

| Entity | States | Transitions | Notes |
|--------|--------|-------------|-------|
| A candidate convention | `SCANNED → AGGREGATING → {BELOW_THRESHOLD (terminal, discarded, bare count only), THRESHOLD_MET} → SIMILARITY_CHECKED_AGAINST_EXISTING_ENTRIES (via `score_text_pair`, full principle sentences — round-5 fix) → {ALREADY_CAPTURED (terminal, discarded, bare count only), NOVEL} → CONTRADICTION_CHECKED → {CONTRADICTS_INSTRUCTIONS (terminal, rejected, bare count only), CLEAR} → REPORTED` (terminal — a row in the durable report file, Data model — **no automatic write of any kind past this point**) | Once reported, a human may hand the candidate to `loop-task-implementer`, manually assembling a legacy `implementation_task` envelope from the report row's content (Rollout, Open questions — the concrete intake path, round-5 fix), which then runs the completely standard `task_selected → builder_dispatched → review_dispatched → adjudicated → pr_opened → {human MERGES, human CLOSES}` sequence — this part of the state machine is not this design's own | `REPORTED` — no automatic intake mechanism of any kind; a human's own decision to act on a report row is the real "intake" |

## Consistency

Unchanged — scan-lease is strong (flock-based), PR-history reads are eventual.

## Retries & idempotency

| Operation | Idempotent? | Retry / backoff strategy |
|-----------|-------------|----------------------------|
| Scan pass | Idempotent by construction — re-running the scan against an unchanged set of already-captured entries always discards the same already-known conventions via `score_text_pair` against their full principle sentences; nothing is ever double-written since nothing is written automatically at all | Scan-lease prevents concurrent double-runs; report regeneration is inherently safe to repeat |
| PR-history scanner read | Not naturally rate-limit-safe | Retry-with-backoff; skip-and-continue, bare skip-count logged |
| `score_text_pair` (conflict-check) | N/A — pure local computation, no I/O, cannot fail on rate limits | None needed |
| `fetch_and_score` (Reviewer) | Not naturally rate-limit-safe | Retry-with-backoff; on repeated failure, `NEEDS_EVIDENCE` (Data model), with the explicit no-manual-fallback rule |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| PRs scanned per pass | Bounded at `min(50, 90 days)`, all-repo scope | Direct GitHub query |
| `score_text_pair` invocations per pass (conflict-check) | One per candidate against every existing `learned-conventions.md` entry — **grows with the file's own lifetime entry count, genuinely unbounded over the repo's life, unlike the scan window** (round-5 honest correction of round 4's unearned "small, expected low" claim, per SRE's finding) — but each invocation is now pure, local string comparison with **zero network cost**, so even hundreds of entries remain cheap CPU work, not a rate-limit or I/O concern. This is the real answer to the capacity question: the *count* grows, but the *per-comparison cost* is negligible, because round 5's fix made this function fetch-free | Direct consequence of the `score_text_pair`/`fetch_and_score` split (round 5) |
| `fetch_and_score` invocations per pass (Reviewer side) | At most 3 per candidate task (one per cited PR), only when a human has actually acted on a report row | Bounded by the occurrence threshold, and only incurred per human-initiated task, not per scan pass |
| Report volume | Expected low, unmeasured | No real scan has ever run yet |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| PR-history-read capability absent | Skip the scan entirely, report the gap |
| PR-history scanner read rate-limited mid-scan | Retry-with-backoff, skip-and-continue, bare skip-count logged |
| `score_text_pair` (conflict-check) fails | Cannot fail on I/O grounds (pure local function); a malformed input is a bug, not a runtime failure mode |
| `fetch_and_score` (Reviewer) rate-limited | `NEEDS_EVIDENCE`, plus the explicit no-manual-fallback rule (Data model) |
| A deliberately-seeded, multi-PR pattern reaches the occurrence threshold | Mitigated by the synthesis rule plus the Reviewer's own mechanical similarity re-check and general judgment — a bounded, disclosed residual |
| Conflict-check misses an unwritten institutional-doctrine violation | Named, accepted residual, precisely scoped |
| Two scan passes race | Prevented by the scan-lease |
| The report file is lost or never read (round-5 fix, closes SRE's round-4 finding) | The report is now a **durable, named file** (Data model), not ephemeral chat output — even if a human doesn't act on it immediately, it persists on disk for later review, the same as every other spec/report artifact this session's own doctrine chain already produces |
| A reported candidate is never acted on by a human | Explicitly acceptable — the ticket's own "proposals only" model, now with a durable artifact rather than an ephemeral one |
| A genuinely recurring, already-merged convention keeps appearing in new PRs | **Does not produce repeat proposals** — `score_text_pair` against full principle sentences (round-5 fix, replacing round 4's too-short category-label comparison) recognizes it as already-captured on every subsequent pass, regardless of which specific PRs currently evidence it |

## Observability

Candidates discarded below threshold, candidates discarded as already-captured (bare count), candidates
rejected by the contradiction-check (bare count), candidates reported (bare count, with the report file
itself being the actual content artifact a human reads), a bare "N PRs skipped due to rate limit" count
per scan pass.

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| 1 | New `docs/skill-framework/learned-conventions.md` (single running list, empty); PR-history scanner (all-repo scope); the small default-branch query; scan-lease reuse | No flag — net-new, additive |
| 2 | Aggregator (category-tagged, category label for display only); `score_text_pair` and `fetch_and_score` as two distinct functions (round-5 fix); the corrected conflict-check (contradiction-check + `score_text_pair`-against-existing-entries on full principle sentences) | Depends on Phase 1 |
| 3 | Convention-scan trigger's report output, written to a **durable, named file** — `docs/superpowers/specs/<date>-b6-convention-scan-report.md` (round-5 fix, closes SRE's round-4 finding): a named, persistent file, escaped/redacted per `safe-output.md`'s rules — matching the *durability property* `architecture-review`'s own report (a fixed-name file, never ephemeral output) demonstrates, though the specific naming convention here follows this same session's own established `docs/superpowers/specs/` pattern for every other report artifact this doctrine chain produces, not `architecture-review`'s own fixed filename (round-5 correction of an overclaimed attribution, SRE's round-5 non-blocking finding). **Never auto-committed** (matching the ticket's own explicit "proposals only" criterion) — a human decides whether/when to commit it alongside acting on any candidate, the same discipline this session already applies to every design-doc artifact | Depends on Phase 2 |
| 4 | Reviewer investigation content: the narrowed `reviewer.md` "may"/"may not" grants (Data model), the fixed-breadcrumb evidence convention with its honestly-stated evidence-quality caveat, the rate-limit/fail-closed/no-fallback behavior, gated on the diff touching `learned-conventions.md` | Depends on Phase 3's report format being defined |
| 5 | First real invocation as a manual dry run against this repo's actual closed/merged PR history | Verification |

## Open questions

1. The occurrence threshold (3/3) and the similarity-check overlap threshold (0.4) remain unvalidated
   against real data — considered starting points.
2. The conflict-check's disclosed blind spot for unwritten institutional doctrine — mitigated by Reviewer
   judgment only for generically-suspicious cases, not eliminated for this specific residual.
3. Whether a human, having read the report, actually reliably follows through — this design deliberately
   makes that a manual, out-of-band step rather than assume any particular follow-through rate; genuinely
   unmeasured, and honestly so.
4. **Task-intake path, named concretely (round-5 fix, closes Software Architect's round-4 finding)**: a
   human acting on a report row manually constructs a **legacy `implementation_task` envelope**
   (`scripts/registry/composition_contracts.yaml`'s 15 real fields: `task_id, scope, acceptance_criteria,
   request, repo_root, target, level_hint, specialist_inputs, test_framework_hint, run_tests,
   max_files_per_run, deadline, session_token_budget, output_dir, regression_gate`) — using the report
   row's principle/evidence/scope as the source material for `request`/`acceptance_criteria`/`scope`, real
   but small manual work (a few sentences), not automatic. This bypass is elsewhere characterized in this
   codebase as "ungoverned" relative to `implementation-planner`'s own richer upstream-evidence
   requirements — using it here is judged sound specifically because that characterization concerns
   skipped *planning* evidence, never the actual Builder/Reviewer/adjudication/lifecycle-gate loop, which
   this design's very first structural fix (Revision history) already guarantees runs identically
   regardless of which intake path supplied the task. Genuinely unvalidated end-to-end (no real
   convention-scan candidate has ever been hand-converted into a task yet) — an honest, disclosed gap, not
   a claimed closure.
