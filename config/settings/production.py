from .base import *  # noqa: F403

from django.core.exceptions import ImproperlyConfigured

DEBUG = False
SECRET_KEY = env("SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("dev-only-", "change-me")):
    raise ImproperlyConfigured("Production requires a strong, unique SECRET_KEY.")
if BEAUTYOS_SMS_PROVIDER == "apps.accounts.sms.DevSMSProvider":
    raise ImproperlyConfigured("Configure a real SMS provider for production.")
if (
    BEAUTYOS_SMS_PROVIDER == "apps.accounts.sms.KavenegarOTPProvider"
    and not (BEAUTYOS_KAVENEGAR_API_KEY and BEAUTYOS_KAVENEGAR_SENDER)
):
    raise ImproperlyConfigured("Kavenegar OTP credentials must be configured in production.")
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Production requires PostgreSQL.")
ALLOW_DEMO_SEED = False
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# Fail closed: the example environment only permits localhost, and a wildcard
# host must never be accepted as a production host.
if "*" in ALLOWED_HOSTS or not any(
    host not in {"localhost", "127.0.0.1", "::1", "[::1]", "testserver"}
    for host in ALLOWED_HOSTS
):
    raise ImproperlyConfigured("Production requires explicit public ALLOWED_HOSTS.")

# Only trust X-Forwarded-Proto if your reverse proxy strips client-supplied
# values and sets the header itself. Direct deployments must leave it off.
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if env.bool("BEAUTYOS_TRUST_PROXY_SSL_HEADER", default=False)
    else None
)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
