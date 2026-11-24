"""OTP-verified, salon-scoped customer self service.

This is deliberately NOT an authenticated salon staff account.
Access only derives from a verified phone number in the current Django session.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import cancel_appointment
from apps.appointments.services.scheduling import (
    SchedulingError, has_overlap, iter_day_slots, staff_is_available,
)
from apps.core.utils.phone import normalize_iran_mobile
from apps.customers.models import CustomerActivity
from apps.customers.services import log_activity
from apps.finance.models import Payment
from apps.staff.models import StaffProfile

ACCESS_SESSION_KEY = "customer_portal_access"
PENDING_SESSION_KEY = "customer_portal_pending"
ACCESS_TTL_SECONDS = 12 * 60 * 60
PENDING_TTL_SECONDS = 15 * 60


class CustomerActionError(Exception):
    """Human-readable failure for an authorized customer action."""


def grant_customer_access(request, *, salon, phone):
    """Called only after successful OTP verification or a finalized verified booking."""
    normalized = normalize_iran_mobile(phone)
    request.session.cycle_key()  # Prevent reuse of a pre-verification session id.
    request.session[ACCESS_SESSION_KEY] = {
        "salon_id": str(salon.pk),
        "phone": normalized,
        "verified_at": int(timezone.now().timestamp()),
    }
    request.session.pop(PENDING_SESSION_KEY, None)
    request.session.modified = True


def verified_customer_phone(request, *, salon):
    data = request.session.get(ACCESS_SESSION_KEY) or {}
    if not isinstance(data, dict) or data.get("salon_id") != str(salon.pk):
        return None
    try:
        age = timezone.now().timestamp() - int(data.get("verified_at", 0))
        if not (0 <= age <= ACCESS_TTL_SECONDS):
            return None
        return normalize_iran_mobile(data.get("phone", ""))
    except (TypeError, ValueError):
        return None


def valid_pending_verification(request, *, salon):
    data = request.session.get(PENDING_SESSION_KEY) or {}
    if not isinstance(data, dict) or data.get("salon_id") != str(salon.pk):
        return None
    try:
        age = timezone.now().timestamp() - int(data.get("issued_at", 0))
        if not (0 <= age <= PENDING_TTL_SECONDS):
            return None
        if not int(data.get("challenge_id", 0)):
            return None
        normalize_iran_mobile(data.get("phone", ""))
    except (TypeError, ValueError):
        return None
    return data


def remember_pending_verification(request, *, salon, phone, challenge):
    request.session[PENDING_SESSION_KEY] = {
        "salon_id": str(salon.pk),
        "phone": normalize_iran_mobile(phone),
        "challenge_id": challenge.pk,
        "issued_at": int(timezone.now().timestamp()),
    }
    request.session.modified = True


def can_customer_manage_appointment(salon, appointment):
    """Only future, unpaid public bookings may be changed by their customer."""
    if appointment.source != Appointment.Source.PUBLIC:
        return False, "برای تغییر نوبت ثبت‌شده توسط سالن، با پذیرش تماس بگیرید."
    if appointment.status not in (Appointment.Status.PENDING, Appointment.Status.CONFIRMED):
        return False, "این نوبت در وضعیت قابل تغییر نیست."
    notice_hours = getattr(salon.settings, "cancellation_notice_hours", 2)
    if appointment.start_at < timezone.now() + timedelta(hours=notice_hours):
        return False, f"تغییر یا لغو باید حداقل {notice_hours} ساعت پیش از نوبت انجام شود."
    if Payment.scoped(salon).filter(
        appointment=appointment, paid_amount_toman__gt=0,
    ).exclude(status=Payment.Status.REFUNDED).exists():
        return False, "برای تغییر نوبتی که پرداخت یا بیعانه دارد، با سالن تماس بگیرید."
    return True, ""


@transaction.atomic
def cancel_customer_appointment(*, salon, appointment_id, phone):
    phone = normalize_iran_mobile(phone)
    appointment = (
        Appointment.scoped(salon).select_for_update()
        .select_related("customer").filter(
            pk=appointment_id, customer__phone=phone, customer__is_deleted=False,
        ).first()
    )
    if appointment is None:
        raise CustomerActionError("نوبت موردنظر یافت نشد.")
    allowed, reason = can_customer_manage_appointment(salon, appointment)
    if not allowed:
        raise CustomerActionError(reason)
    canceled = cancel_appointment(salon=salon, appointment_id=appointment.pk)
    log_activity(
        salon=salon, customer=appointment.customer,
        activity_type=CustomerActivity.ActivityType.APPOINTMENT,
        title="لغو نوبت توسط مشتری", description=f"کد پیگیری: {appointment.tracking_code}",
        entity_type="appointment", entity_id=str(appointment.pk),
    )
    return canceled


@transaction.atomic
def reschedule_customer_appointment(*, salon, appointment_id, phone, start):
    """Lock staff before appointment, matching create_appointment's lock order."""
    phone = normalize_iran_mobile(phone)
    candidate = (
        Appointment.scoped(salon).select_related("customer", "staff", "service")
        .filter(pk=appointment_id, customer__phone=phone, customer__is_deleted=False)
        .first()
    )
    if candidate is None:
        raise CustomerActionError("نوبت موردنظر یافت نشد.")
    staff = StaffProfile.scoped(salon).select_for_update().filter(pk=candidate.staff_id).first()
    appointment = (
        Appointment.scoped(salon).select_for_update().select_related("customer", "service")
        .filter(pk=appointment_id, customer__phone=phone, customer__is_deleted=False).first()
    )
    if appointment is None or staff is None:
        raise CustomerActionError("اطلاعات این نوبت معتبر نیست.")
    allowed, reason = can_customer_manage_appointment(salon, appointment)
    if not allowed:
        raise CustomerActionError(reason)
    if not salon.is_accepting_bookings:
        raise CustomerActionError("رزرو آنلاین این سالن در حال حاضر غیرفعال است.")
    service = appointment.service
    if not service.is_active or service.is_deleted or not service.is_public:
        raise CustomerActionError("این خدمت دیگر برای رزرو آنلاین فعال نیست.")
    if not staff.services.filter(pk=service.pk).exists():
        raise CustomerActionError("این متخصص دیگر خدمت انتخاب‌شده را ارائه نمی‌دهد.")
    lead = getattr(salon.settings, "booking_lead_time_minutes", 60)
    if not start or start < timezone.now() + timedelta(minutes=lead):
        raise CustomerActionError("زمان انتخاب‌شده خارج از مهلت مجاز رزرو است.")
    local = timezone.localtime(start)
    if local.date() > timezone.localdate() + timedelta(days=365):
        raise CustomerActionError("رزرو برای این تاریخ هنوز فعال نیست.")
    if start == appointment.start_at:
        raise CustomerActionError("زمان انتخاب‌شده با نوبت فعلی یکسان است.")
    end = start + timedelta(minutes=service.duration_minutes)
    try:
        staff_is_available(staff, start, end)
        if has_overlap(salon, staff.pk, start, end, exclude_id=appointment.pk):
            raise CustomerActionError("این ساعت دیگر آزاد نیست.")
    except SchedulingError as exc:
        raise CustomerActionError(exc.messages[0] if exc.messages else str(exc)) from exc
    # Reject arbitrary times outside the grid even when valid working hours.
    # Current appointment may intersect its old slot but cannot intersect new slot.
    if start not in set(iter_day_slots(staff, local.date(), service.duration_minutes)):
        raise CustomerActionError("این زمان دیگر در فهرست زمان‌های آزاد نیست.")
    previous = appointment.start_at
    appointment.start_at = start
    appointment.end_at = end
    appointment.status = Appointment.Status.PENDING
    appointment.save(update_fields=["start_at", "end_at", "status", "updated_at"])
    log_activity(
        salon=salon, customer=appointment.customer,
        activity_type=CustomerActivity.ActivityType.APPOINTMENT,
        title="تغییر زمان نوبت توسط مشتری",
        description=f"از {timezone.localtime(previous):%Y-%m-%d %H:%M} به {local:%Y-%m-%d %H:%M}",
        entity_type="appointment", entity_id=str(appointment.pk),
    )
    return appointment
