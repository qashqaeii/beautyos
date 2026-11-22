from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OTPChallenge, RegisterPhoneVerification, User
from apps.core.utils.phone import normalize_iran_mobile


class RegisterVerificationError(Exception):
    pass


class RegisterAccountExistsError(RegisterVerificationError):
    """Phone already has an account — user should log in."""


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ""


REGISTER_SESSION_VERIFICATION_KEY = "register_verification_id"

LEGACY_SESSION_KEYS = (
    "register_verified",
    REGISTER_SESSION_VERIFICATION_KEY,
)


def clear_register_session_flags(request) -> None:
    for key in LEGACY_SESSION_KEYS:
        request.session.pop(key, None)
    request.session.modified = True


def invalidate_register_verifications(*, request) -> None:
    session_key = _session_key(request)
    if not session_key:
        return
    RegisterPhoneVerification.objects.filter(
        session_key=session_key,
        consumed_at__isnull=True,
    ).update(expires_at=timezone.now())
    clear_register_session_flags(request)


def grant_register_verification_after_otp(
    *,
    request,
    phone: str,
    challenge: OTPChallenge,
) -> RegisterPhoneVerification:
    phone = normalize_iran_mobile(phone)
    if challenge.purpose != OTPChallenge.Purpose.REGISTER:
        raise RegisterVerificationError("هدف کد تأیید برای ثبت‌نام نیست.")
    if challenge.phone != phone:
        raise RegisterVerificationError("شماره با کد تأیید مطابقت ندارد.")
    if challenge.consumed_at is None:
        raise RegisterVerificationError("کد تأیید هنوز مصرف نشده است.")

    session_key = _session_key(request)
    invalidate_register_verifications(request=request)

    verification = RegisterPhoneVerification.objects.create(
        session_key=session_key,
        phone=phone,
        otp_challenge=challenge,
        expires_at=timezone.now() + timedelta(seconds=settings.BEAUTYOS_OTP_EXPIRY_SECONDS),
    )
    request.session[REGISTER_SESSION_VERIFICATION_KEY] = str(verification.pk)
    request.session.pop("register_verified", None)
    request.session.modified = True
    return verification


def get_valid_register_verification(*, request) -> RegisterPhoneVerification | None:
    if request.session.get("register_verified"):
        return None

    vid = request.session.get(REGISTER_SESSION_VERIFICATION_KEY)
    if not vid:
        return None

    session_key = _session_key(request)
    try:
        verification = RegisterPhoneVerification.objects.select_related("otp_challenge").get(pk=vid)
    except (RegisterPhoneVerification.DoesNotExist, ValueError, TypeError):
        return None

    phone = verification.phone
    try:
        phone = normalize_iran_mobile(phone)
    except ValueError:
        return None

    if verification.consumed_at is not None:
        return None
    if verification.is_expired:
        return None
    if verification.session_key != session_key:
        return None
    if verification.phone != phone:
        return None
    challenge = verification.otp_challenge
    if challenge.consumed_at is None:
        return None
    if challenge.phone != phone:
        return None
    if challenge.purpose != OTPChallenge.Purpose.REGISTER:
        return None
    return verification


@transaction.atomic
def complete_register_profile(
    *,
    request,
    verification: RegisterPhoneVerification,
    full_name: str,
) -> User:
    session_key = _session_key(request)
    phone = normalize_iran_mobile(verification.phone)

    locked = (
        RegisterPhoneVerification.objects.select_for_update()
        .select_related("otp_challenge")
        .filter(pk=verification.pk)
        .first()
    )
    if locked is None:
        raise RegisterVerificationError("تأیید ثبت‌نام معتبر نیست.")
    if locked.consumed_at is not None:
        raise RegisterVerificationError("این تأیید قبلاً استفاده شده است.")
    if locked.is_expired:
        raise RegisterVerificationError("تأیید ثبت‌نام منقضی شده است.")
    if locked.session_key != session_key:
        raise RegisterVerificationError("نشست ثبت‌نام معتبر نیست.")
    if locked.phone != phone:
        raise RegisterVerificationError("شماره با تأیید ثبت‌نام مطابقت ندارد.")

    challenge = locked.otp_challenge
    if challenge.consumed_at is None:
        raise RegisterVerificationError("کد تأیید هنوز مصرف نشده است.")
    if challenge.phone != phone or challenge.purpose != OTPChallenge.Purpose.REGISTER:
        raise RegisterVerificationError("کد تأیید با ثبت‌نام هم‌خوان نیست.")

    if User.objects.filter(phone=phone).exists():
        locked.consumed_at = timezone.now()
        locked.save(update_fields=["consumed_at", "updated_at"])
        raise RegisterAccountExistsError("این شماره قبلاً ثبت شده است. از ورود استفاده کنید.")

    user = User.objects.create(phone=phone, full_name=full_name)
    # Create a private workspace; real salon details are collected after login.
    from apps.salons import onboarding_wizard as ow
    from apps.salons.models import Salon

    salon = ow.create_salon_for_owner(
        user, name="سالن زیبایی من", slug=f"salon-{uuid4().hex[:12]}",
        public_phone="", city="", address="", tagline="", description="",
        business_type=Salon.BusinessType.BEAUTY_WOMEN,
    )
    salon.is_accepting_bookings = False
    salon.save(update_fields=["is_accepting_bookings", "updated_at"])
    locked.consumed_at = timezone.now()
    locked.save(update_fields=["consumed_at", "updated_at"])
    return user
