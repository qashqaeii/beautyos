from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.appointments.models import PublicBookingPhoneVerification
from apps.appointments.services.scheduling import create_appointment
from apps.core.utils.phone import normalize_iran_mobile


class BookingVerificationError(Exception):
    pass


def merge_booking_session(request, **updates) -> dict:
    booking = dict(request.session.get("booking") or {})
    booking.update(updates)
    request.session["booking"] = booking
    request.session.modified = True
    return booking


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ""


def invalidate_phone_verifications(*, request, salon) -> None:
    session_key = _session_key(request)
    if not session_key:
        return
    PublicBookingPhoneVerification.objects.filter(
        session_key=session_key,
        salon=salon,
        consumed_at__isnull=True,
    ).update(expires_at=timezone.now())
    booking = dict(request.session.get("booking") or {})
    booking.pop("phone_verification_id", None)
    request.session["booking"] = booking
    request.session.modified = True


def grant_phone_verification_after_otp(*, request, salon, phone: str, challenge: OTPChallenge) -> PublicBookingPhoneVerification:
    phone = normalize_iran_mobile(phone)
    session_key = _session_key(request)
    PublicBookingPhoneVerification.objects.filter(
        session_key=session_key,
        salon=salon,
        consumed_at__isnull=True,
    ).update(expires_at=timezone.now())

    verification = PublicBookingPhoneVerification.objects.create(
        session_key=session_key,
        salon=salon,
        phone=phone,
        otp_challenge=challenge,
        expires_at=timezone.now() + timedelta(seconds=settings.BEAUTYOS_OTP_EXPIRY_SECONDS),
    )
    merge_booking_session(request, phone_verification_id=str(verification.pk), phone=phone, salon_id=str(salon.id))
    return verification


def get_valid_phone_verification(*, request, salon, booking: dict) -> PublicBookingPhoneVerification | None:
    vid = booking.get("phone_verification_id")
    phone = booking.get("phone")
    if not vid or not phone:
        return None
    try:
        phone = normalize_iran_mobile(phone)
    except ValueError:
        return None

    session_key = _session_key(request)
    try:
        verification = PublicBookingPhoneVerification.objects.select_related("otp_challenge").get(pk=vid)
    except (PublicBookingPhoneVerification.DoesNotExist, ValueError):
        return None

    if verification.consumed_at is not None:
        return None
    if verification.is_expired:
        return None
    if verification.salon_id != salon.pk:
        return None
    if verification.phone != phone:
        return None
    if verification.session_key != session_key:
        return None
    if verification.otp_challenge.consumed_at is None:
        return None
    if verification.otp_challenge.phone != phone:
        return None
    if verification.otp_challenge.purpose != OTPChallenge.Purpose.BOOKING_VERIFY:
        return None
    return verification


@transaction.atomic
def finalize_public_booking(
    *,
    verification: PublicBookingPhoneVerification,
    request,
    salon,
    booking: dict,
    customer,
    staff,
    service,
    start,
):
    session_key = _session_key(request)
    phone = normalize_iran_mobile(booking["phone"])

    locked = (
        PublicBookingPhoneVerification.objects.select_for_update()
        .select_related("otp_challenge")
        .filter(pk=verification.pk)
        .first()
    )
    if locked is None:
        raise BookingVerificationError("تأیید موبایل معتبر نیست.")
    if locked.consumed_at is not None:
        raise BookingVerificationError("این تأیید قبلاً استفاده شده است.")
    if locked.is_expired:
        raise BookingVerificationError("تأیید موبایل منقضی شده است.")
    if locked.salon_id != salon.pk:
        raise BookingVerificationError("تأیید متعلق به این سالن نیست.")
    if locked.phone != phone:
        raise BookingVerificationError("شماره موبایل با تأیید ثبت‌شده مطابقت ندارد.")
    if locked.session_key != session_key:
        raise BookingVerificationError("نشست رزرو معتبر نیست.")
    if locked.otp_challenge.consumed_at is None:
        raise BookingVerificationError("کد تأیید هنوز مصرف نشده است.")

    from apps.appointments.models import Appointment

    appt = create_appointment(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start=start,
        source=Appointment.Source.PUBLIC,
        status=Appointment.Status.PENDING,
    )
    locked.consumed_at = timezone.now()
    locked.save(update_fields=["consumed_at", "updated_at"])
    return appt