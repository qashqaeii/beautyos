from django.urls import path

from apps.reception import views

app_name = "reception"

urlpatterns = [
    path("", views.desk, name="desk"),
    path("checkin/<int:pk>/", views.quick_checkin, name="checkin"),
]
