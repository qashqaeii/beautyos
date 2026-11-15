import pytest

from apps.core.utils.phone import normalize_iran_mobile


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("09121234567", "+989121234567"),
        ("۰۹۱۲۱۲۳۴۵۶۷", "+989121234567"),
        ("9121234567", "+989121234567"),
    ],
)
def test_normalize_iran_mobile(raw, expected):
    assert normalize_iran_mobile(raw) == expected


def test_invalid_phone():
    with pytest.raises(ValueError):
        normalize_iran_mobile("12345")
