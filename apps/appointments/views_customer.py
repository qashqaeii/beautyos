"""Women-only salon customer self-service, independent of staff login."""
from datetime import datetime, timedelta

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.forms import OTPVerifyForm, PhoneForm
from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import OTPInvalid, OTPRateLimited, issue_otp, verify_otp
from apps.appointments.customer_portal import (
    ACCESS_SESSION_KEY, PENDING_SESSION_KEY, CustomerActionError,
    cancel_customer_appointment, can_customer_manage_appointment,
    grant_customer_access, remember_pending_verification,
    reschedule_customer_appointment, valid_pending_verification,
    verified_customer_phone,
)
from apps.appointments.models import Appointment
from apps.appointments.services.scheduling import iter_day_slots
from apps.core.utils.dates import to_jalali
from apps.core.utils.phone import display_iran_mobile
from apps.customers.models import Customer
from apps.salons.models import Salon
from apps.salons.themes import css_variables_inline_public


def _salon(slug):
    # Existing appointments stay accessible even when booking is switched off.
    return get_object_or_404(Salon, slug=slug, is_active=True)


def _context(salon, **extra):
    return {
        "salon": salon, "public_theme_style": css_variables_inline_public(),
        "seo_robots": "noindex,nofollow", **extra,
    }


def _portal_url(salon, name, **kwargs):
    return reverse("salons_public:" + name, kwargs={"slug": salon.slug, **kwargs})


def _customer_appointments(salon, phone):
    # Never authorize with tracking code alone: phone must be OTP verified.
    return Appointment.scoped(salon).filter(
        customer__phone=phone, customer__is_deleted=False,
    ).select_related("service", "staff", "customer")


def _require_customer(request, salon):
    return verified_customer_phone(request, salon=salon)


@never_cache
@require_http_methods(["GET", "POST"])
def customer_login(request, slug):
    salon = _salon(slug)
    if _require_customer(request, salon):
        return redirect(_portal_url(salon, "customer_home"))
    form = PhoneForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        phone = form.cleaned_data["phone"]
        try:
            issued = issue_otp(
                phone=phone, purpose=OTPChallenge.Purpose.CUSTOMER_PORTAL,
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except (OTPInvalid, OTPRateLimited) as exc:
            form.add_error(None, str(exc))
        except Exception:
            form.add_error(None, "ارسال کد انجام نشد. لطفاً دوباره تلاش کنید.")
        else:
            remember_pending_verification(
                request, salon=salon, phone=phone, challenge=issued.challenge,
            )
            return redirect(_portal_url(salon, "customer_verify"))
    return render(request, "public/customer/login.html", _context(salon, form=form))


@never_cache
@require_http_methods(["GET", "POST"])
def customer_verify(request, slug):
    salon = _salon(slug)
    pending = valid_pending_verification(request, salon=salon)
    if pending is None:
        return redirect(_portal_url(salon, "customer_login"))
    form = OTPVerifyForm(request.POST or None)
    if request.method == "POST" and request.POST.get("action") == "resend":
        try:
            issued = issue_otp(
                phone=pending["phone"], purpose=OTPChallenge.Purpose.CUSTOMER_PORTAL,
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except (OTPInvalid, OTPRateLimited) as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "ارسال کد انجام نشد. لطفاً دوباره تلاش کنید.")
        else:
            remember_pending_verification(
                request, salon=salon, phone=pending["phone"], challenge=issued.challenge,
            )
            messages.success(request, "کد جدید ارسال شد.")
        return redirect(_portal_url(salon, "customer_verify"))
    if request.method == "POST" and form.is_valid():
        # Avoid accepting an OTP issued for another session or salon.
        challenge = OTPChallenge.objects.filter(
            pk=pending["challenge_id"], phone=pending["phone"],
            purpose=OTPChallenge.Purpose.CUSTOMER_PORTAL,
            consumed_at__isnull=True, expires_at__gt=timezone.now(),
        ).first()
        if challenge is None:
            form.add_error("code", "کد منقضی شده است؛ دوباره درخواست دهید.")
        else:
            try:
                verified = verify_otp(
                    phone=pending["phone"],
                    purpose=OTPChallenge.Purpose.CUSTOMER_PORTAL,
                    code=form.cleaned_data["code"],
                )
            except OTPInvalid as exc:
                form.add_error("code", str(exc))
            else:
                if verified.pk != challenge.pk:
                    form.add_error("code", "کد تأیید متعلق به این نشست نیست.")
                else:
                    grant_customer_access(request, salon=salon, phone=pending["phone"])
                    return redirect(_portal_url(salon, "customer_home"))
    return render(request, "public/customer/verify.html", _context(
        salon, form=form, phone_hint=display_iran_mobile(pending["phone"]),
    ))


@never_cache
@require_http_methods(["GET"])
def customer_home(request, slug):
    salon = _salon(slug)
    phone = _require_customer(request, salon)
    if not phone:
        return redirect(_portal_url(salon, "customer_login"))
    customer = Customer.scoped(salon).filter(phone=phone, is_deleted=False).first()
    future, history = [], []
    if customer:
        appointments = list(_customer_appointments(salon, phone).order_by("-start_at")[:250])
        now = timezone.now()
        future = sorted((
            a for a in appointments
            if a.start_at >= now and a.status in (Appointment.Status.PENDING, Appointment.Status.CONFIRMED)
        ), key=lambda a: a.start_at)
        history = [
            a for a in appointments
            if a.start_at < now or a.status not in (Appointment.Status.PENDING, Appointment.Status.CONFIRMED)
        ]
    return render(request, "public/customer/home.html", _context(
        salon, customer=customer, phone=display_iran_mobile(phone),
        upcoming=future[:12], history=history[:30],
    ))


@never_cache
@require_http_methods(["GET"])
def customer_appointment(request, slug, appointment_id):
    salon = _salon(slug)
    phone = _require_customer(request, salon)
    if not phone:
        return redirect(_portal_url(salon, "customer_login"))
    appointment = get_object_or_404(_customer_appointments(salon, phone), pk=appointment_id)
    allowed, reason = can_customer_manage_appointment(salon, appointment)
    return render(request, "public/customer/appointment.html", _context(
        salon, appointment=appointment, can_manage=allowed, restriction=reason,
    ))


@never_cache
@require_POST
def customer_cancel(request, slug, appointment_id):
    salon = _salon(slug)
    phone = _require_customer(request, salon)
    if not phone:
        return HttpResponseForbidden("برای این اقدام ابتدا شماره موبایل را تأیید کنید.")
    # A request cannot mutate a different tenant's appointment.
    get_object_or_404(_customer_appointments(salon, phone), pk=appointment_id)
    try:
        cancel_customer_appointment(salon=salon, appointment_id=appointment_id, phone=phone)
    except CustomerActionError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "نوبت شما لغو شد.")
    return redirect(_portal_url(salon, "customer_appointment", appointment_id=appointment_id))


