from django.apps import AppConfig


class CommissionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.commissions"
    verbose_name = "پورسانت"

    def ready(self):
        from apps.commissions import signals  # noqa: F401
