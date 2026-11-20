# Finance phase 2 – first integration increment

- The approved Editorial Rose concept is applied to the finance home with four compact KPIs, real received/expense trend, payment-method breakdown, quick actions, and operational links.
- Existing Payment, Expense, SalonDebt, Commission and Package records remain authoritative. No parallel ledger or fake figures.
- Earned service value uses completed appointments (completion date; start date for historical rows without completion timestamp), less recorded discounts. Redeemed prepaid sessions use integer prorated package value; package sales disclosed separately. No recognition of standalone receipts as service revenue without a linked completed appointment.
- The operating estimate excludes unrecorded cost, tax, depreciation and unimplemented product revenue/cost; commissions are for completed appointments, not cash settlements. Receivables are current outstanding completed non-package bookings, irrespective of date filter. Methods reflect recorded receipts, never bank balances.
- Receipt page is tenant and permission scoped, printable / browser save as PDF; not a multi-line invoice.
- Remaining: multi-line invoices and idempotent checkout, refund transactions, account ledger/transfers and daily close, specialist salary/rent models, expense recurrence, verified inventory cost and reporting reconciliation. Do not infer these are implemented by the dashboard.
