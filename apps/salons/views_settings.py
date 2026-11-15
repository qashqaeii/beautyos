from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.salons import onboarding_wizard as ow
from apps.salons.decorators import salon_required
from apps.salons.forms_settings import SalonProfileForm, SalonRetentionSettingsForm
from apps.salons.permissions_policy import P_SALON_SETTINGS, require_permission


def _owner_staff(request):
    return ow.get_owner_staff_profile(request.salon, request.user) or ow.ensure_owner_staff_profile(
        request.salon, request.user
    )


@salon_required
@require_permission(P_SALON_SETTINGS)
@require_http_methods(["GET", "POST"])
def salon_settings(request):
    salon = request.salon
    settings_obj = salon.settings
    profile_form = SalonProfileForm(instance=salon)
    retention_form = SalonRetentionSettingsForm(instance=settings_obj)
    owner_staff = _owner_staff(request)
    hours_rows = ow.work_hours_grid(owner_staff)
    hours_errors = []

    if request.method == "POST":
        form_kind = request.POST.get("form_kind", "profile")

        if form_kind == "clear_logo":
            if salon.logo:
                salon.logo.delete(save=False)
                salon.logo = None
                salon.save(update_fields=["logo", "updated_at"])
            messages.success(request, "لوگو حذف شد.")
            return redirect("salons_settings:home")

        if form_kind == "hours":
            rows, hours_errors = ow.parse_work_hours_post(request.POST)
            if hours_errors:
                messages.error(request, "لطفاً ساعات کاری را اصلاح کنید.")
            else:
                ow.save_staff_work_hours(owner_staff, rows)
                messages.success(request, "ساعات فعالیت ذخیره شد.")
                return redirect("salons_settings:home")

        if form_kind == "retention":
            retention_form = SalonRetentionSettingsForm(request.POST, instance=settings_obj)
            if retention_form.is_valid():
                retention_form.save()
                messages.success(request, "قوانین رزرو و پیگیری ذخیره شد.")
                return redirect("salons_settings:home")

        if form_kind == "profile":
            profile_form = SalonProfileForm(request.POST, request.FILES, instance=salon)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "اطلاعات سالن ذخیره شد.")
                return redirect("salons_settings:home")

    public_url = request.build_absolute_uri(reverse("salons_public:landing", kwargs={"slug": salon.slug}))

    return render(
        request,
        "settings/salon.html",
        {
            "salon": salon,
            "profile_form": profile_form,
            "retention_form": retention_form,
            "owner_staff": owner_staff,
            "hours_rows": hours_rows,
            "hours_errors": hours_errors,
            "public_url": public_url,
            "business_type_label": salon.get_business_type_display(),
        },
    )