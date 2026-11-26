from django.urls import path

from apps.dashboard import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("management/", views.management, name="management"),
    path("specialists/", views.specialists, name="specialists"),
    path("my-workspace/", views.specialist_workspace, name="specialist_workspace"),
]
