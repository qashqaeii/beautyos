# Loyalty phase 3 — initial implementation

- Existing loyalty account and transaction history are preserved. Policy is scoped per salon and disabled by default. New paid/partial receipt (including deposit, checkout, product sale) earns floor(payment / configured unit), capped at 1,000,000 points per receipt. Completed visit earns separately. No automatic backfill, package sales reward not yet implemented. Per-receipt rounding means split receipts may yield fewer points than one receipt.
- Original entitlement and spend unit are immutable per source. Refund reduces entitlement based on cumulative refund and original unit even when the policy is disabled; cancellation reverses visit award; a spent award may yield a negative points balance, offset by future grants. Financial refunds are not blocked by loyalty.
- Existing tiers remain based on spendable point balance. Manual adjustment is audited; cross-tenant customer inputs rejected; monthly stats follow Jalali dates.
- Next: reward redemption catalog, birthday and referral bonuses, package/discount integration, member insights and responsive acceptance.
