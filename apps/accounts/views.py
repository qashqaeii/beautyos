from datetime import timedelta
from ipaddress import ip_address

from django.conf import settings
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.accounts.forms import OTPVerifyForm, PhoneForm, RegisterProfileForm
from apps.accounts.models import OTPChallenge, User
from apps.accounts.services.otp import OTPDeliveryError, OTPInvalid, OTPRateLimited, issue_otp, verify_otp
from apps.accounts.services.register_verification import (
    RegisterAccountExistsError,
    RegisterVerificationError,
    clear_register_session_flags,
    complete_register_profile,
    get_valid_register_verification,
    grant_register_verification_after_otp,
    invalidate_register_verifications,
)
from apps.core.utils.phone import display_iran_mobile

OTP_RESEND_COOLDOWN_SECONDS = 60


def _store_dev_otp(request, issued):
    request.session.pop("dev_otp_code", None)
    if settings.DEBUG and issued.dev_code:
        request.session["dev_otp_code"] = issued.dev_code
    request.session["otp_issued_at"] = issued.challenge.created_at.isoformat()


def _otp_issued_at(request):
    raw = request.session.get("otp_issued_at")
    if not raw:
        return None
    try:
        parsed = timezone.datetime.fromisoformat(raw)
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    except (TypeError, ValueError):
        return None


def _verify_context(request, *, phone, otp_form, purpose, next_step=""):
    issued_at = _otp_issued_at(request)
    now = timezone.now()
    resend_at = None
    if issued_at:
        resend_at = issued_at + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)
    expires_at = None
    if issued_at:
        expires_at = issued_at + timedelta(seconds=settings.BEAUTYOS_OTP_EXPIRY_SECONDS)
    return {
        "phone_display": display_iran_mobile(phone),
        "otp_form": otp_form,
        "purpose": purpose,
        "next_step": next_step,
        "dev_otp_code": request.session.get("dev_otp_code") if settings.DEBUG and request.session.get("auth_phone") == phone else None,
        "otp_resend_at_iso": resend_at.isoformat() if resend_at else "",
        "otp_expires_at_iso": expires_at.isoformat() if expires_at else "",
        "can_resend_now": resend_at is None or now >= resend_at,
    }


def _client_ip(request):
    # Do not trust an arbitrary client-supplied X-Forwarded-For header.
    try:
        return str(ip_address(request.META.get("REMOTE_ADDR", "")))
    except ValueError:
        return None


def _clear_pending_auth_session(request):
    clear_register_session_flags(request)
    for key in ("auth_phone", "auth_purpose", "auth_next_step", "dev_otp_code", "otp_issued_at"):
        request.session.pop(key, None)
    request.session.modified = True


def _begin_auth_session(request, *, phone: str, purpose: str, issued, next_step: str = ""):
    invalidate_register_verifications(request=request)
    clear_register_session_flags(request)
    request.session["auth_phone"] = phone
    request.session["auth_purpose"] = purpose
    if next_step:
        request.session["auth_next_step"] = next_step
    else:
        request.session.pop("auth_next_step", None)
    _store_dev_otp(request, issued)


class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(request, self.template_name, {"phone_form": PhoneForm()})

    def post(self, request):
        step = request.POST.get("step", "phone")
        if step == "phone":
            form = PhoneForm(request.POST)
            if not form.is_valid():
                return render(request, self.template_name, {"phone_form": form})
            phone = form.cleaned_data["phone"]
            try:
                issued = issue_otp(
                    phone=phone,
                    purpose=OTPChallenge.Purpose.LOGIN,
                    request_ip=_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            except (OTPRateLimited, OTPInvalid, OTPDeliveryError) as exc:
                form.add_error(None, str(exc))
                return render(request, self.template_name, {"phone_form": form})
            _begin_auth_session(
                request,
                phone=phone,
                purpose=OTPChallenge.Purpose.LOGIN,
                issued=issued,
            )
            return redirect("accounts:verify")
        return redirect("accounts:login")


class RegisterView(View):
    template_name = "accounts/register.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(request, self.template_name, {"phone_form": PhoneForm()})

    def post(self, request):
        form = PhoneForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"phone_form": form})
        phone = form.cleaned_data["phone"]
        if User.objects.filter(phone=phone).exists():
            form.add_error("phone", "این شماره قبلاً ثبت شده است. از ورود استفاده کنید.")
            return render(request, self.template_name, {"phone_form": form})
        try:
            issued = issue_otp(
                phone=phone,
                purpose=OTPChallenge.Purpose.REGISTER,
                request_ip=_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except (OTPRateLimited, OTPInvalid, OTPDeliveryError) as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {"phone_form": form})
        _begin_auth_session(
            request,
            phone=phone,
            purpose=OTPChallenge.Purpose.REGISTER,
            issued=issued,
            next_step="register_profile",
        )
        return redirect("accounts:verify")


