"""Dedicated entry point for central operators; shares the existing OTP security flow."""
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
            # A salon session must not silently become a central operator.
            return render(request, self.template_name, {"phone_form": PhoneForm(), "switch_account": True})
        return render(request, self.template_name, {"phone_form": PhoneForm()})

    def post(self, request):
        if request.user.is_authenticated and not (request.user.is_active and request.user.is_superuser):
            return render(request, self.template_name, {"phone_form": PhoneForm(), "switch_account": True}, status=403)
        form = PhoneForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"phone_form": form})
        # Generic error avoids disclosing which phone numbers have privileged accounts.
        if not User.objects.filter(phone=form.cleaned_data["phone"], is_active=True, is_superuser=True).exists():
            form.add_error(None, "ورود مدیر مرکزی امکان‌پذیر نیست. اطلاعات حساب را بررسی کنید.")
            return render(request, self.template_name, {"phone_form": form})
        return super().post(request)
