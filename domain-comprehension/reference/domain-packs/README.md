# Domain packs

Optional pre-authored config fragments for common domain types. At Session 0:

1. Load pack YAML/markdown sections
2. Merge into `domain-config.yaml`
3. Apply user overrides

## Available packs

| Pack | File | Use when |
|------|------|----------|
| fintech-payout | [fintech-payout.md](fintech-payout.md) | Disbursement, payout, bank rails, recon |
| auth-identity | [auth-identity.md](auth-identity.md) | Authentication, authorization, session management, SSO/federation |
| e-commerce-checkout | [e-commerce-checkout.md](e-commerce-checkout.md) | Cart, checkout, order, inventory, fulfillment, refunds |

## Authoring a new pack

1. Copy `fintech-payout.md` structure
2. Define `five_questions`, `critical_path_tiers`, `scope`, `product_lines`
3. Add row to table above
4. Add invocation example to [examples.md](../../examples.md)

Packs are **hints** — agent still runs census and verifies scope.
