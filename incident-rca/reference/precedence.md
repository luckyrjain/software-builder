# Precedence (when specs conflict)

Load during **Phase 4** (ranking) and **Phase 5** (render). Universal STOP rules in [SKILL.md](../SKILL.md)
outrank everything.

| Rank | Source | Wins over | Applies to |
|------|--------|-----------|------------|
| **1** | [SKILL.md](../SKILL.md) §Red flags — STOP | Ranking and narrative certainty | Caps, blocked Phase 4, acyclic graph |
| **2** | [phase-exit-criteria.md](phase-exit-criteria.md) | Advancing with incomplete gates | Per-phase checkpoints |
| **3** | [evidence-quality.md](evidence-quality.md) | Inline SKILL scoring summary | Hierarchy, formula, caps, dedup, multi-cause |
| **4** | [validate_causal_graph.py](../scripts/validate_causal_graph.py) / [causal-graph-schema.md](causal-graph-schema.md) | Hand-edited graph prose | CG-01–CG-08, score arithmetic |
| **5** | Correlator CLI output (when present) | Manual re-ranking | Phase 5 merge logic |
| **6** | [manual-scoring.md](manual-scoring.md) | Ad-hoc weights | Signal weights when CLI absent |
| **7** | [thresholds.md](thresholds.md) | Heuristic guesses | Numeric cutoffs (throttle %, onset windows) |
| **8** | [org-profiles.md](org-profiles.md) | Generic search/DB heuristics | OpenSearch/mpokket branches |

## Scoring conflicts

| Question | Rule |
|----------|------|
| CLI vs manual | **CLI canonical** when `rca_result.json` valid; else manual per evidence-quality formula |
| Formula vs narrative confidence | **Bands in report body** — no decimal scores in executive narrative |
| Validator vs manual score | **Validator wins** for `causal_graph`; fix graph before render |
| Unresolved contradiction | Cap **MEDIUM**; no cut-style certainty language |

## Evidence conflicts

| Signals disagree | Resolution |
|------------------|------------|
| Logs vs metrics on attribution | [evidence-quality.md](evidence-quality.md) hierarchy — document in **Gaps** |
| Deploy time vs error onset | Correlated until diff-on-path proves Observed cause |
| traffic_anomaly vs flat ES throughput | Expensive-query branch — see [org-profiles.md](org-profiles.md) |

When still ambiguous, prefer *No defensible root cause* over best-guess primary.
