from django.contrib import messages
from django.shortcuts import redirect, render

from apps.core.tenant import require_salon_access
from apps.salons.decorators import salon_required
from apps.salons.forms_settings import SalonRetentionSettingsForm, SalonSettingsForm
from apps.salons.models import SalonMembership


@salon_required
def salon_settings(request):
    require_salon_access(request.user, request.salon, SalonMembership.Role.MANAGER)
    settings_obj = request.salon.settings
    if request.method == "POST":
        salon_form = SalonSettingsForm(request.POST, request.FILES, instance=request.salon)
        retention_form = SalonRetentionSettingsForm(request.POST, instance=settings_obj)
        if salon_form.is_valid() and retention_form.is_valid():
            salon_form.save()
            retention_form.save()
            messages.success(request, "تنظیمات ذخیره شد.")
            return redirect("salons_settings:home")
    else:
        salon_form = SalonSettingsForm(instance=request.salon)
        retention_form = SalonRetentionSettingsForm(instance=settings_obj)
    return render(
        request,
        "settings/salon.html",
        {
            "salon_form": salon_form,
            "retention_form": retention_form,
            "salon": request.salon,
            "stored_dashboard_theme": settings_obj.dashboard_theme,
        },
    )
