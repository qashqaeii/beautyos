from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
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
    # Prefer middleware-validated active tenant over a stale onboarding session.
    salon_id = (
        getattr(getattr(request, "salon", None), "pk", None)
        or request.session.get(ow.SESSION_SALON_KEY)
        or request.session.get("active_salon_id")
    )
    if not salon_id:
        return None
    membership = SalonMembership.objects.filter(
        user=request.user,
        salon_id=salon_id,
        is_active=True,
        role=SalonMembership.Role.OWNER,
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

    def _step_redirect(self, request, step: int):
        if request.method == "POST" and step > 1:
            salon = _wizard_salon(request)
            if salon and ow.salon_needs_onboarding(salon):
                settings_obj = salon.settings
                if step > settings_obj.onboarding_step:
                    settings_obj.onboarding_step = step
                    settings_obj.save(update_fields=["onboarding_step", "updated_at"])
        result = redirect("salons_onboarding:wizard", step=step)
        if request.GET.get("modal") == "1":
            result["Location"] += "?modal=1"
        return result

    def _guard_step(self, request, step: int, salon: Salon | None):
        if salon is None and SalonMembership.objects.filter(user=request.user, is_active=True).exists():
            raise PermissionDenied
        if salon and not SalonMembership.objects.filter(
            user=request.user, salon=salon, role=SalonMembership.Role.OWNER, is_active=True
        ).exists():
            raise PermissionDenied
        # Step 2 creates the salon, so a new owner cannot have a salon yet.
        # Previous guard redirected its GET straight back to step 1, trapping
        # every first-time user in an onboarding loop.
        if salon is None:
            if step == 2 and not (request.session.get(ow.SESSION_SALON_NAME) or "").strip():
                return self._step_redirect(request, step=1)
            if 3 <= step <= WIZARD_STEPS_TOTAL:
                return self._step_redirect(request, step=1)
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
            form = OnboardingStaffForm(
                instance=profile, salon=salon,
                initial={"display_name": request.user.full_name, "is_bookable": False}
                if profile is None else None,
            )
        elif step == 5:
            form = None
        else:
            form = None

        ctx = self._base_context(request, step, salon, form)
        if step == 3 and salon:
            ctx["presets"] = presets_for(salon.business_type)
        if step == 4 and salon:
            ctx["salon_name"] = salon.name
        if step == 5 and salon:
            ctx["hours_rows"] = ow.salon_hours_grid(salon)
        if step == WIZARD_STEPS_TOTAL and salon:
            ctx["summary"] = ow.onboarding_summary(salon)
        return render(request, self.steps[step], ctx)

    def post(self, request, step: int):
        step = max(1, min(step, WIZARD_STEPS_TOTAL))
        salon = _wizard_salon(request)
        blocked = self._guard_step(request, step, salon)
        if blocked:
            return blocked
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
                return self._step_redirect(request, step=2)
        elif step == 2:
            salon_name = request.session.get(ow.SESSION_SALON_NAME, "").strip()
            if not salon_name:
                return self._step_redirect(request, step=1)
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
                    return self._step_redirect(request, step=3)
        elif step == 3:
            salon = _wizard_salon(request)
            if not salon:
                return self._step_redirect(request, step=2)
            if request.POST.get("action") == "skip":
                return self._step_redirect(request, step=4)
            form = OnboardingServiceSetupForm(request.POST, salon=salon)
            if form.is_valid():
                ow.create_selected_services(
                    salon,
                    form.cleaned_data.get("selected_presets") or [],
                    form.cleaned_data.get("custom_services") or [],
                )
                return self._step_redirect(request, step=4)
        elif step == 4:
            salon = _wizard_salon(request)
            if not salon:
                return self._step_redirect(request, step=2)
            if request.POST.get("action") == "skip":
                return self._step_redirect(request, step=5)
            profile = ow.get_owner_staff_profile(salon, request.user)
            if request.POST.get("is_bookable") != "on":
                # Leaving this unchecked does not create a specialist account.
                if profile and profile.is_bookable:
                    profile.is_bookable = False
                    profile.save(update_fields=["is_bookable", "updated_at"])
                return self._step_redirect(request, step=5)
            form = OnboardingStaffForm(request.POST, instance=profile, salon=salon)
            if form.is_valid():
                with transaction.atomic():
                    if profile is None:
                        profile = ow.ensure_owner_staff_profile(salon, request.user)
                        form.instance = profile
                    form.save()
                return self._step_redirect(request, step=5)
        elif step == 5:
            salon = _wizard_salon(request)
            if not salon:
                return self._step_redirect(request, step=2)
            if request.POST.get("action") == "skip":
                ow.apply_default_salon_work_hours(salon)
                ow.initialize_owner_specialist_hours(salon, request.user)
                return self._step_redirect(request, step=6)
            rows, hours_errors = ow.parse_work_hours_post(request.POST)
            if not hours_errors:
                ow.save_salon_work_hours(salon, rows)
                ow.initialize_owner_specialist_hours(salon, request.user)
                return self._step_redirect(request, step=6)
        elif step == WIZARD_STEPS_TOTAL:
            salon = _wizard_salon(request)
            if not salon:
                return self._step_redirect(request, step=1)
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
            ctx["hours_rows"] = ow.salon_hours_grid(salon)
            ctx["hours_errors"] = hours_errors
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
            "wizard_base_template": (
                "onboarding/wizard/modal_shell.html"
                if request.GET.get("modal") == "1"
                else "layouts/public_wizard.html"
            ),
        }


@method_decorator(login_required, name="dispatch")
class OnboardingLegacyRedirect(View):
    def get(self, request):
        if SalonMembership.objects.filter(user=request.user, is_active=True).exists():
            return redirect("dashboard:home")
        return redirect("salons_onboarding:wizard", step=1)

@login_required
@require_POST
def defer_onboarding(request):
    """Keep setup unfinished while persisting the owner's 'later' choice."""
    membership = getattr(request, "membership", None)
    if not request.salon or not membership or membership.role != SalonMembership.Role.OWNER:
        raise PermissionDenied
    if ow.salon_needs_onboarding(request.salon):
        settings_obj = request.salon.settings
        settings_obj.onboarding_deferred_at = timezone.now()
        settings_obj.save(update_fields=["onboarding_deferred_at", "updated_at"])
    return JsonResponse({"ok": True})