class VerifyOTPView(View):
    def _change_number_url(self, purpose):
        if purpose == OTPChallenge.Purpose.REGISTER:
            return reverse("accounts:register")
        return reverse("accounts:login")

    def get(self, request):
        phone = request.session.get("auth_phone")
        purpose = request.session.get("auth_purpose")
        if not phone or not purpose:
            return redirect("accounts:login")
        ctx = _verify_context(
            request,
            phone=phone,
            otp_form=OTPVerifyForm(),
            purpose=purpose,
            next_step=request.session.get("auth_next_step", ""),
        )
        ctx["change_number_url"] = self._change_number_url(purpose)
        return render(request, "accounts/verify_otp.html", ctx)

    def post(self, request):
        phone = request.session.get("auth_phone")
        purpose = request.session.get("auth_purpose")
        if not phone or not purpose:
            return redirect("accounts:login")

        if request.POST.get("action") == "resend":
            issued_at = _otp_issued_at(request)
            if issued_at and timezone.now() < issued_at + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS):
                ctx = _verify_context(
                    request,
                    phone=phone,
                    otp_form=OTPVerifyForm(),
                    purpose=purpose,
                    next_step=request.session.get("auth_next_step", ""),
                )
                ctx["change_number_url"] = self._change_number_url(purpose)
                ctx["resend_error"] = "لطفاً چند ثانیه صبر کنید و دوباره تلاش کنید."
                return render(request, "accounts/verify_otp.html", ctx)
            try:
                issued = issue_otp(
                    phone=phone,
                    purpose=purpose,
                    request_ip=_client_ip(request),
                    user_agent=request.META.get("HTTP_USER_AGENT", ""),
                )
            except (OTPRateLimited, OTPInvalid, OTPDeliveryError) as exc:
                ctx = _verify_context(
                    request,
                    phone=phone,
                    otp_form=OTPVerifyForm(),
                    purpose=purpose,
                    next_step=request.session.get("auth_next_step", ""),
                )
                ctx["change_number_url"] = self._change_number_url(purpose)
                ctx["resend_error"] = str(exc)
                return render(request, "accounts/verify_otp.html", ctx)
            _store_dev_otp(request, issued)
            ctx = _verify_context(
                request,
                phone=phone,
                otp_form=OTPVerifyForm(),
                purpose=purpose,
                next_step=request.session.get("auth_next_step", ""),
            )
            ctx["change_number_url"] = self._change_number_url(purpose)
            ctx["resend_ok"] = True
            return render(request, "accounts/verify_otp.html", ctx)

        form = OTPVerifyForm(request.POST)
        next_step = request.POST.get("next_step", "") or request.session.get("auth_next_step", "")
        if not form.is_valid():
            ctx = _verify_context(request, phone=phone, otp_form=form, purpose=purpose, next_step=next_step)
            ctx["change_number_url"] = self._change_number_url(purpose)
            return render(request, "accounts/verify_otp.html", ctx)

        try:
            challenge = verify_otp(phone=phone, purpose=purpose, code=form.cleaned_data["code"])
        except OTPInvalid as exc:
            form.add_error("code", str(exc))
            ctx = _verify_context(request, phone=phone, otp_form=form, purpose=purpose, next_step=next_step)
            ctx["change_number_url"] = self._change_number_url(purpose)
            return render(request, "accounts/verify_otp.html", ctx)

        if purpose == OTPChallenge.Purpose.REGISTER:
            grant_register_verification_after_otp(request=request, phone=phone, challenge=challenge)
            return render(
                request,
                "accounts/register_profile.html",
                {"profile_form": RegisterProfileForm(), "phone_display": display_iran_mobile(phone)},
            )

        invalidate_register_verifications(request=request)
        user = User.objects.filter(phone=phone).first()
        if user is None:
            return redirect("accounts:register")
        if not user.is_active:
            _clear_pending_auth_session(request)
            return redirect("accounts:login")

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        _clear_pending_auth_session(request)
        from apps.salons.middleware import sync_login_active_salon

        sync_login_active_salon(request, user)
        return redirect(self._post_login_redirect(request, user))

    def _post_login_redirect(self, request, user):
        from apps.salons.models import SalonMembership

        if SalonMembership.objects.filter(user=user, is_active=True).exists():
            return reverse("dashboard:home")
        return reverse("salons_onboarding:create")


class RegisterProfileView(View):
    def post(self, request):
        verification = get_valid_register_verification(request=request)
        if verification is None:
            return redirect("accounts:register")

        phone = verification.phone
        form = RegisterProfileForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "accounts/register_profile.html",
                {"profile_form": form, "phone_display": display_iran_mobile(phone)},
            )

        try:
            user = complete_register_profile(
                request=request,
                verification=verification,
                full_name=form.cleaned_data["full_name"],
            )
        except RegisterAccountExistsError:
            return redirect("accounts:login")
        except RegisterVerificationError:
            return redirect("accounts:register")

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        _clear_pending_auth_session(request)
        return redirect("salons_onboarding:create")


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("website:home")

    def get(self, request):
        return redirect("website:home")
