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


WIZARD_STEPS_TOTAL = 5


@method_decorator(login_required, name="dispatch")
class OnboardingWizardView(View):
    steps = {
        1: "onboarding/wizard/step_business.html",
        2: "onboarding/wizard/step_identity.html",
        3: "onboarding/wizard/step_services.html",
        4: "onboarding/wizard/step_staff.html",
        5: "onboarding/wizard/step_complete.html",
    }

    def get(self, request, step: int):
        step = max(1, min(step, WIZARD_STEPS_TOTAL))
        salon = _wizard_salon(request)
        if step > 1 and salon is None and step < WIZARD_STEPS_TOTAL:
            return redirect("salons_onboarding:wizard", step=1)

        if step == 1:
            form = OnboardingBusinessTypeForm(
                initial={"business_type": request.session.get(ow.SESSION_BUSINESS_TYPE) or (salon.business_type if salon else "")}
            )
        elif step == 2:
            form = OnboardingIdentityForm(instance=salon) if salon else OnboardingIdentityForm()
        elif step == 3:
            if not salon:
                return redirect("salons_onboarding:wizard", step=2)
            form = OnboardingServiceSetupForm(salon=salon)
        else:
            form = None

        ctx = self._base_context(request, step, salon, form)
        if step == 3 and salon:
            ctx["presets"] = presets_for(salon.business_type)
        if step == WIZARD_STEPS_TOTAL and salon:
            from apps.services.models import Service
            from apps.staff.models import StaffProfile

            ctx["stats"] = {
                "services": Service.scoped(salon).filter(is_deleted=False).count(),
                "staff": StaffProfile.scoped(salon).filter(is_deleted=False).count(),
            }
        return render(request, self.steps[step], ctx)

    def post(self, request, step: int):
        step = max(1, min(step, WIZARD_STEPS_TOTAL))
        salon = _wizard_salon(request)
        form = None

        if step == 1:
            form = OnboardingBusinessTypeForm(request.POST)
            if form.is_valid():
                bt = form.cleaned_data["business_type"]
                request.session[ow.SESSION_BUSINESS_TYPE] = bt
                if salon:
                    ow.apply_business_defaults(salon, bt)
                    return redirect("salons_onboarding:wizard", step=2)
                return redirect("salons_onboarding:wizard", step=2)
        elif step == 2:
            business_type = request.session.get(ow.SESSION_BUSINESS_TYPE) or Salon.BusinessType.COMBINED
            form = OnboardingIdentityForm(request.POST, request.FILES, instance=salon) if salon else OnboardingIdentityForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        if salon:
                            salon = form.save()
                            ow.apply_business_defaults(salon, business_type)
                        else:
                            salon = ow.create_salon_for_owner(
                                request.user,
                                name=form.cleaned_data["name"],
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
            form = OnboardingServiceSetupForm(request.POST, salon=salon)
            if form.is_valid():
                ow.create_selected_services(
                    salon,
                    form.cleaned_data.get("selected_presets") or [],
                    form.cleaned_data.get("custom_services") or [],
                )
                return redirect("salons_onboarding:wizard", step=4)
        elif step == 4:
            return redirect("salons_onboarding:wizard", step=5)
        elif step == WIZARD_STEPS_TOTAL:
            salon = _wizard_salon(request)
            if salon:
                ow.complete_onboarding(salon)
                request.session.pop(ow.SESSION_SALON_KEY, None)
                request.session.pop(ow.SESSION_BUSINESS_TYPE, None)
            return redirect("dashboard:home")

        ctx = self._base_context(request, step, salon, form)
        return render(request, self.steps.get(step, self.steps[1]), ctx)

    def _base_context(self, request, step, salon, form):
        return {
            "step": step,
            "steps_total": WIZARD_STEPS_TOTAL,
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
