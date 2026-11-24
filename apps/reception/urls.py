from django.urls import path

from apps.reception import views

app_name = "reception"

urlpatterns = [
    path("", views.desk, name="desk"),
    path("confirm/<int:pk>/", views.quick_confirm, name="confirm"),
    path("checkin/<int:pk>/", views.quick_checkin, name="checkin"),
    path("complete/<int:pk>/", views.quick_complete, name="complete"),
]
