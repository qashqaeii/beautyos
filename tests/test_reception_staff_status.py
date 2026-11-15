import pytest

from apps.dashboard.role_services import reception_staff_day_status


@pytest.mark.parametrize(
    "capacity,expected",
    [
        (None, "ساعت کاری ثبت نشده"),
        ({"on_leave": True, "free_minutes": 0, "total_minutes": 0}, "مرخصی امروز"),
        ({"on_leave": False, "free_minutes": 0, "total_minutes": 120}, "وقت آزاد ندارد"),
        ({"on_leave": False, "free_minutes": 45, "total_minutes": 120}, "45 دقیقه آزاد"),
    ],
)
def test_reception_staff_day_status(capacity, expected):
    assert reception_staff_day_status(capacity) == expected
