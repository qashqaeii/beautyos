# Phase 5 — Salon automation and delivery

## Scope
Phase 5 extends the opt-in appointment reminders, Jalali birthday and winback queue with real appointment confirmation/cancellation events, explicit campaign scheduling, delivery status reconciliation and per-salon limits.

## Security and reliability
- All sending is disabled by default. Campaigns require explicit manager scheduling, marketing permission and current customer consent.
- Booking events require transactional SMS permission and an enabled scenario; they are recorded only on a new lifecycle event, never retroactively.
- A durable unique source key prevents duplicate queue entries. Salon/message database locks serialize claims.
- Before sending, active tenant, customer consent, appointment status, campaign status and expiry are rechecked.
- Rolling 24-hour salon cap: 1–500 marketing messages (default 30). At most one marketing message per customer in any 24-hour window.
- The provider receives a stable localid equal to the outbox row ID. Once claimed, an ambiguous result never returns to pending; reconciliation polls by provider ID or localid without a blind resend.
- Provider acceptance is not proof of delivery. Only a positive provider status changes state to delivered.
- Audit records contain event IDs and statuses but no customer phone numbers, SMS text or API keys.

## Configuration
Set these environment keys on the server. Do not commit credentials.

    BEAUTYOS_AUTOMATION_SEND_ENABLED=False
    BEAUTYOS_KAVENEGAR_API_KEY=
    BEAUTYOS_KAVENEGAR_SENDER=

Run migrations with: python manage.py migrate
OTP uses its existing provider. Marketing never uses the OTP transport.

## Schedule
Install an external cron/systemd timer every 5–15 minutes:

    python manage.py run_automation --limit 100

The command prepares, dispatches only when authorized and configured, then reconciles prior results. A preparation-only command remains available: python manage.py prepare_automation.
The repository does NOT install a production scheduler, configure credentials or enable transport automatically.

## Activation checklist
1. Migrate and confirm manager-only access and customer marketing consent.
2. Test with a dedicated internal salon and verified sender while the production gate is off.
3. Enable the global gate and the required per-salon scenarios explicitly.
4. Install the external scheduler and monitor accepted, delivered, failed, skipped and unknown.
5. Never reset or resend unknown items without positive proof of non-delivery.

## Tests
    pytest -q tests/test_automation_phase5.py tests/test_automation_delivery_phase5.py tests/test_automation_campaign_phase5.py tests/test_marketing_phase4.py
    python manage.py check
    python manage.py makemigrations --check --dry-run

Full end-to-end SMS delivery requires actual server credentials and authorization.
