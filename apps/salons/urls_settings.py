from django.urls import path

from apps.salons import views_settings

app_name = "salons_settings"

urlpatterns = [
    path("", views_settings.salon_settings, name="home"),
]
