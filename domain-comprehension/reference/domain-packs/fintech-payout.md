# Domain pack: fintech-payout

Example pack for disbursement / payout / bank-rail subsystems (derived from mPokket disbursement comprehension).

Merge into `domain-config.yaml` at Session 0.

## domain

```yaml
domain:
  name: disbursement
  display_name: Disbursement
  description: End-to-end disbursement and payout flow
```

## scope

```yaml
scope:
  include_keywords:
    - disbursement
    - payout
    - bank
    - recon
    - orchestration
    - queue push
  exclude_patterns:
    - '*-mohan-test'
    - '*-datadog'
    - cloudfront-test
    - disbursement-testing-datadog
  seed_repos:
    - api-disbursement
    - disbursement-service
    - disbursement-core-service
    - secured-disbursement-service
    - orchestration-disbursement
    - disbursement-consumer
    - Disbursement-task-consumer
    - disbursement-recon-service
    - disbursement-recon-consumer
    - workers-common-disbursement-recon
    - disbursement-lumen-internal-api
    - disbursement-lender-service
    - disbursement-internal-bff
    - disbursement-external-bff
    - disbursement-external-web-bff
    - disbursement-external-tpa-bff
    - disbursement-mobile-api
    - disbursement-mobile-api-thin-layer
    - disbursement-queue-push-api
    - queue-push-disbursement
    - disbursement-documents
    - disbursement-resend-document-consumer
    - disbursement-crm-service
    - flask-api-disbursement
    - flask-roach-disbursement
    - disbursal-block-service
    - payee-validation-service
    - loan-product-service
    - hdfc-bank-service
    - icici-bank-service
    - idfc-bank-service
    - jana-bank-service
    - rbl-bank-service
    - yes-bank-service
    - slice-service
    - idfc-auto-recon
    - yes-bank-autorecon-lambda-function
    - user-consent-service
    - mcoin-consumer
    - document-management-tool
  conditional_repos:
    - autodebit-service
```

## context

```yaml
context:
  regulatory_notes: RBI-regulated Indian fintech; India/US split — geography-specific rails
  product_lines:
    - name: secured
      hints: [secured-disbursement-service, SecuredDisbursement]
    - name: neo
      hints: [NeoDisbursement, Neo Kafka, neo-disbursement]
    - name: legacy-flask
      hints: [flask-api-disbursement, flask-roach-disbursement]
```

## five_questions

```yaml
five_questions:
  - id: Q1
    question: What service actually moves money (executes the payout)?
    search_terms:
      - disburse
      - payout
      - transfer
      - IMPS
      - NEFT
      - UPI
      - RTGS
      - ACH
      - PaymentGateway
      - initiatePayment
      - executePayout
      - fundTransfer
  - id: Q2
    question: What prevents double disbursement (idempotency / dedup)?
    search_terms:
      - idempoten
      - dedup
      - unique
      - requestId
      - clientReference
      - ON CONFLICT
      - duplicate
      - Transactional
  - id: Q3
    question: What is the source of truth for payout/disbursement state?
    search_terms:
      - disbursement_status
      - DisbursementRequest
      - ledger
      - journal
      - disbursement_requests
  - id: Q4
    question: How is reconciliation performed?
    search_terms:
      - reconcil
      - settlement
      - bank statement
      - UTR
      - unmatched
      - recon
  - id: Q5
    question: What happens when a payout fails?
    search_terms:
      - retry
      - DLQ
      - dead letter
      - FAILED
      - compensat
      - reversal
      - manual review
      - stuck
      - PENDING
```

## critical_path_tiers

```yaml
critical_path_tiers:
  tier_0:
    label: Money executor
    definition: Executes or directly invokes money movement
    provisional:
      - hdfc-bank-service
      - icici-bank-service
      - idfc-bank-service
      - jana-bank-service
      - rbl-bank-service
      - yes-bank-service
      - slice-service
      - yes-bank-autorecon-lambda-function
  tier_1:
    label: Payout orchestration
    definition: Required for payout execution
    provisional:
      - api-disbursement
      - disbursement-service
      - disbursement-core-service
      - secured-disbursement-service
      - orchestration-disbursement
      - disbursement-consumer
      - Disbursement-task-consumer
  tier_2:
    label: Recon and ops
    definition: Recon, reporting, internal ops, documents
    provisional:
      - disbursement-recon-service
      - disbursement-recon-consumer
      - workers-common-disbursement-recon
      - disbursement-lumen-internal-api
      - idfc-auto-recon
      - disbursement-documents
      - disbursement-crm-service
  tier_3:
    label: BFF and gates
    definition: BFFs, mobile, queue helpers, validation gates
    provisional:
      - disbursement-internal-bff
      - disbursement-external-bff
      - disbursement-external-web-bff
      - disbursement-external-tpa-bff
      - disbursement-mobile-api
      - disbursement-mobile-api-thin-layer
      - disbursement-queue-push-api
      - queue-push-disbursement
      - payee-validation-service
      - disbursal-block-service
      - loan-product-service
      - user-consent-service
  flow_critical_gates:
    - disbursal-block-service
    - payee-validation-service
    - user-consent-service
    - loan-product-service
```

## deliverables

```yaml
deliverables:
  map_file: DISBURSEMENT_MAP.md
  core_section: Money Movement
```

## ownership

```yaml
ownership:
  gitlab:
    org_prefix: mpokket
    squad_path_segment: 2
    group_prefixes:
      - mpokket/disbursement
  datadog:
    service_aliases:
      disbursement-service: neo-disbursement-service
    domain_service_query: "name:disbursement*"
```

## architecture_validation

```yaml
architecture_validation:
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []
  critical_paths:
    - name: secured-disbursement-happy-path
      services:
        - secured-disbursement-service
        - orchestration-disbursement
        - hdfc-bank-service
    - name: neo-disbursement-happy-path
      services:
        - neo-disbursement-service
        - disbursement-service
        - icici-bank-service
    - name: legacy-api-entry
      services:
        - api-disbursement
        - disbursement-core-service
        - yes-bank-service
```

## Architecture signals to investigate

| Signal | What to determine |
|--------|-------------------|
| Secured line | Entry API, orchestrator, money executor |
| Neo line | Parallel or shared rails vs secured |
| Legacy Flask | Active vs deprecated vs Java `api-disbursement` |
| queue-push duplicates | Which of `queue-push-disbursement` vs `disbursement-queue-push-api` is authoritative |
| Document sub-flow | Blocking vs async relative to money path |

## Business flows (minimum 3 for P2)

Seed journeys for `BUSINESS_FLOWS.md`:

| Journey | Trigger | Terminal |
|---------|---------|----------|
| Disbursement (secured) | Loan disburse request | Payout success / failure |
| Disbursement (neo) | Neo disburse API | Bank rail completion |
| Reconciliation | Bank statement / UTR match | Recon settled / exception |
| Refund / reversal | Failure or ops action | Funds returned / manual review |
| Auto-debit (conditional) | Mandate trigger | Debit success / retry |

Use at least three that apply to in-scope repos; add others when evidence supports.
