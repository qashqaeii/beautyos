import re

import phonenumbers

IR_MOBILE_PATTERN = re.compile(r"^(\+98|0098|98|0)?9\d{9}$")


def normalize_iran_mobile(raw: str) -> str:
    """Return E.164 Iran mobile (+989xxxxxxxxx) or raise ValueError."""
    if not raw or not str(raw).strip():
        raise ValueError("شماره موبایل الزامی است.")
    digits = re.sub(r"[\s\-()]", "", str(raw).strip())
    digits = digits.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    digits = digits.replace("ي", "ی").replace("ك", "ک")
    if digits.startswith("+98"):
        candidate = digits
    elif digits.startswith("0098"):
        candidate = "+98" + digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        candidate = "+" + digits
    elif digits.startswith("09") and len(digits) == 11:
        candidate = "+98" + digits[1:]
    elif digits.startswith("9") and len(digits) == 10:
        candidate = "+98" + digits
    else:
        candidate = digits if digits.startswith("+") else "+98" + digits.lstrip("0")

    try:
        parsed = phonenumbers.parse(candidate, "IR")
    except phonenumbers.NumberParseException as exc:
        raise ValueError("شماره موبایل معتبر نیست.") from exc

    if not phonenumbers.is_valid_number(parsed):
        raise ValueError("شماره موبایل معتبر نیست.")
    ntype = phonenumbers.number_type(parsed)
    if ntype not in (
        phonenumbers.PhoneNumberType.MOBILE,
        phonenumbers.PhoneNumberType.FIXED_LINE_OR_MOBILE,
    ):
        raise ValueError("فقط شماره موبایل ایران پذیرفته می‌شود.")

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def display_iran_mobile(e164: str) -> str:
    try:
        parsed = phonenumbers.parse(e164, "IR")
        national = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        return national.replace(" ", "")
    except phonenumbers.NumberParseException:
        return e164
