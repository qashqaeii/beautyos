from django.urls import path

from apps.packages import views

app_name = "packages"

urlpatterns = [
    path("", views.package_list, name="list"),
    path("new/", views.package_create, name="create"),
    path("sell/", views.sell, name="sell"),
]
