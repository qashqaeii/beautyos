"""Salon hours constrain both displayed availability and direct server-side booking."""
from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.appointments.services.scheduling import SchedulingError, iter_day_slots, staff_is_available
from apps.salons.models import SalonWorkHours
from tests.test_public_booking_flow import public_booking_setup  # noqa: F401


@pytest.mark.django_db
def test_day_slots_intersect_salon_and_specialist_hours(salon, public_booking_setup):
    data = public_booking_setup
    weekday = (data["day"].weekday() + 2) % 7
    SalonWorkHours.objects.create(
        salon=salon, weekday=weekday, start_time=time(11, 0), end_time=time(14, 0),
    )
    available = list(iter_day_slots(data["staff"], data["day"], 30))
    assert available
    assert available[0].astimezone(timezone.get_current_timezone()).time() >= time(11, 0)
    assert available[-1].astimezone(timezone.get_current_timezone()).time() <= time(13, 30)
    with pytest.raises(SchedulingError, match="ساعات فعالیت سالن"):
        staff_is_available(data["staff"], timezone.datetime.fromisoformat(data["start_iso"]), timezone.datetime.fromisoformat(data["start_iso"]) + timedelta(minutes=30))


@pytest.mark.django_db
def test_closed_salon_blocks_slot_even_when_specialist_is_available(salon, public_booking_setup):
    data = public_booking_setup
    weekday = (data["day"].weekday() + 2) % 7
    SalonWorkHours.objects.create(
        salon=salon, weekday=weekday, is_closed=True,
        start_time=time(0, 0), end_time=time(0, 0),
    )
    assert list(iter_day_slots(data["staff"], data["day"], 30)) == []
    with pytest.raises(SchedulingError, match="سالن در این روز تعطیل است"):
        staff_is_available(data["staff"], timezone.datetime.fromisoformat(data["start_iso"]), timezone.datetime.fromisoformat(data["start_iso"]) + timedelta(minutes=30))
