from django.urls import path

from apps.loyalty import views, reward_views, benefit_views

app_name = "loyalty"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("program/", views.program_settings, name="program"),
    path("rewards/", reward_views.rewards, name="rewards"),
    path("birthdays/", reward_views.birthdays, name="birthdays"),
    path("referrals/", benefit_views.referrals, name="referrals"),
    path("vouchers/", benefit_views.vouchers, name="vouchers"),
    path("<int:pk>/", views.member_detail, name="member"),
]
