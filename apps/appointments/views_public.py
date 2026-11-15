from datetime import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import OTPVerifyForm
from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import OTPInvalid, OTPRateLimited, issue_otp, verify_otp
from apps.appointments.models import Appointment
from apps.appointments.public_booking import (
    BookingVerificationError,
    finalize_public_booking,
    get_valid_phone_verification,
    grant_phone_verification_after_otp,
    invalidate_phone_verifications,
    merge_booking_session,
)
from apps.appointments.services.scheduling import SchedulingError, iter_day_slots
from apps.core.utils.dates import to_jalali
from apps.core.utils.phone import normalize_iran_mobile
from apps.customers.models import Customer
from apps.salons.models import Salon
from apps.salons.themes import css_variables_inline_public
from apps.services.models import Service
from apps.staff.models import StaffProfile


def _salon(slug):
    return get_object_or_404(Salon, slug=slug, is_active=True, is_accepting_bookings=True)


def _booking_context(salon, **extra):
    return {
        "salon": salon,
        "public_theme_style": css_variables_inline_public(),
        **extra,
    }


def _ensure_booking_salon(request, salon, booking: dict) -> bool:
    if booking.get("salon_id") and booking.get("salon_id") != str(salon.id):
        return False
    return True


def booking_start(request, slug):
    salon = _salon(slug)
    services = Service.scoped(salon).filter(is_active=True, is_public=True, is_deleted=False)
    return render(request, "public/booking/step_service.html", _booking_context(salon, services=services))


def booking_staff(request, slug):
    salon = _salon(slug)
    service_id = request.GET.get("service")
    service = get_object_or_404(Service.scoped(salon), pk=service_id, is_public=True)
    staff = (
        StaffProfile.scoped(salon)
        .filter(is_active=True, is_bookable=True, is_deleted=False, services=service)
        .distinct()
    )
    merge_booking_session(request, salon_id=str(salon.id), service_id=service.pk)
    return render(request, "public/booking/step_staff.html", _booking_context(salon, service=service, staff_list=staff))


def booking_datetime(request, slug):
    salon = _salon(slug)
    booking = request.session.get("booking") or {}
    if not _ensure_booking_salon(request, salon, booking):
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))
    service = get_object_or_404(Service.scoped(salon), pk=booking.get("service_id"))
    staff = get_object_or_404(StaffProfile.scoped(salon), pk=request.GET.get("staff") or booking.get("staff_id"))
    merge_booking_session(request, staff_id=staff.pk)

    day_str = request.GET.get("day")
    if day_str:
        day = datetime.strptime(day_str, "%Y-%m-%d").date()
    else:
        day = timezone.localdate()
    slots = list(iter_day_slots(staff, day, service.duration_minutes))
    return render(
        request,
        "public/booking/step_datetime.html",
        _booking_context(
            salon,
            service=service,
            staff=staff,
            day=day,
            day_jalali=to_jalali(day),
            slots=slots,
        ),
    )


def booking_contact(request, slug):
    salon = _salon(slug)
    booking = request.session.get("booking") or {}
    if not booking.get("start_iso") or not _ensure_booking_salon(request, salon, booking):
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))
    if request.method == "POST":
        name = request.POST.get("full_name", "").strip()
        phone_raw = request.POST.get("phone", "").strip()
        try:
            phone = normalize_iran_mobile(phone_raw)
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(
                request,
                "public/booking/step_contact.html",
                _booking_context(salon, full_name=name, phone=phone_raw),
            )

        prior_phone = booking.get("phone")
        merge_booking_session(request, name=name, phone=phone, salon_id=str(salon.id))
        if prior_phone and prior_phone != phone:
            invalidate_phone_verifications(request=request, salon=salon)

        try:
            issue_otp(
                phone=phone,
                purpose=OTPChallenge.Purpose.BOOKING_VERIFY,
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except OTPRateLimited:
            messages.error(request, "تعداد درخواست‌ها بیش از حد مجاز است. لطفاً بعداً تلاش کنید.")
            return render(
                request,
                "public/booking/step_contact.html",
                _booking_context(salon, full_name=name, phone=phone_raw),
            )
        except OTPInvalid as exc:
            messages.error(request, str(exc))
            return render(
                request,
                "public/booking/step_contact.html",
                _booking_context(salon, full_name=name, phone=phone_raw),
            )
        except Exception:
            messages.error(request, "خطا در ارسال کد. بعداً تلاش کنید.")
            return render(
                request,
                "public/booking/step_contact.html",
                _booking_context(salon, full_name=name, phone=phone_raw),
            )
        return redirect(reverse("salons_public:booking_verify", kwargs={"slug": slug}))
    return render(request, "public/booking/step_contact.html", _booking_context(salon))


def booking_pick_slot(request, slug):
    if request.method == "POST":
        merge_booking_session(request, start_iso=request.POST.get("start_iso"))
        return redirect(reverse("salons_public:booking_contact", kwargs={"slug": slug}))
    return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))


