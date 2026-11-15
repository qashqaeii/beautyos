from django.urls import path

from apps.expenses import views

app_name = "expenses"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("new/", views.create, name="create"),
]
