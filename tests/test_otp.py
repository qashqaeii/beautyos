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
def test_otp_invalid_code():
    phone = "+989122222222"
    issue_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN)
    with pytest.raises(OTPInvalid):
        verify_otp(phone=phone, purpose=OTPChallenge.Purpose.LOGIN, code="000000")
