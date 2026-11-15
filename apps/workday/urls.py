from django.urls import path

from apps.workday import views

app_name = "workday"

urlpatterns = [
    path("", views.home, name="home"),
]
