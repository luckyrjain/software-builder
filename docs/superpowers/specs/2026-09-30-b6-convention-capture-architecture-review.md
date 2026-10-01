# Architecture review — B6: cross-run repo-convention capture

**Decision: Approved with conditions**

Sound in shape — reuses `architecture-review`'s own already-precedented "propose, never mutate, human
decides" model rather than inventing a new one — but this ticket's real weight sits almost entirely in
what its M-sizing correctly anticipates and its one-line acceptance criteria understate: a genuinely new
cross-run read capability with no existing precedent, and the first mechanism in this repo whose sole
output (a proposed durable rule) is synthesized FROM untrusted historical content rather than merely
evaluated against it. Six conditions need closing before implementation.

## Architecture decision

Five coupled pieces:

1. **A new multi-run read/aggregation capability.** The Orchestrator — already the sole actor with
   run-log read/write access (`reference/run-log.md`: "Only the Orchestrator reads or writes it") — gains
   a function to scan its own historical run logs within an explicit, bounded window (never unbounded
   "all history ever") looking for a repeated pattern.
2. **A concrete occurrence/diversity threshold**, not a single-incident trigger: a candidate convention
   must recur above a stated minimum count across a stated minimum number of *distinct* tasks/PRs, never
   generalized from one run's own idiosyncrasy.
3. **A new, dedicated human-approved proposal target file** (no existing file — not a repo-root
   `CLAUDE.md`, which doesn't exist; not `CONTRIBUTING.md`, whose stated purpose is contributor/PR process
   — serves this today) — modeled directly on `architecture-review`'s own report-only, non-mutating shape:
   the Orchestrator opens a PR proposing the addition, a human reviews and merges it themselves, never
   auto-committed.
4. **An explicit, enumerated conflict-resolution check**: before any candidate is ever proposed, check it
   against a concretely-named set of "repository instructions" files — never a diffuse, unenumerated class
   — and if it conflicts with anything already stated there, it is never proposed at all (not soft-flagged
   for a human to adjudicate; the repo instructions win outright, per the ticket's own acceptance
   criterion).
5. **An injection-resistant synthesis rule**: the proposal's own wording must be an Orchestrator-synthesized
   generic principle, cited against evidence (task/PR references), never a verbatim rendering of the raw
   historical content that produced the pattern.

## Risks

