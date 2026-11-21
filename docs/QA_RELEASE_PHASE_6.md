# BeautyOS — Phase 6: QA and Release (first increment)

## Release scope
Phase 6 in docs/MVP_PLAN.md is QA/Release. This increment adds production fail-closed checks, a real database readiness probe, explicit OTP transport for production, and release validation in CI. It does not deploy to production.

## Mandatory before staging or production
1. Build and verify a clean revision. The main quality workflow must pass PostgreSQL, browser, production preflight and migration checks.
2. Create a database backup and separately back up media. Verify a restore to an isolated environment; do not test restores against live data.
3. Configure DJANGO_SETTINGS_MODULE=config.settings.production. Never use docker-compose.yml as a production deployment: it explicitly loads config.settings.local, and is bound to localhost for developer use only.
4. Set a unique 50+ character SECRET_KEY, a PostgreSQL DATABASE_URL, explicit ALLOWED_HOSTS (without wildcard), HTTPS CSRF_TRUSTED_ORIGINS and a real BEAUTYOS_SMS_PROVIDER.
5. For Kavenegar OTP set BEAUTYOS_SMS_PROVIDER=apps.accounts.sms.KavenegarOTPProvider and set BEAUTYOS_KAVENEGAR_API_KEY and BEAUTYOS_KAVENEGAR_SENDER in server secrets (never commit them). OTP transport is independent of marketing automation.
6. Set BEAUTYOS_TRUST_PROXY_SSL_HEADER=True only when the controlled TLS-terminating reverse proxy overwrites X-Forwarded-Proto. Otherwise leave False; ensure SECURE_SSL_REDIRECT works without loops.
7. Keep BEAUTYOS_AUTOMATION_SEND_ENABLED=False until campaigns and message policies are explicitly reviewed. The release checks never send SMS.
8. Install runtime dependencies, build CSS, run python manage.py migrate --noinput and python manage.py collectstatic --noinput, then run python manage.py release_check.
9. Confirm GET /health/ (process liveness) and GET /health/ready/ (PostgreSQL readiness). Do not route traffic to instances reporting HTTP 503 from readiness.
10. Smoke-test public landing and booking OTP (on authorized test number), salon onboarding, appointment conflict prevention, reception, finance, role permissions and tenant isolation. Verify backup/rollback plan before opening real traffic.

## Commands (production settings)
    export DJANGO_SETTINGS_MODULE=config.settings.production
    python manage.py check --deploy
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    python manage.py release_check

release_check is read-only. It verifies Django deployment checks, a SELECT 1 query, no unapplied migrations and presence of collected CSS. Never use it as a substitute for external monitoring, a verified backup or a staging smoke test.

## Rollback guidance
Prefer reverting the application build to the last known good commit after checking migration compatibility. Schema rollback is a separate DBA-approved procedure and should not destroy user data. Disabling automations or background jobs is safer than deleting pending message records.

## Known remaining release gates
- This is only the first QA/Release increment, not a production launch.
- A real domain, reverse proxy, remote PostgreSQL, persistent static/media volumes and operating-system process supervisor must be validated in staging.
- Full backup/restore and vendor OTP delivery must be exercised in a controlled environment with secrets provided by the operator.
- See docs/PRODUCT_COMPLETION_MATRIX.md for the product features that are still Partial/Missing; this release work does not imply those features are complete.
