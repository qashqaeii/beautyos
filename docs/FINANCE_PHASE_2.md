# Finance phase 2 – first integration increment

- The approved Editorial Rose concept is applied to the finance home with four compact KPIs, real received/expense trend, payment-method breakdown, quick actions, and operational links.
- Existing Payment, Expense, SalonDebt, Commission and Package records remain authoritative. No parallel ledger or fake figures.
- Earned service value uses completed appointments (completion date; start date for historical rows without completion timestamp), less recorded discounts. Redeemed prepaid sessions use integer prorated package value; package sales disclosed separately. No recognition of standalone receipts as service revenue without a linked completed appointment.
- The operating estimate excludes unrecorded cost, tax, depreciation and unimplemented product revenue/cost; commissions are for completed appointments, not cash settlements. Receivables are current outstanding completed non-package bookings, irrespective of date filter. Methods reflect recorded receipts, never bank balances.
- Receipt page is tenant and permission scoped, printable / browser save as PDF; not a multi-line invoice.
- Remaining: multi-line invoices and idempotent checkout, refund transactions, account ledger/transfers and daily close, specialist salary/rent models, expense recurrence, verified inventory cost and reporting reconciliation. Do not infer these are implemented by the dashboard.

## Checkout increment
- Internal invoice groups up to 50 completed, non-package appointments for the same customer. All prices and prior receipts are calculated on the server under the existing appointment row locks.
- Payment rows remain authoritative; issue-time snapshot records gross, prior discounts/receipts, new discount, new payment and balance. Three payment methods can be allocated in one submission.
- Request UUID + payload digest enforce idempotency, and one invoice line per appointment prevents accidental second invoicing. Later receipts still use the existing receipt flow. Access is tenant-scoped.
- No automatic refunds, fiscal e-invoice integration, product lines, bank-account ledger or cash close yet. Package sessions must be redeemed through the existing package flow, not invoiced as new services.

## Cash reconciliation and reporting increment
- Daily immutable CashClose snapshots (one per salon/day) compare counted cash with opening + recorded cash receipts + manual other cash in - manual cash out. Nonzero differences require a note; duplicate submissions do not create multiple closures. Card and transfer receipts are disclosed separately; later receipt changes are flagged rather than rewriting the snapshot.
- Cash reconciliation is not a bank-account ledger; the manual amounts do not create duplicate expense or payment rows.
- Expense reports use Jalali month boundaries and include partial receipts, without labeling cash receipts minus expenses as net profit. Expense creation validates positive amounts and records an audit event.
- Financial overview uses actual line chart and receipt-method donut inspired by the approved design.
