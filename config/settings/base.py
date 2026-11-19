import os
from pathlib import Path

import django
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(env_file)

SECRET_KEY = env(
    "SECRET_KEY",
    default="dev-only-change-me-in-production-beautyos-2025",
)

DEBUG = env.bool("DEBUG", default=False)

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "django_htmx",
    "apps.core",
    "apps.accounts",
    "apps.salons",
    "apps.customers",
    "apps.services",
    "apps.staff",
    "apps.appointments",
    "apps.finance",
    "apps.portfolio",
    "apps.notifications",
    "apps.retention",
    "apps.dashboard",
    "apps.audit",
    "apps.commissions",
    "apps.expenses",
    "apps.packages",
    "apps.reception",
    "apps.workday",
    "apps.inventory",
    "apps.loyalty",
    "apps.waitlist",
    "apps.website",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.salons.middleware.SalonTenantMiddleware",
    "apps.salons.middleware_onboarding.OnboardingGateMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
            Path(django.__file__).resolve().parent / "forms" / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "builtins": [
                "django.contrib.humanize.templatetags.humanize",
                "apps.core.templatetags.format_tags",
            ],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.salons.context_processors.salon_context",
                "apps.core.context_processors.global_context",
            ],
        },
    },
]

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"

WSGI_APPLICATION = "config.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "website:home"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
}

BEAUTYOS_OTP_EXPIRY_SECONDS = env.int("BEAUTYOS_OTP_EXPIRY_SECONDS", default=300)
BEAUTYOS_OTP_MAX_ATTEMPTS = env.int("BEAUTYOS_OTP_MAX_ATTEMPTS", default=5)
BEAUTYOS_OTP_RATE_LIMIT = env("BEAUTYOS_OTP_RATE_LIMIT", default="5/m")
BEAUTYOS_SMS_PROVIDER = env(
    "BEAUTYOS_SMS_PROVIDER",
    default="apps.accounts.sms.DevSMSProvider",
)

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


def _beautyos_asset_version() -> str:
    stamps = []
    for rel in (
        "static/css/beautyos.css",
        "static/css/editorial-foundation.css",
        "static/css/editorial-workspace.css",
        "static/css/editorial-public.css",
        "static/css/editorial-calendar.css",
        "static/css/luna-home-hero.css",
        "static/css/luna-auth.css",
        "static/images/photos/beautyos-register-hero.webp",
        "static/images/photos/luna-salon-hero.webp",
        "static/images/logos/beautyos-logo-3d.webp",
        "static/images/photos/bg1.webp",
        "static/images/photos/bg2.webp",
        "static/images/photos/bg3.webp",
        "static/js/jalali-datepicker.js",
        "static/js/fa-money.js",
        "static/js/appointment-customer-picker.js",
        "static/js/time24-input.js",
    ):
        path = BASE_DIR / rel
        if path.is_file():
            stamps.append(int(path.stat().st_mtime))
    return str(max(stamps)) if stamps else "0"


BEAUTYOS_ASSET_VERSION = env("BEAUTYOS_ASSET_VERSION", default=_beautyos_asset_version())
