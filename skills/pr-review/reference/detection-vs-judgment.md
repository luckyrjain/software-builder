# Detection vs judgment

Separate **finding defects** (detector) from **deciding they matter** (judge). Reduces oscillation and
makes the pipeline evolvable. Used in Phase 2 step 1 (detect) and steps 3–9 (judge).

Load with `reference/finding-pipeline.md`.

## Roles

| Role | Question | Output |
|------|----------|--------|
| **Detector** | *What might be wrong here?* | Candidate `{ id, hypothesis, location, evidence[], detector }` |
| **Judge** | *Does it matter? Should we post?* | Verdict after pipeline steps 2–10; separate **Observed** from **Assumption** when production exposure is inferred (`reference/finding-evidence-model.md`) |

Detectors are **permissive** — they surface hypotheses from checklist rows, diff patterns, and
`capability_profile` triggers. Judges are **strict** — pipeline gates, severity, value filter.

## Detector sources

| Source | Examples |
|--------|----------|
| `reference/review-checklist.md` | §2 secret pattern, §4 N+1 hint, §9 missing log |
| `capability_profile` | K8s → deploy probes; LLM → prompt injection |
| `review-rules.yaml` domains | payments → idempotency hint on money paths |
| Persona emphasis | SRE → §9/§17 first pass on production hunks |

Detectors **must not** assign Overall severity or recommend posting — only tag candidates.

## Candidate record (internal)

```
candidate: {
  hypothesis: "Webhook handler skips signature verification",
  location: "payments/webhook.py:42",
  evidence: ["- if not verify_sig(body): pass  # removed check"],
  detector: "checklist §2 / security scan"
}
```

## Judge pipeline

Pass each candidate through `reference/finding-pipeline.md` steps 2–10. The judge emits a **finding**
only when all gates pass (or non-negotiable waives path/guess).

| Judge outcome | Meaning |
|---------------|---------|
| **emit** | Row in findings table; eligible for Phase 4 post |
| **emit (grouped)** | Merged into root-cause group — one gate-matrix row |
| **suppress** | Dropped — record reason in `review_metrics` |
| **chat-only** | Unverifiable or feedback-downgraded — no post |

## Anti-patterns

- **Do not** skip detect because "probably fine" — let the judge suppress with evidence.
- **Do not** combine detect + severity in one pass — score only after step 7.
- **Do not** detector-post — posting happens in Phase 4 after full judge pipeline.

## Checklist mapping

Each checklist § row is a **detector hint**. Example §9 row *"New error path logs at debug only"*:

1. Detector fires on changed catch blocks without error-level log.
2. Judge: evidence? (yes — line in diff) → guess? (yes) → path? (yes — error path reachable) → severity
   by context → value filter → emit.
