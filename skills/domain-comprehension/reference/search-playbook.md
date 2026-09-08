# Search playbook

Derive grep seeds from `domain-config.yaml` → `five_questions[].search_terms`.

## Per-question workflow

1. Run each `search_term` across in-scope repos (respect ignore dirs)
2. Rank hits: migrations/schemas > handlers > config > comments
3. Record top files per question in Session 0 notes → draft answers

## Generic seed terms (supplement if thin)

| Theme | Terms |
|-------|-------|
| Side effect | `execute`, `process`, `submit`, `transfer`, `publish`, `dispatch` |
| Idempotency | `idempoten`, `dedup`, `unique`, `requestId`, `ON CONFLICT`, `duplicate` |
| State | `status`, `state`, `enum`, `ledger`, `journal`, migration table names |
| Reconciliation | `reconcil`, `settlement`, `unmatched`, `match` |
| Failure | `retry`, `DLQ`, `dead letter`, `FAILED`, `compensat`, `reversal`, `stuck` |

## Conditional repo check

For each `conditional_repos` entry:

```bash
rg -l '<include_keywords joined>|' <repo> --glob '!node_modules' --glob '!vendor' --glob '!target'
```

Include in scope only if gating evidence found.

## Product-line hints

If `product_lines` configured, grep each `hints` list and map hits to inventory rows.
