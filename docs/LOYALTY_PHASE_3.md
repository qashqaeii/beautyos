# Loyalty phase 3 — initial implementation

- Existing loyalty account and transaction history are preserved. Policy is scoped per salon and disabled by default. New paid/partial receipt (including deposit, checkout, product sale) earns floor(payment / configured unit), capped at 1,000,000 points per receipt. Completed visit earns separately. No automatic backfill, package sales reward not yet implemented. Per-receipt rounding means split receipts may yield fewer points than one receipt.
- Original entitlement and spend unit are immutable per source. Refund reduces entitlement based on cumulative refund and original unit even when the policy is disabled; cancellation reverses visit award; a spent award may yield a negative points balance, offset by future grants. Financial refunds are not blocked by loyalty.
- Existing tiers remain based on spendable point balance. Manual adjustment is audited; cross-tenant customer inputs rejected; monthly stats follow Jalali dates.
- Next: reward redemption catalog, birthday and referral bonuses, package/discount integration, member insights and responsive acceptance.

## Rewards and birthday gifts
- Salon-scoped reward catalog and immutable redemption price/name snapshot. Account lock + idempotency key prevent negative or double spending; pending gifts can be fulfilled or cancelled once and cancellation restores exact points as adjustment. Fulfilled gifts cannot be cancelled. Gift fulfillment is operational, not an automatic invoice discount or stock movement.
- Birthday view shows registered birthdays in current Jalali month; manager confirms annual gift once per customer/year, amount configured per salon. No SMS or outbound marketing. Browser smoke coverage adds program, rewards and birthdays.

## Referrals and checkout vouchers
- Existing customer (completed visit) can refer a new customer before their first completion. One referrer per customer, no self-referral, tenant checked. Bonus amount is snapshotted at registration. Completion while enabled awards once; cancelling the qualifying visit reverses the award, without reissuing on a later visit.
- Manager issues expiring fixed-value vouchers assigned to one customer. Checkout validates and locks the voucher, includes its full amount within recorded invoice discounts, and binds it to the invoice in the same transaction. One voucher per invoice, non-transferable, no cash value, no automatic restoration on reversal of a completed invoice. Existing manual discounts remain supported; no new money ledger.
