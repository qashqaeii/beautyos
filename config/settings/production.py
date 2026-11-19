from .base import *  # noqa: F403

from django.core.exceptions import ImproperlyConfigured

DEBUG = False
SECRET_KEY = env("SECRET_KEY")
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("dev-only-", "change-me")):
    raise ImproperlyConfigured("Production requires a strong, unique SECRET_KEY.")
if BEAUTYOS_SMS_PROVIDER == "apps.accounts.sms.DevSMSProvider":
    raise ImproperlyConfigured("Configure a real SMS provider for production.")
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Production requires PostgreSQL.")
ALLOW_DEMO_SEED = False
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])


SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
