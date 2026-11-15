from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from apps.salons.forms import SalonCreateForm, SalonProfileForm
from apps.salons.models import Salon, SalonMembership, SalonSettings


class SalonCreateView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if SalonMembership.objects.filter(user=request.user, is_active=True).exists():
            return redirect("dashboard:home")
        return render(request, "onboarding/salon_create.html", {"form": SalonCreateForm()})

    @transaction.atomic
    def post(self, request):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        form = SalonCreateForm(request.POST)
        if not form.is_valid():
            return render(request, "onboarding/salon_create.html", {"form": form})

        salon = form.save()
        SalonSettings.objects.create(salon=salon)
        SalonMembership.objects.create(
            user=request.user,
            salon=salon,
            role=SalonMembership.Role.OWNER,
        )
        request.session["active_salon_id"] = str(salon.id)
        request.session["onboarding_salon_id"] = str(salon.id)
        return redirect("salons_onboarding:profile")


class SalonProfileOnboardingView(View):
    def get(self, request):
        salon = self._get_onboarding_salon(request)
        if salon is None:
            return redirect("salons_onboarding:create")
        return render(
            request,
            "onboarding/salon_profile.html",
            {"form": SalonProfileForm(instance=salon), "salon": salon},
        )

    def post(self, request):
        salon = self._get_onboarding_salon(request)
        if salon is None:
            return redirect("salons_onboarding:create")
        form = SalonProfileForm(request.POST, instance=salon)
        if not form.is_valid():
            return render(
                request,
                "onboarding/salon_profile.html",
                {"form": form, "salon": salon},
            )
        form.save()
        request.session.pop("onboarding_salon_id", None)
        return redirect("dashboard:home")

    def _get_onboarding_salon(self, request):
        salon_id = request.session.get("onboarding_salon_id") or request.session.get("active_salon_id")
        if not salon_id:
            return None
        membership = SalonMembership.objects.filter(
            user=request.user,
            salon_id=salon_id,
            is_active=True,
            role__in=[SalonMembership.Role.OWNER, SalonMembership.Role.MANAGER],
        ).select_related("salon").first()
        return membership.salon if membership else None


@method_decorator(login_required, name="dispatch")
class SalonSwitchView(View):
    def _switch(self, request, salon_id):
        membership = SalonMembership.objects.filter(
            user=request.user,
            salon_id=salon_id,
            is_active=True,
        ).first()
        if membership:
            request.session["active_salon_id"] = str(salon_id)
        return redirect(request.POST.get("next") or request.GET.get("next") or request.META.get("HTTP_REFERER") or "/")

    def post(self, request, salon_id):
        return self._switch(request, salon_id)

    def get(self, request, salon_id):
        return self._switch(request, salon_id)
