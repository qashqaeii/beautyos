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


class KavenegarOTPProvider(SMSProvider):
    """Production OTP sender. Never prints codes or uses the marketing outbox."""

    def send_otp(self, phone: str, code: str, purpose: str) -> None:
        import json
        from urllib.error import HTTPError, URLError
        from urllib.parse import quote, urlencode
        from urllib.request import Request, urlopen

        api_key = getattr(settings, "BEAUTYOS_KAVENEGAR_API_KEY", "")
        sender = getattr(settings, "BEAUTYOS_KAVENEGAR_SENDER", "")
        if not api_key or not sender:
            raise RuntimeError("OTP provider credentials are missing.")
        destination = "0" + phone[3:] if phone.startswith("+98") else phone
        message = f"کد تأیید BeautyOS: {code}\nاین کد را در اختیار دیگران قرار ندهید."
        url = "https://api.kavenegar.com/v1/" + quote(api_key, safe="") + "/sms/send.json"
        req = Request(url, data=urlencode({
            "receptor": destination, "sender": sender, "message": message,
        }).encode("utf-8"), headers={"Accept": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=8) as response:
                payload = json.loads(response.read(65536))
            if int(payload["return"]["status"]) != 200:
                raise RuntimeError("OTP service rejected the message.")
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            # Do not include the exception text, it may contain the secret URL.
            raise RuntimeError("OTP could not be delivered.") from None
