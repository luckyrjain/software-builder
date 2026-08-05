# who-owns-x-bot: design

**Date:** 2026-08-05
**Status:** Approved design
**Source:** Item #1 of [team-facing-agents-roadmap.md](../plans/2026-08-05-team-facing-agents-roadmap.md) —
P0, "smallest possible agent on this list, likely the right first thing to build to validate the
wrapper pattern before investing in composed agents."

## Problem

Engineers ask "who owns X" in Slack today and either page around a wiki or interrupt a teammate. The
answer already exists — **squad-map** computes it — but squad-map is an ambient, conversational skill
built for an interactive coding-agent session (Cursor/Claude Code), not for a single-shot Slack slash
command with no follow-up turns.

## Approach

`who-owns-x-bot` is a **thin wrapper skill**, not a new skill with its own analysis logic. It:

1. Accepts a single input — a repo/service/component name (the argument to a `/who-owns` Slack slash
   command, or any single-shot automated caller).
2. Delegates the lookup entirely to squad-map: reads an existing `SQUAD_MAP.md` if present and fresh,
   otherwise invokes squad-map's own Inputs → Phase 0 → Phase 1 scoped to that single repo.
3. Formats the result as a **single Slack message** (not a markdown file) — one line if resolved, a
   short disambiguation list if the name matches multiple repos, or an explicit "don't know" if
   unmapped — and returns.

No new ownership logic, no new MCP calls, no new confidence rules. Everything about *how* ownership is
determined stays in squad-map; this skill only owns *how the answer is packaged for a single-shot,
no-follow-up caller*.

## Why a separate skill instead of "just call squad-map from the Slack bot"

squad-map's output contract is a markdown file at workspace root plus a chat-formatted summary — correct
for an interactive session where the user can ask a follow-up ("what about the Datadog side?"). A Slack
slash command gets exactly one reply and no workspace to write a file into. Packaging that reply (which
repo matched, which confidence band, how to phrase "I don't know" so it prompts a human fallback instead
of guessing) is a distinct, small, and stable responsibility — worth its own SKILL.md so the packaging
rules don't get silently re-invented differently by whichever automation calls squad-map next (this is
exactly what `who-owns-x-bot` should NOT need to duplicate itself: see the reference/slack-format.md
note re: reuse when item #11 Weekly Squad Digest is built later).

## Non-goals (explicitly out of scope for this item)

- No new confidence, reconciliation, or discovery logic — any change to *how* ownership is computed is a
  squad-map change, not a who-owns-x-bot change.
- No live Slack app / HTTP server / OAuth in this repo — this repo ships agent instructions (`SKILL.md`),
  consistent with all 7 existing skills; the actual Slack slash-command HTTP handler is host
  infrastructure outside this repo's scope, exactly as pr-review's actual GitLab webhook receiver is
  outside this repo's scope. `SETUP.md` documents the integration contract (what the caller passes in,
  what it gets back) for whoever builds that handler.
- No caching/aggregation layer — that's explicitly item #11 (Weekly Squad Digest) and the shared
  aggregation-layer phase in the roadmap, deferred until items #8/#10 exist too.

## Interface contract

**Input** (from the Slack slash-command payload or any single-shot caller):

| Field | Required | Notes |
|-------|----------|-------|
| `query` | Yes | Free-text repo/service/component name, e.g. `/who-owns api-disbursement` |
| `workspace_root` | No | Defaults to the caller's configured default workspace (see SETUP.md); needed only when squad-map has to run a fresh lookup |

**Output** — one Slack-formatted message, three possible shapes:

1. **Resolved** — `api-disbursement → *disbursement* squad (HIGH confidence)` + squad-map's own evidence
   line (GitLab namespace / Datadog team tag). No separate contact/channel field — squad-map's schema
   doesn't carry one, so this skill doesn't invent one either.
2. **Ambiguous / conflict** — squad-map found the repo but GitLab squad ≠ Datadog team, or the query
   matched more than one repo — list up to 3 candidates, ask the human to pick.
3. **Unknown** — squad-map returned UNKNOWN or found no match — say so plainly and suggest the human
   fallback (e.g. `#ask-platform`), never guess a squad to avoid giving a confidently wrong answer.

Full format spec: `who-owns-x-bot/reference/slack-format.md`.

## Acceptance criteria

- `who-owns-x-bot/SKILL.md` exists, ≤ 180 lines, links `skill-routing.md` and `prompt-injection.md`.
- Given a repo squad-map can resolve at HIGH/MEDIUM confidence, the skill produces the "Resolved" shape.
- Given a repo squad-map marks UNKNOWN or cannot find, the skill produces the "Unknown" shape — it never
  fabricates a squad name.
- Given a query matching multiple repos or a GitLab/Datadog conflict, the skill produces the "Ambiguous"
  shape rather than picking one silently.
- `make lint-who-owns-x-bot` and `make lint-framework` pass; skill is wired into root README.md,
  docs/README.md, docs/REPOSITORY.md, `skill-routing.md`, `phase-glossary.md`, `CHANGELOG.md`.
- Skill's own frontmatter sets `disable-model-invocation: true` — unlike squad-map, this skill is meant
  to be invoked explicitly by an automation caller passing a structured `query`, not ambiently from a
  human's natural-language chat turn (which should still route to squad-map directly, per
  skill-routing.md disambiguation rule 4).

## Implementation plan

Single-commit build (thin wrapper, no code beyond formatting rules — same "no scripts, doc-only" shape
as this repo's simplest skills' formatting concerns):

1. `who-owns-x-bot/SKILL.md`, `README.md`, `SETUP.md`, `CHANGELOG.md`, `examples.md`.
2. `who-owns-x-bot/workflow/inputs.md` (parse `query` + optional `workspace_root`; untrusted-content
   note — the Slack message text is user input, not instructions) and `workflow/lookup.md` (single
   phase: delegate to squad-map, apply `reference/slack-format.md`, return).
3. `who-owns-x-bot/reference/phase-index.md`, `lazy-load-index.md`, `slack-format.md`, `smoke-test.md`.
4. `.cursor/rules/who-owns-x-bot.mdc`, `.kiro/steering/who-owns-x-bot.md`.
5. `Makefile`: `install-who-owns-x-bot` (chains `install-squad-map`), `install-claude-who-owns-x-bot`,
   `lint-who-owns-x-bot` (SKILL.md line cap, workflow frontmatter, dangling anchors, required reference
   files) added to `.PHONY` and the top-level `lint:` dependency list.
6. Root `README.md`, `docs/README.md`, `docs/REPOSITORY.md`: skills table / file map / install / lint
   rows, following the squad-map row pattern exactly.
7. `docs/skill-framework/shared/skill-routing.md`: routing-table row (automation entry point, disjoint
   from squad-map's ambient-chat row) + disambiguation rule.
8. `docs/skill-framework/shared/phase-glossary.md`: `### who-owns-x-bot mapping` subsection.
9. Root `CHANGELOG.md` + `who-owns-x-bot/CHANGELOG.md`: initial release entry.
10. `make lint` green; deep review pass; fix to 0 issues; commit.
