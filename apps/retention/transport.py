"""Kavenegar customer SMS gateway, isolated from the OTP transport.

One stable numeric localid per durable message. Ambiguous HTTP responses are
never automatically retried; statuslocalmessageid is used for reconciliation.
"""
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from django.conf import settings


class TransportUnavailable(RuntimeError):
    pass


class ProviderRejected(RuntimeError):
    """A definitive API error response, not a network timeout."""


class ProviderUnknown(RuntimeError):
    """The provider may have accepted the message; do not retry automatically."""


def ready():
    return bool(
        getattr(settings, "BEAUTYOS_AUTOMATION_SEND_ENABLED", False)
        and getattr(settings, "BEAUTYOS_KAVENEGAR_API_KEY", "")
        and getattr(settings, "BEAUTYOS_KAVENEGAR_SENDER", "")
    )


def recipient_number(phone):
    if phone.startswith("+98"):
        return "0" + phone[3:]
    return phone


class KavenegarTransport:
    def __init__(self):
        self.key = getattr(settings, "BEAUTYOS_KAVENEGAR_API_KEY", "")
        self.sender = getattr(settings, "BEAUTYOS_KAVENEGAR_SENDER", "")
        if not ready():
            raise TransportUnavailable("درگاه ارسال اتوماسیون غیرفعال است.")

    def _request(self, endpoint, params):
        # Do not log exception URLs: the API key is in the vendor URL.
        url = "https://api.kavenegar.com/v1/" + quote(self.key, safe="") + "/sms/" + endpoint + ".json"
        req = Request(url, data=urlencode(params).encode("utf-8"), headers={"Accept": "application/json"}, method="POST")
        try:
            with urlopen(req, timeout=8) as response:
                raw = response.read(1048576)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise ProviderUnknown("پاسخ قطعی از درگاه دریافت نشد.") from None
        try:
            payload = json.loads(raw)
            result = payload["return"]
            code = int(result["status"])
        except (TypeError, ValueError, KeyError, IndexError):
            raise ProviderUnknown("پاسخ درگاه قابل تفسیر نیست.") from None
        if code != 200:
            raise ProviderRejected(f"درگاه درخواست را رد کرد (کد {code}).")
        return payload.get("entries", [])

    def send(self, row, phone):
        entries = self._request("send", {
            "receptor": recipient_number(phone),
            "sender": self.sender,
            "message": row.text,
            "localid": row.pk,
        })
        entry = entries[0] if isinstance(entries, list) and entries else {}
        message_id = str(entry.get("messageid") or "")
        if not message_id or not message_id.isdecimal():
            raise ProviderUnknown("شناسه معتبر ارسال از درگاه دریافت نشد.")
        return message_id

    def lookup(self, row):
        params = {"messageid": row.provider_message_id} if row.provider_message_id else {"localid": row.pk}
        endpoint = "status" if row.provider_message_id else "statuslocalmessageid"
        entries = self._request(endpoint, params)
        entry = entries[0] if isinstance(entries, list) and entries else {}
        if not isinstance(entry, dict):
            return None, ""
        message_id = str(entry.get("messageid") or row.provider_message_id or "")
        try:
            vendor_status = int(entry.get("status"))
        except (TypeError, ValueError):
            return None, message_id
        if vendor_status == 10:
            return "delivered", message_id
        if vendor_status in {6, 8}:
            return "failed", message_id
        if vendor_status in {1, 2, 4, 5}:
            return "accepted", message_id
        # Unknown/invalid status is not proof of non-delivery.
        return None, message_id
