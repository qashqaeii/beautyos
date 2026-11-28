"""Dedicated central-operator login; use the existing verified OTP flow."""
from django.conf import settings
from django.shortcuts import redirect, render

from apps.accounts.forms import PhoneForm
from apps.accounts.models import User
from apps.accounts.views import LoginView

PLATFORM_AUTH_FLOW = "platform"


class PlatformLoginView(LoginView):
    template_name = "platform_admin/login.html"

    def _login_page_context(self, request, phone_form):
        ctx = {"phone_form": phone_form}
        if settings.DEBUG and request.session.get("auth_flow") == PLATFORM_AUTH_FLOW:
            if request.session.get("dev_otp_code"):
                ctx["dev_otp_code"] = request.session["dev_otp_code"]
        return ctx

    def get(self, request):
        if request.user.is_authenticated:
            if request.user.is_active and request.user.is_superuser:
                return redirect("platform_admin:overview")
            return render(request, self.template_name, {
                "phone_form": PhoneForm(), "switch_account": True,
            })
        return render(request, self.template_name, self._login_page_context(request, PhoneForm()))

    def post(self, request):
        if request.user.is_authenticated:
            if request.user.is_active and request.user.is_superuser:
                return redirect("platform_admin:overview")
            return render(request, self.template_name, {
                "phone_form": PhoneForm(), "switch_account": True,
            }, status=403)

        form = PhoneForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                self._login_page_context(request, form),
            )

        phone = form.cleaned_data["phone"]
        # PhoneForm returns canonical E.164, matching ensure_superuser.
        # Never provision privileged users from a public login request.
        if not User.objects.filter(phone=phone, is_active=True, is_superuser=True).exists():
            msg = "حساب مدیریت مرکزی برای این شماره فعال نیست."
            if settings.DEBUG and User.objects.filter(phone=phone, is_active=True).exists():
                msg += (
                    " در محیط توسعه، دستور "
                    "`python manage.py ensure_superuser --phone 09357930033 "
                    "--name \"مدیر پلتفرم\" --local-otp-only` را اجرا کنید."
                )
            form.add_error(None, msg)
            return render(
                request,
                self.template_name,
                self._login_page_context(request, form),
                status=403,
            )

        request.session["auth_flow"] = PLATFORM_AUTH_FLOW
        request.session.modified = True
        # Existing verification page displays the development OTP when DEBUG is enabled.
        return super().post(request)
