# Domain pack: e-commerce-checkout

Pack for cart, checkout, order management, inventory, fulfillment, and refund domains.

Merge into `domain-config.yaml` at Session 0.

## domain

```yaml
domain:
  name: checkout
  display_name: Checkout & Orders
  description: Cart to confirmed order, payment capture, inventory, fulfillment, and returns
```

## scope

```yaml
scope:
  include_keywords:
    - cart
    - order
    - checkout
    - inventory
    - payment
    - fulfil
    - refund
    - shipment
    - coupon
    - promo
  exclude_patterns:
    - '*-mock*'
    - '*-stub*'
  seed_repos: []          # fill in with your repo names
  conditional_repos: []   # e.g., fraud-detection-service, loyalty-service
```

## context

```yaml
context:
  regulatory_notes: Replace with applicable scope (PCI-DSS, regional tax, etc.)
  product_lines:
    - name: digital
      hints: [digital-goods, instant-delivery, no-shipping]
    - name: physical
      hints: [warehouse, fulfillment-center, logistics]
    - name: marketplace
      hints: [seller, vendor, third-party-fulfillment]
```

## five_questions

```yaml
five_questions:
  - id: Q1
    question: How does a cart become a confirmed order?
    search_terms:
      - placeOrder
      - confirmOrder
      - checkoutSession
      - cart.*convert
      - order.*create
      - CartService
      - OrderService
  - id: Q2
    question: When and how is payment captured?
    search_terms:
      - capturePayment
      - chargeCard
      - authorize
      - capture
      - PaymentIntent
      - paymentCapture
      - settle
  - id: Q3
    question: How is inventory reserved and released?
    search_terms:
      - reserveInventory
      - reserve
      - hold
      - release.*inventory
      - stock
      - quantity.*available
      - oversell
  - id: Q4
    question: How does fulfillment or shipping get triggered?
    search_terms:
      - fulfil
      - shipOrder
      - pickPack
      - warehouseJob
      - dispatch
      - tracking
      - courier
  - id: Q5
    question: How are cancellations and refunds handled?
    search_terms:
      - cancel
      - refund
      - reversal
      - compensat
      - return
      - chargeback
      - void
```

## critical_path_tiers

```yaml
critical_path_tiers:
  tier_0:
    label: Order + payment execution
    definition: Confirms the order and captures payment — money changes hands here
    provisional: []   # e.g., order-service, payment-service
  tier_1:
    label: Inventory + fulfillment
    definition: Required to complete the order after payment
    provisional: []   # e.g., inventory-service, fulfillment-service
  tier_2:
    label: Notifications + recon
    definition: Post-order communications, reporting, reconciliation
    provisional: []   # e.g., notification-service, order-recon
  tier_3:
    label: Storefront + BFF
    definition: Entry points, cart, promotions, search
    provisional: []   # e.g., storefront-bff, cart-service, promo-service
  flow_critical_gates:
    - []   # e.g., fraud-check-service, inventory-service
```

## deliverables

```yaml
deliverables:
  map_file: CHECKOUT_MAP.md
  core_section: Order & Payment
```

## ownership

```yaml
ownership:
  gitlab:
    org_prefix: ''          # fill in
    squad_path_segment: 2
    group_prefixes: []      # fill in
  datadog:
    service_aliases: {}
    domain_service_query: "name:order*"
```

## architecture_validation

```yaml
architecture_validation:
  enabled: true
  span_window: now-7d
  dependency_depth: 2
  entry_services: []
  critical_paths:
    - name: checkout-happy-path
      services: []    # fill in: e.g., [storefront-bff, order-service, payment-service, inventory-service]
    - name: refund-path
      services: []    # fill in: e.g., [order-service, payment-service, inventory-service]
    - name: fulfillment-path
      services: []    # fill in: e.g., [order-service, fulfillment-service, logistics-service]
```

## Architecture signals to investigate

| Signal | What to determine |
|--------|-------------------|
| Cart ownership | Is cart state in the storefront BFF, a dedicated cart service, or the order service? |
| Payment timing | Is payment authorized at checkout or only captured at fulfillment? |
| Inventory reservation | Pessimistic (reserve on add-to-cart) vs optimistic (reserve at order confirm)? |
| Async fulfillment | Is fulfillment triggered synchronously in the order flow or via event/queue? |
| Marketplace split | For marketplace: does the platform capture or does each seller capture separately? |

## Business flows (minimum 3 for P2)

Seed journeys for `BUSINESS_FLOWS.md`:

| Journey | Trigger | Terminal |
|---------|---------|----------|
| Standard checkout | Cart submitted | Order confirmed, payment captured, fulfillment queued |
| Order cancellation | User cancels pre-fulfillment | Order cancelled, payment voided/refunded |
| Refund | Return requested or chargeback | Refund issued, inventory restocked |
| Failed payment retry | Payment capture fails | Retry or order cancelled |
| Partial fulfillment | One item out of stock | Partial ship + partial refund or backorder |

## P3b adversarial hints

- **Double-charge on retry:** if the payment capture request times out, can it be replayed without idempotency protection?
- **Inventory oversell race:** can two concurrent checkout sessions reserve the last unit simultaneously?
- **Coupon stacking:** can multiple discount codes be applied in one order beyond policy limits?
- **Partial fulfillment without refund:** if only some items ship, is the partial refund automated or manual?
- **Payment capture before inventory confirm:** can money be taken for an item that cannot be fulfilled?
