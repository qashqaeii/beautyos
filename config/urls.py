from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("apps.core.urls")),
    path("app/", include("apps.dashboard.urls")),
    path("control/", include("apps.platform_admin.urls")),
    path("support/", include("apps.platform_admin.urls_salon")),
    path("", include("apps.website.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("onboarding/", include("apps.salons.urls_onboarding")),
    path("members/", include("apps.salons.urls_members")),
    path("reception/", include("apps.reception.urls")),
    path("my-workday/", include("apps.workday.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("loyalty/", include("apps.loyalty.urls")),
    path("waitlist/", include("apps.waitlist.urls")),
    path("customers/", include("apps.customers.urls")),
    path("services/", include("apps.services.urls")),
    path("staff/", include("apps.staff.urls")),
    path("appointments/", include("apps.appointments.urls")),
    path("finance/", include("apps.finance.urls")),
    path("expenses/", include("apps.expenses.urls")),
    path("commissions/", include("apps.commissions.urls")),
    path("packages/", include("apps.packages.urls")),
    path("retention/", include("apps.retention.urls")),
    path("portfolio/", include("apps.portfolio.urls")),
    path("settings/", include("apps.salons.urls_settings")),
    path("s/", include("apps.salons.urls_public")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
