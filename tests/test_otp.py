import pytest

from apps.accounts.models import OTPChallenge
from apps.accounts.services import otp as otp_service
from apps.accounts.services.otp import OTPInvalid, issue_otp, verify_otp
from apps.accounts.sms import DevSMSProvider


@pytest.mark.django_db
def test_otp_issue_and_verify(monkeypatch):
    captured = {}

    class CapturingProvider(DevSMSProvider):
        def send_otp(self, phone, code, purpose):
            captured["code"] = code

    monkeypatch.setattr(otp_service, "get_sms_provider", lambda: CapturingProvider())

    phone = "+989121111111"
    issue_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN)
    verify_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN, code=captured["code"])
    challenge = OTPChallenge.objects.filter(phone=phone).latest("created_at")
    assert challenge.consumed_at is not None


@pytest.mark.django_db
def test_otp_invalid_code(settings, monkeypatch):
    settings.DEBUG = True
    monkeypatch.setattr(otp_service, "_generate_code", lambda: "123456")
    phone = "+989122222222"
    issue_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN)
    with pytest.raises(OTPInvalid):
        verify_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN, code="000000")
    challenge = OTPChallenge.objects.filter(phone=phone).latest("created_at")
    assert challenge.attempts == 1


@pytest.mark.django_db
def test_otp_rate_includes_consumed_challenges(monkeypatch, settings):
    settings.DEBUG = True
    from apps.accounts.services.otp import OTPRateLimited
    monkeypatch.setattr(otp_service, "_generate_code", lambda: "123456")
    phone = "+989123456789"
    for _ in range(5):
        issue_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN)
        verify_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN, code="123456")
    with pytest.raises(OTPRateLimited):
        issue_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN)


@pytest.mark.django_db
def test_otp_provider_failure_rolls_back(monkeypatch):
    from apps.accounts.services.otp import OTPDeliveryError

    class BrokenProvider:
        def send_otp(self, *args):
            raise RuntimeError("provider failure")

    monkeypatch.setattr(otp_service, "get_sms_provider", BrokenProvider)
    with pytest.raises(OTPDeliveryError):
        issue_otp(phone="+989123456789", purpose=OTPChallenge.Purpose.LOGIN)
    assert not OTPChallenge.objects.filter(phone="+989123456789").exists()
