---
workflow_version: 1.0
phase: classify
produces:
  - response_mode
  - depth
  - risk_domains
consumes:
  - request
  - source_material
  - mode_hint
  - depth_hint
---

# Classify — mode, depth, risk

## 1. Response mode

Infer from [response-modes.md](../reference/response-modes.md):

| Signal | Mode |
|--------|------|
| Convert idea / write PRD / feature spec | **PRD** |
| Should we build? / challenge / build vs buy / alternatives | **Validation** |
| Existing PRD + review / gaps / readiness / improve | **Review** |
| Existing PRD + critique only (`critique_only: true`) | **Review** (findings only) |

If the user supplies an existing PRD and asks what the gaps are, use **Review**, not Validation.

## 2. Depth

Select per [depth.md](../reference/depth.md). Default **Standard** when uncertain between Lite and
Standard; default **Rigorous** when uncertain between Standard and Rigorous **and** plausible failure
could cause financial loss, data corruption, security incident, regulatory exposure, irreversible user
harm, or material operational disruption.

Record: `depth` + one-line reason (required in output header).

## 3. Material risk domains

Flag domains that trigger mandatory review perspectives in Break:

- money movement, lending, payments, billing
- sensitive personal data, regulated workflows
- security-critical behavior, fraud, abuse
- distributed / async multi-system workflows
- irreversible actions, migration, high availability

Pass `risk_domains` to Break and Gate.
