from django.urls import path

from apps.retention import views

app_name = "retention"

urlpatterns = [
    path("", views.follow_up_queue, name="queue"),
    path("<int:pk>/done/", views.follow_up_done, name="done"),
]
