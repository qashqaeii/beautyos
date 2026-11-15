from django.urls import path

from apps.accounts import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("verify/", views.VerifyOTPView.as_view(), name="verify"),
    path("register/profile/", views.RegisterProfileView.as_view(), name="register_profile"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
]
