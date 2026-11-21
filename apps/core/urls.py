"""Liveness and database readiness probes with no sensitive data in responses."""
from django.db import connections
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@require_GET
@never_cache
def health(request):
    """Cheap liveness: never depends on the database."""
    return JsonResponse({"status": "ok", "product": "BeautyOS"})


@require_GET
@never_cache
def ready(request):
    """Readiness: return 503 if the default database cannot answer a query."""
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        # Do not leak DB credentials, driver details or connection strings.
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", health, name="health"),
    path("ready/", ready, name="ready"),
]
