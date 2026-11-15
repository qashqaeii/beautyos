from django.urls import path

from apps.portfolio import views

app_name = "portfolio"

urlpatterns = [
    path("", views.portfolio_list, name="list"),
    path("new/", views.portfolio_create, name="create"),
    path("<int:pk>/edit/", views.portfolio_edit, name="edit"),
]
