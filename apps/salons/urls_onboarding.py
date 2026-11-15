from django.urls import path

from apps.salons import views_onboarding, views_wizard

app_name = "salons_onboarding"

urlpatterns = [
    path("create/", views_wizard.OnboardingLegacyRedirect.as_view(), name="create"),
    path("profile/", views_wizard.OnboardingLegacyRedirect.as_view(), name="profile"),
    path("wizard/<int:step>/", views_wizard.OnboardingWizardView.as_view(), name="wizard"),
    path("switch/<uuid:salon_id>/", views_onboarding.SalonSwitchView.as_view(), name="switch"),
]