@never_cache
@require_http_methods(["GET", "POST"])
def customer_reschedule(request, slug, appointment_id):
    salon = _salon(slug)
    phone = _require_customer(request, salon)
    if not phone:
        if request.method == "POST":
            return HttpResponseForbidden("برای این اقدام ابتدا شماره موبایل را تأیید کنید.")
        return redirect(_portal_url(salon, "customer_login"))
    appointment = get_object_or_404(_customer_appointments(salon, phone), pk=appointment_id)
    allowed, reason = can_customer_manage_appointment(salon, appointment)
    if not salon.is_accepting_bookings:
        allowed, reason = False, "رزرو آنلاین سالن غیرفعال است."
    if request.method == "POST":
        if not allowed:
            messages.error(request, reason)
            return redirect(_portal_url(salon, "customer_appointment", appointment_id=appointment_id))
        from apps.appointments.views_public import _parse_slot
        start = _parse_slot(request.POST.get("start_iso"))
        try:
            reschedule_customer_appointment(
                salon=salon, appointment_id=appointment_id, phone=phone, start=start,
            )
        except CustomerActionError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, "زمان نوبت تغییر کرد و در انتظار تأیید سالن قرار گرفت.")
            return redirect(_portal_url(salon, "customer_appointment", appointment_id=appointment_id))
        return redirect(_portal_url(salon, "customer_reschedule", appointment_id=appointment_id))
    today = timezone.localdate()
    try:
        day = datetime.strptime(request.GET.get("day", ""), "%Y-%m-%d").date()
    except ValueError:
        day = timezone.localtime(appointment.start_at).date() if allowed else today
    if not today <= day <= today + timedelta(days=365):
        day = today
    earliest = timezone.now() + timedelta(minutes=getattr(salon.settings, "booking_lead_time_minutes", 60))
    slots = []
    if allowed:
        slots = [
            slot for slot in iter_day_slots(
                appointment.staff, day, appointment.service.duration_minutes,
            ) if slot >= earliest and slot != appointment.start_at
        ]
    last_day = today + timedelta(days=365)
    day_choices = [
        {"value": day + timedelta(days=offset), "label": to_jalali(day + timedelta(days=offset)),
         "selected": offset == 0}
        for offset in range(7) if day + timedelta(days=offset) <= last_day
    ]
    return render(request, "public/customer/reschedule.html", _context(
        salon, appointment=appointment, can_manage=allowed, restriction=reason,
        day=day, day_jalali=to_jalali(day), slots=slots, day_choices=day_choices,
        previous_week=max(today, day - timedelta(days=7)) if day > today else None,
        next_week=day + timedelta(days=7) if day + timedelta(days=7) <= last_day else None,
    ))


@never_cache
@require_POST
def customer_logout(request, slug):
    salon = _salon(slug)
    request.session.pop(ACCESS_SESSION_KEY, None)
    request.session.pop(PENDING_SESSION_KEY, None)
    request.session.cycle_key()
    return redirect(_portal_url(salon, "customer_login"))