def booking_verify(request, slug):
    salon = _salon(slug)
    booking = request.session.get("booking") or {}
    phone = booking.get("phone")
    if not phone or not _ensure_booking_salon(request, salon, booking):
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))
    if not booking.get("start_iso") or not booking.get("service_id") or not booking.get("staff_id"):
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))

    if request.method == "POST" and request.POST.get("action") == "resend":
        try:
            issue_otp(
                phone=phone,
                purpose=OTPChallenge.Purpose.BOOKING_VERIFY,
                request_ip=request.META.get("REMOTE_ADDR"),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            messages.success(request, "کد جدید ارسال شد.")
        except OTPRateLimited:
            messages.error(request, "تعداد درخواست‌ها بیش از حد مجاز است. لطفاً بعداً تلاش کنید.")
        except OTPInvalid as exc:
            messages.error(request, str(exc))
        except Exception:
            messages.error(request, "خطا در ارسال کد. بعداً تلاش کنید.")
        return render(request, "public/booking/step_verify.html", _booking_context(salon, form=OTPVerifyForm()))

    if request.method == "POST":
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            try:
                challenge = verify_otp(
                    phone=phone,
                    purpose=OTPChallenge.Purpose.BOOKING_VERIFY,
                    code=form.cleaned_data["code"],
                )
            except OTPInvalid as exc:
                form.add_error("code", str(exc))
                return render(request, "public/booking/step_verify.html", _booking_context(salon, form=form))
            grant_phone_verification_after_otp(request=request, salon=salon, phone=phone, challenge=challenge)
            return redirect(reverse("salons_public:booking_confirm", kwargs={"slug": slug}))
    else:
        form = OTPVerifyForm()
    return render(request, "public/booking/step_verify.html", _booking_context(salon, form=form))


def booking_confirm(request, slug):
    salon = _salon(slug)
    booking = request.session.get("booking") or {}
    required = ("service_id", "staff_id", "start_iso", "phone", "name")
    if not all(booking.get(k) for k in required) or not _ensure_booking_salon(request, salon, booking):
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))

    verification = get_valid_phone_verification(request=request, salon=salon, booking=booking)
    if verification is None:
        messages.error(request, "ابتدا شماره موبایل را تأیید کنید.")
        return redirect(reverse("salons_public:booking_verify", kwargs={"slug": slug}))

    service = get_object_or_404(Service.scoped(salon), pk=booking["service_id"])
    staff = get_object_or_404(StaffProfile.scoped(salon), pk=booking["staff_id"])
    start = datetime.fromisoformat(booking["start_iso"])
    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.get_current_timezone())

    customer, _ = Customer.objects.get_or_create(
        salon=salon,
        phone=booking["phone"],
        defaults={"full_name": booking["name"], "is_deleted": False},
    )
    if customer.is_deleted:
        customer.is_deleted = False
        customer.full_name = booking["name"]
        customer.save()
    elif customer.full_name != booking["name"]:
        customer.full_name = booking["name"]
        customer.save(update_fields=["full_name", "updated_at"])

    if request.method == "POST":
        try:
            appt = finalize_public_booking(
                verification=verification,
                request=request,
                salon=salon,
                booking=booking,
                customer=customer,
                staff=staff,
                service=service,
                start=start,
            )
            request.session.pop("booking", None)
            return render(request, "public/booking/success.html", _booking_context(salon, appointment=appt))
        except BookingVerificationError:
            messages.error(request, "تأیید موبایل معتبر نیست. لطفاً دوباره کد را وارد کنید.")
            return redirect(reverse("salons_public:booking_verify", kwargs={"slug": slug}))
        except SchedulingError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return render(
        request,
        "public/booking/step_confirm.html",
        _booking_context(salon, service=service, staff=staff, start=start, customer=customer),
    )