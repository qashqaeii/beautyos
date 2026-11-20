from django.urls import path

from apps.retention import views, campaign_views, automation_views

app_name = "retention"

urlpatterns = [
    path("", views.follow_up_queue, name="queue"),
    path("campaigns/",campaign_views.campaigns,name="campaigns"),
    path("automation/",automation_views.automation,name="automation"),
    path("campaigns/<int:pk>/",campaign_views.campaign_detail,name="campaign_detail"),
    path("<int:pk>/done/", views.follow_up_done, name="done"),
]
