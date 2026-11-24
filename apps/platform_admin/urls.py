from django.urls import path

from apps.platform_admin import views, subscription_views

app_name = "platform_admin"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("salons/", views.salons, name="salons"),
    path("subscriptions/", subscription_views.subscriptions, name="subscriptions"),
    path("salons/<uuid:salon_id>/", views.salon_detail, name="salon_detail"),
    path("salons/<uuid:salon_id>/status/", views.salon_status, name="salon_status"),
    path("users/", views.users, name="users"),
    path("users/<int:user_id>/", views.user_detail, name="user_detail"),
    path("users/<int:user_id>/status/", views.user_status, name="user_status"),
    path("reports/", views.reports, name="reports"),
    path("support/", views.support_tickets, name="support"),
    path("support/<int:ticket_id>/", views.ticket_detail, name="ticket_detail"),
    path("support/<int:ticket_id>/reply/", views.ticket_reply, name="ticket_reply"),
    path("inquiries/", views.public_inquiries, name="inquiries"),
    path("inquiries/<int:inquiry_id>/", views.public_inquiry_detail, name="inquiry_detail"),
    path("articles/", views.articles, name="articles"),
    path("articles/new/", views.article_edit, name="article_new"),
    path("articles/<int:article_id>/", views.article_edit, name="article_edit"),
    path("audit/", views.audit, name="audit"),
    path("system/", views.system, name="system"),
]
