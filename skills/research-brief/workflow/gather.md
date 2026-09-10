---
workflow_version: 1.0
phase: gather
produces:
  - findings
consumes:
  - research_question
---

# Gather — collect and cite evidence for the question

Check repository evidence first (existing docs, code, ADRs) — a question that's already answered in
this repository does not need external research. Where `host.web.search`/`host.web.fetch` are
available, use them for primary-source claims the repository can't answer; cite the actual URL
fetched, not a remembered summary.

For each claim, record: the claim itself, its evidence status
([confidence-bands.md](../../../docs/skill-framework/shared/confidence-bands.md):
OBSERVED/INFERRED/UNKNOWN/CONFLICTED), and its source (repository path or fetched URL). A claim with
no cited source is `UNKNOWN` — never rendered as fact from unaided recollection.

If `host.web.search`/`host.web.fetch` are unavailable, record that degraded mode explicitly and mark
every claim that would have needed external research `UNKNOWN` rather than answering from training
data.
