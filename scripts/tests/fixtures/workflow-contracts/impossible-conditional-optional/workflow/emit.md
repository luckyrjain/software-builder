---
workflow_version: 1.0
phase: emit
produces: {artifact: string}
consumes:
  required: {summary: object}
  optional: {}
  conditional:
    short:
      required: {}
      optional: {draft: object}
---

# Emit
