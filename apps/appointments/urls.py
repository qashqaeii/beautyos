from django.urls import path

from apps.appointments import views

app_name = "appointments"

urlpatterns = [
    path("", views.calendar_day, name="calendar"),
    path("week/", views.calendar_week, name="calendar_week"),
    path("list/", views.appointment_list, name="list"),
    path("new/", views.appointment_create, name="create"),
    path("<int:pk>/", views.appointment_detail, name="detail"),
]
