from django.urls import path

from apps.staff import views

app_name = "staff"

urlpatterns = [
    path("", views.staff_list, name="list"),
    path("add/", views.staff_create, name="create"),
    path("<int:pk>/", views.staff_detail, name="detail"),
    path("<int:pk>/edit/", views.staff_edit, name="edit"),
    path("<int:pk>/hours/", views.staff_hours, name="hours"),
    path("<int:pk>/time-off/", views.staff_time_off, name="time_off"),
]
