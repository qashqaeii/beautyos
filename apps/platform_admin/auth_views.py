"""Dedicated central-operator login; use the existing verified OTP flow."""
from django.shortcuts import redirect, render

from apps.accounts.forms import PhoneForm
from apps.accounts.models import User
from apps.accounts.views import LoginView


class PlatformLoginView(LoginView):
    template_name = "platform_admin/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            if request.user.is_active and request.user.is_superuser:
                return redirect("platform_admin:overview")
            return render(request, self.template_name, {
                "phone_form": PhoneForm(), "switch_account": True,
            })
        return render(request, self.template_name, {"phone_form": PhoneForm()})

    def post(self, request):
        if request.user.is_authenticated:
            if request.user.is_active and request.user.is_superuser:
                return redirect("platform_admin:overview")
            return render(request, self.template_name, {
                "phone_form": PhoneForm(), "switch_account": True,
            }, status=403)

        form = PhoneForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"phone_form": form})

        # PhoneForm returns canonical E.164, matching ensure_superuser.
        # Never provision privileged users from a public login request.
        if not User.objects.filter(
            phone=form.cleaned_data["phone"], is_active=True, is_superuser=True
        ).exists():
            form.add_error(None, "حساب مدیریت مرکزی برای این شماره فعال نیست.")
            return render(request, self.template_name, {"phone_form": form}, status=403)

        # Existing verification page already displays the development OTP when
        # DEBUG is enabled. Keep that redirect: rendering the phone form here
        # would strand the user instead of advancing to OTP verification.
        return super().post(request)
