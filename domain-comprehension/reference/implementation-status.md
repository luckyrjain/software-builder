# Implementation status (normative)

**Required for:** P3 capability matrix, API/event catalogs, P5 synthesis. **No other values allowed.**

Two independent axes — record **both** where applicable.

## Axis 1: Implementation

| Status | Definition | Evidence required |
|--------|------------|-------------------|
| **Implemented** | Production code path complete | Handler + persistence/gateway |
| **Partially implemented** | Core path exists; known gaps | Code path + listed gaps |
| **Deprecated** | Superseded or no inbound refs | `@Deprecated`, git log, Datadog absence |
| **Stub** | Interface exists; no real logic | Code inspection |
| **Experimental** | Feature flag / non-prod only | Flag + config path |
| **Unknown** | Insufficient evidence | Notes column |

## Axis 2: Exercise (implemented vs exercised)

| Status | Definition | Evidence required |
|--------|------------|-------------------|
| **referenced** | Inbound refs (imports, HTTP client, consumer) | Static code refs |
| **runtime_confirmed** | Observed in Datadog P2b on critical or catalog path | Trace + code alias |
| **dead_code** | Implementation present; no refs and no runtime in window | Ref scan + P2b absence |
| **unknown** | Not yet verified | — |

**Rule:** `runtime_confirmed` requires code **or** config endpoint exists — runtime alone does not prove implementation completeness.

Precedence on conflict: [evidence-precedence.md](evidence-precedence.md).

## Matrix format

| Capability / feature | Implementation | Exercise | Evidence | Notes |
|---------------------|----------------|----------|----------|-------|

API/event catalog columns: `Implementation` | `Exercise` | `Evidence`.

## Rules

- Never **Implemented** + **runtime_confirmed** from README or ADR alone
- **Stub** vs **Partially implemented**: stub = no business logic; partial = logic with holes
- Section status = worst implementation status among rows (for leader summary)
- **dead_code** on P2b critical hop → architectural smell ([architectural-smells.md](architectural-smells.md))
