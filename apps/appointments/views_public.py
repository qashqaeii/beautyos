from datetime import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import OTPVerifyForm, PhoneForm
from apps.accounts.models import OTPChallenge
from apps.accounts.services.otp import OTPInvalid, issue_otp, verify_otp
from apps.appointments.models import Appointment
from apps.appointments.services.scheduling import SchedulingError, create_appointment, iter_day_slots
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
    request.session["booking"] = {"salon_id": str(salon.id), "service_id": service.pk}
    return render(request, "public/booking/step_staff.html", _booking_context(salon, service=service, staff_list=staff))


def booking_datetime(request, slug):
    salon = _salon(slug)
    booking = request.session.get("booking") or {}
    service = get_object_or_404(Service.scoped(salon), pk=booking.get("service_id"))
    staff = get_object_or_404(StaffProfile.scoped(salon), pk=request.GET.get("staff") or booking.get("staff_id"))
    booking["staff_id"] = staff.pk
    request.session["booking"] = booking

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
    if not booking.get("start_iso"):
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))
    if request.method == "POST":
        name = request.POST.get("full_name", "").strip()
        phone = request.POST.get("phone", "").strip()
        try:
            phone = normalize_iran_mobile(phone)
        except ValueError as exc:
            messages.error(request, str(exc))
            return render(request, "public/booking/step_contact.html", _booking_context(salon))
        request.session["booking"]["name"] = name
        request.session["booking"]["phone"] = phone
        try:
            issue_otp(phone=phone, purpose=OTPChallenge.Purpose.BOOKING_VERIFY, request_ip=request.META.get("REMOTE_ADDR"))
        except Exception:
            messages.error(request, "خطا در ارسال کد. بعداً تلاش کنید.")
            return render(request, "public/booking/step_contact.html", _booking_context(salon))
        return redirect(reverse("salons_public:booking_verify", kwargs={"slug": slug}))
    return render(request, "public/booking/step_contact.html", _booking_context(salon))


def booking_pick_slot(request, slug):
    if request.method == "POST":
        request.session.setdefault("booking", {})
        request.session["booking"]["start_iso"] = request.POST.get("start_iso")
        request.session.modified = True
        return redirect(reverse("salons_public:booking_contact", kwargs={"slug": slug}))
    return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))


def booking_verify(request, slug):
    salon = _salon(slug)
    booking = request.session.get("booking") or {}
    phone = booking.get("phone")
    if not phone:
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))

    if request.method == "POST":
        form = OTPVerifyForm(request.POST)
        if form.is_valid():
            try:
                verify_otp(phone=phone, purpose=OTPChallenge.Purpose.BOOKING_VERIFY, code=form.cleaned_data["code"])
            except OTPInvalid as exc:
                form.add_error("code", str(exc))
                return render(request, "public/booking/step_verify.html", _booking_context(salon, form=form))
            return redirect(reverse("salons_public:booking_confirm", kwargs={"slug": slug}))
    else:
        form = OTPVerifyForm()
    return render(request, "public/booking/step_verify.html", _booking_context(salon, form=form))


def booking_confirm(request, slug):
    salon = _salon(slug)
    booking = request.session.get("booking") or {}
    required = ("service_id", "staff_id", "start_iso", "phone", "name")
    if not all(booking.get(k) for k in required):
        return redirect(reverse("salons_public:booking_start", kwargs={"slug": slug}))

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
            appt = create_appointment(
                salon=salon,
                customer=customer,
                staff=staff,
                service=service,
                start=start,
                source=Appointment.Source.PUBLIC,
                status=Appointment.Status.PENDING,
            )
            request.session.pop("booking", None)
            return render(request, "public/booking/success.html", _booking_context(salon, appointment=appt))
        except SchedulingError as exc:
            messages.error(request, exc.messages[0] if exc.messages else str(exc))
    return render(
        request,
        "public/booking/step_confirm.html",
        _booking_context(salon, service=service, staff=staff, start=start, customer=customer),
    )
