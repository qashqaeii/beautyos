import importlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class SMSProvider:
    def send_otp(self, phone: str, code: str, purpose: str) -> None:
        raise NotImplementedError


class DevSMSProvider(SMSProvider):
    """Development provider — logs OTP instead of sending SMS."""

    def send_otp(self, phone: str, code: str, purpose: str) -> None:
        if not settings.DEBUG:
            raise RuntimeError("DevSMSProvider is disabled outside development.")
        logger.info(
            "[BeautyOS DevSMS] purpose=%s phone=%s code=%s",
            purpose,
            phone,
            code,
        )
        print(f"[BeautyOS DevSMS] {purpose} → {phone}: {code}")


def get_sms_provider() -> SMSProvider:
    path = settings.BEAUTYOS_SMS_PROVIDER
    module_path, class_name = path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()
