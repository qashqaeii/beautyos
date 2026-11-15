from .base import *  # noqa: F403

DEBUG = True
ALLOW_DEMO_SEED = True
BEAUTYOS_DEMO_GRANT_PHONE = "09357930033"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

INTERNAL_IPS = ["127.0.0.1"]
