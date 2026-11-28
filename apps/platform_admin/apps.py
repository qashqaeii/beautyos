from django.apps import AppConfig


class PlatformAdminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.platform_admin"
    verbose_name = "مدیریت مرکزی BeautyOS"

    def ready(self):
        from apps.platform_admin import signals  # noqa: F401
