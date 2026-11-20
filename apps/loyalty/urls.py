from django.urls import path

from apps.loyalty import views

app_name = "loyalty"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("program/", views.program_settings, name="program"),
    path("<int:pk>/", views.member_detail, name="member"),
]