| Risk | Section | Severity | Notes |
|------|---------|----------|-------|
| A bad-faith contributor could deliberately seed the same rebuttal/finding/style pattern across many distinct tasks/PRs over time, specifically to manufacture a "learned convention" candidate that nudges a distracted human reviewer into approving something they wouldn't accept if stated plainly and attributed to its actual source | Security | Blocking | This is the ticket's central novel risk — the first mechanism in this repo whose output is *synthesized from*, not merely evaluated against, untrusted historical content across many runs. See Conditions §1, §3 |
| No stated occurrence/diversity threshold — a single, idiosyncratic incident (a one-off Reviewer nitpick, a rebuttal specific to one task's own context) could be generalized into a proposed durable rule with no repeat-and-diversity evidence behind it | Failure modes | Blocking | See Conditions §1 |
| "Conflicts with repo instructions resolve to the repo instructions" has no concrete target today — the real codebase concept is a diffuse, unenumerated *class* of files (any in-repo agent-instructions file), not one canonical file a conflict-check can be run against | Architecture decision | Blocking | See Conditions §2 |
| Unbounded cross-run scanning cost as this repo's run-log history grows without limit over the project's lifetime | Scale limits | Conditional | See Conditions §4 |
| A proposal artifact that verbatim-quotes historical task text, rebuttal content, or (per gap-backlog B1) human free-text clarify-interview answers risks landing sensitive or PII-adjacent content in a durable, public-repo file — a data-exposure vector distinct from and broader than B4's own (which was scoped to one PR's comments, not this repo's entire run history) | Security / Operability | Conditional | See Conditions §5 |

## Scale limits

| Dimension | Breaks down at | Evidence |
|-----------|-----------------|----------|
| Number of historical run logs scanned per proposal-generation pass | Grows unboundedly with this repo's own lifetime run count if the scan window is "all runs ever" rather than a stated recency/count bound | `scripts/run_log.py` has no existing cross-run aggregation function to benchmark against — this is genuinely new cost, not an extension of measured existing cost (Conditions §4) |
| Proposal volume a human must review | A badly-tuned occurrence threshold could produce a stream of low-value proposals, imposing a real, if modest, ongoing review burden on a solo maintainer | Not addressed by the ticket itself; worth naming as a real operability cost, not assumed free |

## Failure modes

| Failure mode | Detection | Recovery | Notes |
|--------------|-----------|----------|-------|
| A single-incident pattern is mistakenly generalized into a proposed rule | Requires the occurrence/diversity threshold to actually be enforced, not just stated as intent | Below-threshold candidates are never proposed at all | Must be a concrete, checkable number, not "when it seems like a pattern" (Conditions §1) |
| A candidate convention silently conflicts with an existing, already-stated repository instruction | Requires the conflict-check to run against a concretely enumerated file set | Conflicting candidates are never proposed, full stop — the repo instructions win outright, exactly matching the ticket's own acceptance criterion | Must name the actual files checked, not a description of a class (Conditions §2) |
| A deliberately-seeded, multi-task pattern reaches proposal despite passing the occurrence/diversity threshold (the threshold alone doesn't distinguish organic repetition from manufactured repetition) | The synthesis rule (Orchestrator-authored generic principle, cited evidence, never verbatim historical text) is the actual mitigation — it doesn't prevent a seeded pattern from reaching proposal, but it prevents the seeded text itself from becoming the proposed rule's own wording, and the cited evidence lets a human trace and discount a suspicious cluster of citations from the same actor/timeframe | Requires the human reviewer to actually look at the cited evidence, not just approve the proposed wording at face value — an honest, disclosed limitation, not a fully-closed one | This is the same class of irreducible-ambiguity acceptance this session used for B5's Condition 2 — name it explicitly rather than claiming perfect closure |

## Security

| Concern | Trust boundary / data flow | Blast radius | Notes |
|---------|------------------------------|---------------|-------|
| Untrusted historical run-log content (task text, rebuttal text, human clarify-interview free-text answers) shapes the wording of a proposal a human will read and may approve | Read: Orchestrator's own existing run-log access, no new boundary. Synthesis: genuinely new — the first place in this repo where untrusted content across many runs is distilled into new proposed prose rather than evaluated against a fixed rubric | If unclosed: a human could be nudged into approving a manufactured "convention" they'd reject if they saw its actual, unsynthesized source | The ticket's single most important risk (Conditions §1, §3) |
| The proposal artifact itself may contain sensitive/PII-adjacent content lifted from historical task text | Write: same PR-creation capability the Orchestrator already has elsewhere, no new capability — but a broader content-exposure surface (many runs' worth of history, not one PR's comments) | A public-repo proposal file is a durable, indexed, public artifact — broader and more permanent exposure than a single PR comment thread | See Conditions §5 |
| The multi-run read capability itself | Orchestrator-only, same actor that already writes every run log it would read | Contained — no new actor gains access; this is a capability *expansion* (single-run to multi-run) for an actor that already has full access to each individual file, not a new trust boundary | Correctly scoped in the design description; not itself a blocking concern |

## Operability

| Concern | Owner | Operating cost | Notes |
|---------|-------|------------------|-------|
| Reviewing and merging (or rejecting) proposal PRs | Repo owner | Real, ongoing, proportional to how often a pattern crosses threshold — same "solo-maintainer reviews every PR" cost class as everything else in this repo, not a new burden category | Volume risk is the only real new variable — see Scale limits |
| Building and maintaining the new multi-run aggregation function | Repo owner (via this session's own doctrine chain) | Real, one-time build cost; ongoing cost only if the scan window/threshold need retuning based on real proposal volume | Not addressed by the ticket; should be named, not assumed zero |

## Alternatives considered

| Alternative | Why not chosen | Notes |
|-------------|-------------------|-------|
| No cross-run capture at all (current state) | Rejected: literally the gap this ticket exists to close | Correctly motivates building something |
| Fully-automatic convention application — the Orchestrator directly commits captured conventions without human review | Rejected outright: directly contradicts the ticket's own explicit "never auto-committed" acceptance criterion | Not a real option, correctly excluded |
| Route learned-pattern proposals through gap-backlog B4's existing external-comment-ingestion machinery instead of building a new mechanism | Rejected: B4 is narrowly scoped to PR-comment-triggered, single-task Reviewer investigation — structurally different from a periodic, self-triggered, cross-run scan; reusing it here would be scope creep into B4's own deliberately-narrow design | Correct rejection, keeps blast radius contained to a new, purpose-built mechanism rather than overloading an existing narrow one |
| Extend `scripts/run_log.py` in place vs. build a separate multi-run reader module | Left open — a real implementation-level choice, not an architectural one; deferred to `system-design` | Not a blocking decision at this stage |

## Conditions

1. **Define a concrete, evidence-based occurrence/diversity threshold.** State the actual minimum count
   and the minimum number of distinct tasks/PRs/dates a pattern must recur across before it becomes a
   proposal candidate at all — a single incident, however clear, must never alone trigger a proposal.
2. **Enumerate the concrete "repository instructions" file set the conflict-check runs against** (e.g.
   `CONTRIBUTING.md`, every `SKILL.md`, any other named in-repo agent-instructions file) — not a
   description of a class. A detected conflict means the candidate is never proposed, full stop, not
   soft-flagged for human adjudication.
3. **State the injection-resistance mechanism concretely, mechanically, not just as an intention**: the
   proposal's own wording must be Orchestrator-synthesized as a generic principle with cited evidence
   (task/PR references) — never a verbatim rendering of, or directly dictated by, the raw historical
   content that produced the pattern. State explicitly that this bounds but does not eliminate the
   deliberate-seeding risk (Failure modes), and that the cited evidence is what lets a human reviewer
   trace and discount a suspicious cluster.
4. **State an explicit, bounded scan window** (a run-count cap or recency window) for the cross-run
   aggregation — never "all runs ever, unbounded" — so compute cost stays proportional as this repo's
   run-log history grows over its lifetime.
5. **State a data-minimization/redaction rule for the proposal artifact itself**, consistent with this
   repo's existing `safe-output.md` conventions: never verbatim-quote potentially-sensitive raw historical
   content (task text, rebuttal text, human free-text clarify-interview answers) in the proposal — cite by
   reference (task/PR id), synthesize the principle in the Orchestrator's own words.
6. **State explicitly whether concurrent-run race/dedup handling is in scope**, and if so, reuse this
   session's own existing plan-identity/lease-id precedent (gap-backlog B1-B3) rather than inventing new
   machinery — or explicitly scope this ticket as single-session-only if concurrency is genuinely out of
   scope, stated honestly rather than left ambiguous.

None of these six block starting a `system-design` pass — they're precise, implementable requirements for
that pass to satisfy, not open architectural questions.
