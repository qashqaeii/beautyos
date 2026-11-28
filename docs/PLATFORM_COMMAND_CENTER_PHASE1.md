# BeautyOS — Platform Command Center / Phase 1

## Delivered
- Separate `PlatformActivityEvent` table for **product usage** (not security audit).
- Allowlisted event kinds, timestamp, salon, positive count and unique retry-safe key.
- Transaction-commit capture of newly created appointments. Failed/rolled-back transactions do not produce activity.
- Aggregation service for distinct active salons and counts per feature.
- Usage retention cohort calculator: denominator = distinct salons active in original period; numerator = those same salons active in return period.
- Empty cohort returns `None`, never misleading 0% or 100%.
- Tests for deduplication, event allowlist, usage summary, retention and empty cohorts.

## Definitions
- **Usage-active salon**: a salon with at least one tracked meaningful event during the selected window.
- **Usage retention**: fraction of a fixed initial activity cohort that is active again in a later, non-overlapping window.
- **Paid renewal retention**: a separate metric, unavailable until verified platform billing/renewal records exist.
- **Salon business receipts** are not BeautyOS revenue.
- **Coverage**: only new appointment creations are automatically emitted at this stage. Other event kinds are reserved for later explicit integrations. Do not interpret current totals as complete usage analytics.

## Privacy and reliability
Never include names, phone numbers, customer details, notes, addresses or arbitrary JSON payloads in activity events. Dedupe keys must use internal opaque operation IDs, not PII. Business writes remain authoritative. Do not use signals to infer completed appointments or invoices from unverified states.

## Verify before moving to phase 2
```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
pytest -q tests/test_platform_activity_metrics.py tests/test_platform_admin.py
```
Also require full PostgreSQL CI green. Historical backfill is deliberately not enabled: mixing partial historical coverage with live events would distort retention. No billing, SMS or production deployment changes in this phase.
