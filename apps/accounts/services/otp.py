import hashlib
import hmac
import logging
from ipaddress import ip_address
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import connection, transaction
from django.db.models import F
from django.utils import timezone

from apps.accounts.models import OTPChallenge
from apps.accounts.sms import get_sms_provider
from apps.core.utils.phone import normalize_iran_mobile


def _hash_code(code: str, phone: str) -> str:
    key = settings.SECRET_KEY.encode()
    msg = f"{phone}:{code}".encode()
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class OTPRateLimited(Exception):
    pass


class OTPInvalid(Exception):
    pass


class OTPDeliveryError(Exception):
    pass


def _lock_rate_key(key):
    if connection.vendor == "postgresql":
        digest = hashlib.sha256(key.encode()).digest()[:8]
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [int.from_bytes(digest, "big", signed=True)])


@dataclass
class IssuedOTP:
    challenge: "OTPChallenge"
    dev_code: str | None = None


@transaction.atomic
def issue_otp(*, phone: str, purpose: str, request_ip=None, user_agent: str = "") -> IssuedOTP:
    phone = normalize_iran_mobile(phone)
    try:
        request_ip = str(ip_address(request_ip)) if request_ip else None
    except ValueError:
        request_ip = None
    # Serialize even the first request, when there is no OTP row to lock.
    keys = ["otp:phone:" + phone]
    if request_ip:
        keys.append("otp:ip:" + request_ip)
    for key in sorted(keys):
        _lock_rate_key(key)
    window_start = timezone.now() - timedelta(minutes=10)
    all_recent = OTPChallenge.objects.filter(created_at__gte=window_start)
    if all_recent.filter(phone=phone).count() >= 12 or (
        request_ip and all_recent.filter(request_ip=request_ip).count() >= 30
    ):
        raise OTPRateLimited("تعداد درخواست‌ها بیش از حد مجاز است. لطفاً بعداً تلاش کنید.")
    recent = OTPChallenge.objects.filter(
        phone=phone,
        purpose=purpose,
        created_at__gte=window_start,
    ).count()
    if recent >= 5:
        raise OTPRateLimited("تعداد درخواست‌ها بیش از حد مجاز است. لطفاً بعداً تلاش کنید.")

    active = (
        OTPChallenge.objects.select_for_update()
        .filter(
            phone=phone,
            purpose=purpose,
            consumed_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        .order_by("-created_at")
    )
    carried_attempts = active.values_list("attempts", flat=True).first() or 0
    if carried_attempts >= settings.BEAUTYOS_OTP_MAX_ATTEMPTS:
        raise OTPInvalid("تعداد تلاش‌ها بیش از حد مجاز است.")

    active.update(expires_at=timezone.now())

    code = _generate_code()
    challenge = OTPChallenge.objects.create(
        phone=phone,
        purpose=purpose,
        code_hash=_hash_code(code, phone),
        expires_at=timezone.now() + timedelta(seconds=settings.BEAUTYOS_OTP_EXPIRY_SECONDS),
        request_ip=request_ip,
        user_agent=(user_agent or "")[:255],
        attempts=carried_attempts,
    )
    try:
        provider = get_sms_provider()
        provider.send_otp(phone, code, purpose)
    except Exception:
        logging.getLogger(__name__).warning("OTP delivery failed")
        raise OTPDeliveryError("ارسال پیامک انجام نشد. لطفاً دوباره تلاش کنید.") from None
    dev_code = code if settings.DEBUG else None
    return IssuedOTP(challenge=challenge, dev_code=dev_code)


def verify_otp(*, phone: str, purpose: str, code: str) -> OTPChallenge:
    """Verify OTP. Failed attempts are persisted even when OTPInvalid is raised."""
    phone = normalize_iran_mobile(phone)
    invalid_message = None
    success_challenge_id = None

    with transaction.atomic():
        challenge = (
            OTPChallenge.objects.select_for_update()
            .filter(
                phone=phone,
                purpose=purpose,
                consumed_at__isnull=True,
            )
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            invalid_message = "کد تأیید یافت نشد."
        elif challenge.is_expired:
            invalid_message = "کد تأیید منقضی شده است."
        elif challenge.attempts >= settings.BEAUTYOS_OTP_MAX_ATTEMPTS:
            invalid_message = "تعداد تلاش‌ها بیش از حد مجاز است."
        else:
            expected = challenge.code_hash
            supplied = _hash_code(code.strip(), phone)
            if not hmac.compare_digest(expected, supplied):
                OTPChallenge.objects.filter(pk=challenge.pk).update(
                    attempts=F("attempts") + 1,
                    updated_at=timezone.now(),
                )
                challenge.refresh_from_db(fields=["attempts", "updated_at"])
                if challenge.attempts >= settings.BEAUTYOS_OTP_MAX_ATTEMPTS:
                    invalid_message = "تعداد تلاش‌ها بیش از حد مجاز است."
                else:
                    invalid_message = "کد تأیید نادرست است."
            else:
                if challenge.attempts >= settings.BEAUTYOS_OTP_MAX_ATTEMPTS:
                    invalid_message = "تعداد تلاش‌ها بیش از حد مجاز است."
                else:
                    challenge.consumed_at = timezone.now()
                    challenge.save(update_fields=["consumed_at", "updated_at"])
                    success_challenge_id = challenge.pk

    if invalid_message:
        raise OTPInvalid(invalid_message)

    return OTPChallenge.objects.get(pk=success_challenge_id)