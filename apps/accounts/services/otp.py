import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
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


@dataclass
class IssuedOTP:
    challenge: "OTPChallenge"
    dev_code: str | None = None


@transaction.atomic
def issue_otp(*, phone: str, purpose: str, request_ip=None, user_agent: str = "") -> IssuedOTP:
    phone = normalize_iran_mobile(phone)
    window_start = timezone.now() - timedelta(minutes=10)
    recent = OTPChallenge.objects.filter(
        phone=phone,
        purpose=purpose,
        created_at__gte=window_start,
        consumed_at__isnull=True,
    ).count()
    if recent >= 5:
        raise OTPRateLimited("تعداد درخواست‌ها بیش از حد مجاز است. لطفاً بعداً تلاش کنید.")

    code = _generate_code()
    challenge = OTPChallenge.objects.create(
        phone=phone,
        purpose=purpose,
        code_hash=_hash_code(code, phone),
        expires_at=timezone.now() + timedelta(seconds=settings.BEAUTYOS_OTP_EXPIRY_SECONDS),
        request_ip=request_ip,
        user_agent=(user_agent or "")[:255],
    )
    provider = get_sms_provider()
    provider.send_otp(phone, code, purpose)
    dev_code = code if settings.DEBUG else None
    return IssuedOTP(challenge=challenge, dev_code=dev_code)


@transaction.atomic
def verify_otp(*, phone: str, purpose: str, code: str) -> OTPChallenge:
    phone = normalize_iran_mobile(phone)
    challenge = (
        OTPChallenge.objects.filter(
            phone=phone,
            purpose=purpose,
            consumed_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if challenge is None:
        raise OTPInvalid("کد تأیید یافت نشد.")
    if challenge.is_expired:
        raise OTPInvalid("کد تأیید منقضی شده است.")
    if challenge.attempts >= settings.BEAUTYOS_OTP_MAX_ATTEMPTS:
        raise OTPInvalid("تعداد تلاش‌ها بیش از حد مجاز است.")

    expected = challenge.code_hash
    supplied = _hash_code(code.strip(), phone)
    if not hmac.compare_digest(expected, supplied):
        challenge.attempts += 1
        challenge.save(update_fields=["attempts", "updated_at"])
        raise OTPInvalid("کد تأیید نادرست است.")

    challenge.consumed_at = timezone.now()
    challenge.save(update_fields=["consumed_at", "updated_at"])
    return challenge
