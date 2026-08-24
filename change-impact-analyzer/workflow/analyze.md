---
workflow_version: 1.0
phase: analyze
produces:
  - change_classes
  - impacted_surfaces
  - evidence_gaps
consumes:
  - assessment_target
  - change_material
  - input_provenance
---

# Analyze

Classify the supplied change and identify impacted repositories, services, contracts, data,
dependencies, owners, tests, operational surfaces, and specialist-review triggers. Missing
authoritative evidence remains an explicit unknown; it never becomes fabricated complete coverage.
