import pytest
from datetime import date, datetime, timedelta, time
from django.utils import timezone

import jdatetime

from apps.appointments.models import Appointment
from apps.appointments.services.calendar_month import build_jalali_month_grid, staff_dots_by_day
from apps.core.utils.dates import add_jalali_months, jalali_month_query_value, parse_jalali_month_param
from apps.customers.models import Customer
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile


@pytest.mark.parametrize(
    "jy,jm,delta,expected",
    [
        (1404, 12, 1, (1405, 1)),
        (1405, 1, -1, (1404, 12)),
        (1405, 8, 1, (1405, 9)),
        (1405, 9, -1, (1405, 8)),
    ],
)
def test_add_jalali_months(jy, jm, delta, expected):
    assert add_jalali_months(jy, jm, delta) == expected


def test_parse_jalali_month_param():
    ref = jdatetime.date(1405, 8, 15).togregorian()
    assert parse_jalali_month_param("1405-08", ref) == (1405, 8)
    assert parse_jalali_month_param("1405/09", ref) == (1405, 9)
    assert parse_jalali_month_param(None, ref) == (1405, 8)


def test_jalali_month_query_value():
    assert jalali_month_query_value(1405, 8) == "1405-08"


def test_build_month_grid_cell_count():
    jy, jm = 1405, 8
    today = jdatetime.date(jy, jm, 10).togregorian()
    grid = build_jalali_month_grid(jy, jm, today=today, selected_day=today, dots_by_day={})
    days = [c for c in grid["cells"] if not c.get("pad")]
    assert len(days) == 30
    assert len(grid["cells"]) % 7 == 0


@pytest.mark.django_db
def test_staff_dots_by_day(salon, owner_membership):
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    svc = Service.objects.create(
        salon=salon, category=cat, name="A", duration_minutes=60, price_toman=100_000
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "تست", "is_active": True, "is_bookable": True},
    )
    staff.services.add(svc)
    day = timezone.localdate() + timedelta(days=5)
    customer = Customer.objects.create(salon=salon, full_name="تست", phone="+989121111188")
    start = timezone.make_aware(datetime.combine(day, time(10, 0)))
    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=svc,
        start_at=start,
        end_at=start + timedelta(minutes=60),
        price_toman=100_000,
        status=Appointment.Status.CONFIRMED,
    )
    dots = staff_dots_by_day([appt])
    assert day in dots
    assert dots[day] == [staff.pk]