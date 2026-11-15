from django.urls import path

from apps.waitlist import views

app_name = "waitlist"

urlpatterns = [
    path("", views.queue, name="queue"),
    path("<int:pk>/confirm/", views.confirm_appointment, name="confirm"),
]
