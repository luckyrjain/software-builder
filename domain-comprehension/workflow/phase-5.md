---
workflow_version: 1.6
phase: 5
---

# Comprehension Phase P5 — Delivery and handoff

Final evidence review, section confidence calibration, and delivery checklist.

## Required outputs

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Final five questions | `EXEC_SUMMARY.md` | COMPLETE or UNKNOWN each — no DRAFT allowed | Phase incomplete |
| Overall confidence | `EXEC_SUMMARY.md` | Question table + overall band | Phase incomplete |
| Engineering leader summary | `EXEC_SUMMARY.md` § Engineering Leader Summary | Per [engineering-leader-summary.md](../reference/engineering-leader-summary.md) | Phase incomplete |
| Architecture decisions | `ARCHITECTURE_DECISIONS.md` | ADRs or UNKNOWN | Phase incomplete |
| Repo map table | `EXEC_SUMMARY.md` | classification + squad + tier + branch + SHA per repo | Phase incomplete |
| Evidence summary (final) | `EXEC_SUMMARY.md` + manifest | All counters populated (non-zero where evidence exists) | Phase incomplete |
| Section confidences | `EXEC_SUMMARY.md` | Per major section | Phase incomplete |
| PROGRESS.md status | `PROGRESS.md` | `FIRST_PASS_COMPLETE` | Phase incomplete |

## Memory Bank export (optional)

When `domain-config.yaml` `memory_bank.export_mode` is `p5` or (`optional` and user requested export):

| Artifact | Location | Key fields | If absent |
|----------|----------|------------|-----------|
| Per-repo memory banks | `<repo>/memory-bank/*.md` | Six core files per export-target repo | Required when `export_mode: p5` |
| Generated appendix | `<repo>/memory-bank/.generated/` | Refreshed when P0.5 graphs exist | Recommended |
| Manifest artifact | `manifest.yaml` `memory_bank_export` | `ok` \| `waived` \| `n_a` | Update every P5 |

**Procedure:** [memory-bank-integration.md](../reference/memory-bank-integration.md).

**Do not** run a separate cursor-bank "initialize memory bank" pass when P5 export completes — export
projects comprehension deliverables into Memory Bank format.

When `export_mode: never`, set manifest `memory_bank_export` → `n_a`.

## API tooling export (optional)

When `domain-config.yaml` `api_tooling.export_mode` is `p5` or (`optional` and user requested export):

| Output | Location | Required fields | Note |
|--------|----------|------------------|------|
| Postman collection | `postman/postman_collection.json` | Numbered folder per in-scope repo/service, built from `API_CATALOG.md` + P1 Auth & Gateway + P2 Deployment base URLs | Required when `export_mode: p5` |
| Per-env environment files | `postman/postman_environment.<env>.json` (one per `api_tooling.envs`) | Importable, base URL from § Deployment | Required |
| Generator config | `postman/environment.defaults.json` | Not imported — `gen_postman.py` input | Required |
| Generator script | `postman/gen_postman.py` | Regenerates env files, patches collection (`appVersion`/`versionCode` sync) | Required |
| OTP helper | `postman/fetch_otp_from_redis.py` | Only when `api_tooling.otp_helper` resolves to on (see below) | Conditional |
| README | `postman/README.md` | Import steps, Happy Path, Newman command | Required |
| Manifest artifact | `manifest.yaml` `api_tooling_export` | `ok` \| `waived` \| `n_a` | Update every P5 |

**`otp_helper` resolution:** `always` → always write it; `never` → never; `auto` (default) → write it only
if any in-scope repo's P1 Auth & Gateway subsection recorded Redis OTP-pattern usage — cite the evidence in
the script's header comment.

**Procedure:** [api-tooling-integration.md](../reference/api-tooling-integration.md).

**Evidence rule:** every request in the collection traces to an `API_CATALOG.md` row. A route with no
evidenced auth model (P1 recorded `UNKNOWN`) gets a commented-out placeholder header in the collection —
never an invented value.

When `export_mode: never`, set manifest `api_tooling_export` → `n_a`.

## Definition of Done

[phase-completion-gate.md](../reference/phase-completion-gate.md)
