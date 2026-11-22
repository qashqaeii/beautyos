from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

from apps.salons import onboarding_wizard as ow
from apps.salons.business_catalog import presets_for
from apps.salons.forms_wizard import (
    OnboardingBusinessTypeForm,
    OnboardingIdentityForm,
    OnboardingServiceSetupForm,
    OnboardingStaffForm,
)
from apps.salons.models import Salon, SalonMembership
from apps.salons.themes import LUNA_SIGNATURE_TOKENS, resolve_global_dashboard_theme


def _wizard_salon(request) -> Salon | None:
    salon_id = request.session.get(ow.SESSION_SALON_KEY) or request.session.get("active_salon_id")
    if not salon_id:
        return None
    membership = SalonMembership.objects.filter(
        user=request.user,
        salon_id=salon_id,
        is_active=True,
        role__in=[SalonMembership.Role.OWNER, SalonMembership.Role.MANAGER],
    ).select_related("salon", "salon__settings").first()
    return membership.salon if membership else None


WIZARD_STEPS_TOTAL = 6


@method_decorator(login_required, name="dispatch")
class OnboardingWizardView(View):
    steps = {
        1: "onboarding/wizard/step_business.html",
        2: "onboarding/wizard/step_identity.html",
        3: "onboarding/wizard/step_services.html",
        4: "onboarding/wizard/step_staff.html",
        5: "onboarding/wizard/step_hours.html",
        6: "onboarding/wizard/step_complete.html",
    }

    def _guard_step(self, request, step: int, salon: Salon | None):
        # Step 2 creates the salon, so a new owner cannot have a salon yet.
        # Previous guard redirected its GET straight back to step 1, trapping
        # every first-time user in an onboarding loop.
        if salon is None:
            if step == 2 and not (request.session.get(ow.SESSION_SALON_NAME) or "").strip():
                return redirect("salons_onboarding:wizard", step=1)
            if 3 <= step < WIZARD_STEPS_TOTAL:
                return redirect("salons_onboarding:wizard", step=1)
        if salon and not ow.salon_needs_onboarding(salon) and step < WIZARD_STEPS_TOTAL:
            return redirect("dashboard:home")
        return None

    def get(self, request, step: int):
        step = max(1, min(step, WIZARD_STEPS_TOTAL))
        salon = _wizard_salon(request)
        blocked = self._guard_step(request, step, salon)
        if blocked:
            return blocked

        salon_name = request.session.get(ow.SESSION_SALON_NAME) or (salon.name if salon else "")

        if step == 1:
            form = OnboardingBusinessTypeForm(
                initial={"name": salon_name}
            )
        elif step == 2:
            form = (
                OnboardingIdentityForm(instance=salon, salon_name=salon_name)
                if salon
                else OnboardingIdentityForm(salon_name=salon_name)
            )
        elif step == 3:
            form = OnboardingServiceSetupForm(salon=salon)
        elif step == 4:
            profile = ow.get_owner_staff_profile(salon, request.user) if salon else None
            if profile is None and salon:
                profile = ow.ensure_owner_staff_profile(salon, request.user)
            form = OnboardingStaffForm(instance=profile, salon=salon) if profile else None
        elif step == 5:
            profile = ow.get_owner_staff_profile(salon, request.user) if salon else None
            form = None
        else:
            form = None

        ctx = self._base_context(request, step, salon, form)
        if step == 3 and salon:
            ctx["presets"] = presets_for(salon.business_type)
        if step == 4 and salon:
            ctx["salon_name"] = salon.name
        if step == 5 and salon:
            profile = ow.get_owner_staff_profile(salon, request.user)
            if profile is None:
                profile = ow.ensure_owner_staff_profile(salon, request.user)
            ctx["hours_rows"] = ow.work_hours_grid(profile)
            ctx["owner_staff"] = profile
        if step == WIZARD_STEPS_TOTAL and salon:
            ctx["summary"] = ow.onboarding_summary(salon)
        return render(request, self.steps[step], ctx)

    def post(self, request, step: int):
        step = max(1, min(step, WIZARD_STEPS_TOTAL))
        salon = _wizard_salon(request)
        form = None
        hours_errors = None

        if step == 1:
            form = OnboardingBusinessTypeForm(request.POST)
            if form.is_valid():
                # The onboarding flow is women-only; ignore client-supplied business_type.
                request.session[ow.SESSION_BUSINESS_TYPE] = Salon.BusinessType.BEAUTY_WOMEN
                request.session[ow.SESSION_SALON_NAME] = form.cleaned_data["name"]
                if salon:
                    salon.name = form.cleaned_data["name"]
                    salon.save(update_fields=["name", "updated_at"])
                    ow.apply_business_defaults(salon, Salon.BusinessType.BEAUTY_WOMEN)
                return redirect("salons_onboarding:wizard", step=2)
        elif step == 2:
            salon_name = request.session.get(ow.SESSION_SALON_NAME, "").strip()
            if not salon_name:
                return redirect("salons_onboarding:wizard", step=1)
            business_type = Salon.BusinessType.BEAUTY_WOMEN
            form = (
                OnboardingIdentityForm(request.POST, request.FILES, instance=salon, salon_name=salon_name)
                if salon
                else OnboardingIdentityForm(request.POST, request.FILES, salon_name=salon_name)
            )
            if form.is_valid():
                try:
                    with transaction.atomic():
                        if salon:
                            salon = form.save()
                            salon.name = salon_name
                            salon.save(update_fields=["name", "updated_at"])
                            ow.apply_business_defaults(salon, business_type)
                        else:
                            salon = ow.create_salon_for_owner(
                                request.user,
                                name=salon_name,
                                slug=form.cleaned_data["slug"],
                                public_phone=form.cleaned_data.get("public_phone", ""),
                                city=form.cleaned_data.get("city", ""),
                                address=form.cleaned_data.get("address", ""),
                                tagline=form.cleaned_data.get("tagline", ""),
                                description=form.cleaned_data.get("description", ""),
                                business_type=business_type,
                                logo=form.cleaned_data.get("logo"),
                            )
                        request.session[ow.SESSION_SALON_KEY] = str(salon.id)
                        request.session["active_salon_id"] = str(salon.id)
                except ValidationError as exc:
                    form.add_error(None, exc.message if hasattr(exc, "message") else str(exc))
                else:
                    return redirect("salons_onboarding:wizard", step=3)
        elif step == 3:
            salon = _wizard_salon(request)
            if not salon:
                return redirect("salons_onboarding:wizard", step=2)
            if request.POST.get("action") == "skip":
                return redirect("salons_onboarding:wizard", step=4)
            form = OnboardingServiceSetupForm(request.POST, salon=salon)
            if form.is_valid():
                ow.create_selected_services(
                    salon,
                    form.cleaned_data.get("selected_presets") or [],
                    form.cleaned_data.get("custom_services") or [],
                )
                return redirect("salons_onboarding:wizard", step=4)
        elif step == 4:
            salon = _wizard_salon(request)
            if not salon:
                return redirect("salons_onboarding:wizard", step=2)
            if request.POST.get("action") == "skip":
                ow.ensure_owner_staff_profile(salon, request.user)
                return redirect("salons_onboarding:wizard", step=5)
            profile = ow.ensure_owner_staff_profile(salon, request.user)
            form = OnboardingStaffForm(request.POST, instance=profile, salon=salon)
            if form.is_valid():
                form.save()
                return redirect("salons_onboarding:wizard", step=5)
        elif step == 5:
            salon = _wizard_salon(request)
            if not salon:
                return redirect("salons_onboarding:wizard", step=2)
            if request.POST.get("action") == "skip":
                profile = ow.ensure_owner_staff_profile(salon, request.user)
                ow.apply_default_work_hours(profile)
                return redirect("salons_onboarding:wizard", step=6)
            profile = ow.ensure_owner_staff_profile(salon, request.user)
            rows, hours_errors = ow.parse_work_hours_post(request.POST)
            if not hours_errors:
                ow.save_staff_work_hours(profile, rows)
                return redirect("salons_onboarding:wizard", step=6)
        elif step == WIZARD_STEPS_TOTAL:
            salon = _wizard_salon(request)
            if not salon:
                return redirect("salons_onboarding:wizard", step=1)
            if not ow.salon_needs_onboarding(salon):
                request.session.pop(ow.SESSION_SALON_KEY, None)
                request.session.pop(ow.SESSION_BUSINESS_TYPE, None)
                request.session.pop(ow.SESSION_SALON_NAME, None)
                return redirect("dashboard:home")
            ow.complete_onboarding(salon)
            request.session.pop(ow.SESSION_SALON_KEY, None)
            request.session.pop(ow.SESSION_BUSINESS_TYPE, None)
            request.session.pop(ow.SESSION_SALON_NAME, None)
            return redirect("dashboard:home")

        ctx = self._base_context(request, step, salon, form)
        if step == 3 and salon:
            ctx["presets"] = presets_for(salon.business_type)
        if step == 5 and salon:
            profile = ow.get_owner_staff_profile(salon, request.user) or ow.ensure_owner_staff_profile(
                salon, request.user
            )
            ctx["hours_rows"] = ow.work_hours_grid(profile)
            ctx["hours_errors"] = hours_errors
            ctx["owner_staff"] = profile
        if step == WIZARD_STEPS_TOTAL and salon:
            ctx["summary"] = ow.onboarding_summary(salon)
        return render(request, self.steps.get(step, self.steps[1]), ctx)

    def _base_context(self, request, step, salon, form):
        salon_name = request.session.get(ow.SESSION_SALON_NAME) or (salon.name if salon else "")
        return {
            "step": step,
            "steps_total": WIZARD_STEPS_TOTAL,
            "wizard_step_labels": ow.WIZARD_STEP_LABELS,
            "salon_name": salon_name,
            "form": form,
            "salon": salon,
            "theme_preview": LUNA_SIGNATURE_TOKENS,
            "global_theme_key": resolve_global_dashboard_theme(),
            "global_theme_label": "Editorial Rose",
        }


@method_decorator(login_required, name="dispatch")
class OnboardingLegacyRedirect(View):
    def get(self, request):
        if SalonMembership.objects.filter(user=request.user, is_active=True).exists():
            salon = _wizard_salon(request) or SalonMembership.objects.filter(
                user=request.user, is_active=True
            ).select_related("salon__settings").first().salon
            if salon and ow.salon_needs_onboarding(salon):
                return redirect("salons_onboarding:wizard", step=1)
            return redirect("dashboard:home")
        return redirect("salons_onboarding:wizard", step=1)