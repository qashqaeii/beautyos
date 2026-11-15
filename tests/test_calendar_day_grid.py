import pytest
from datetime import datetime, time, timedelta
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.calendar_day_grid import build_day_calendar_grid
from apps.customers.models import Customer
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours


@pytest.mark.django_db
def test_calendar_grid_marks_other_service_busy(salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    svc_a = Service.objects.create(
        salon=salon, category=cat, name="A", duration_minutes=60, price_toman=100_000
    )
    svc_b = Service.objects.create(
        salon=salon, category=cat, name="B", duration_minutes=60, price_toman=100_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "تست متخصص", "is_active": True, "is_bookable": True},
    )
    staff.services.add(svc_a, svc_b)
    day = timezone.localdate() + timedelta(days=3)
    weekday = (day.weekday() + 2) % 7
    StaffWorkHours.objects.update_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(9, 0), "end_time": time(18, 0), "is_closed": False},
    )
    customer = Customer.objects.create(salon=salon, full_name="تست", phone="+989121111199")
    start = timezone.make_aware(datetime.combine(day, time(10, 0)))
    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=svc_b,
        start_at=start,
        end_at=start + timedelta(minutes=60),
        price_toman=100_000,
        status=Appointment.Status.CONFIRMED,
    )
    grid = build_day_calendar_grid(
        day,
        [staff],
        [appt],
        selected_service_id=svc_a.pk,
        can_book=True,
    )
    segs = grid["columns"][0]["segments"]
    busy = [s for s in segs if s["type"] == "busy"]
    assert busy
    assert busy[0]["label"] == "رزرو شده"