---
workflow_version: 1.0
phase: hypotheses
produces:
  - hypotheses_tested
  - root_cause
consumes:
  - symptom
  - repro_status
  - repro_evidence
---

# Hypotheses — form and falsify candidate root causes

Form at least one candidate root cause from the evidence gathered so far. For each candidate, actively
try to falsify it: what evidence, if found, would prove this candidate wrong? Look for that evidence
before retaining the candidate.

A candidate survives only when an active falsification attempt failed to disprove it, and the
evidence for it is stronger than for any rejected alternative. Record every candidate tried —
including rejected ones — with the evidence that rejected it; never silently drop a considered and
rejected hypothesis from the record.

If no candidate survives falsification with available evidence, `root_cause` remains unresolved; do
not select the "least bad" unfalsified guess and present it as confirmed.

If the evidence reveals this is actually a live production incident (an active time window, ongoing
user impact), stop and offer `incident-rca` rather than continuing this workflow.
