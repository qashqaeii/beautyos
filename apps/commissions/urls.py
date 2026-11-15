from django.urls import path

from apps.commissions import views

app_name = "commissions"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("rules/", views.rules_list, name="rules"),
    path("rules/new/", views.rule_create, name="rule_create"),
    path("settle/<int:staff_id>/", views.settle_staff, name="settle"),
]
