from django.urls import path

from apps.platform_admin import views

app_name = "salon_support"

urlpatterns = [
    path("", views.salon_support, name="home"),
    path("new/", views.salon_ticket_new, name="new"),
    path("<int:ticket_id>/", views.salon_ticket_detail, name="detail"),
]
