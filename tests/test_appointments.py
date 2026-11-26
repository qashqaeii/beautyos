from datetime import timedelta

import pytest
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.scheduling import SchedulingError, create_appointment
from apps.customers.models import Customer
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours
from datetime import time


@pytest.mark.django_db
def test_appointment_conflict(salon, owner_membership):
    from apps.accounts.models import User

    user = owner_membership.user
    cat = ServiceCategory.objects.create(salon=salon, name="c")
    service = Service.objects.create(salon=salon, category=cat, name="svc", duration_minutes=60, price_toman=100)
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "S", "is_bookable": True},
    )
    staff.services.add(service)
    customer = Customer.objects.create(salon=salon, full_name="C", phone="+989121234560")
    start = timezone.now() + timedelta(days=1)
    start = timezone.localtime(start).replace(hour=10, minute=0, second=0, microsecond=0)
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    create_appointment(salon=salon, customer=customer, staff=staff, service=service, start=start, actor=user)
    with pytest.raises(SchedulingError):
        create_appointment(salon=salon, customer=customer, staff=staff, service=service, start=start, actor=user)


@pytest.mark.django_db
def test_booking_rejects_unassigned_service(salon, owner_membership):
    """Server-side enforcement must not rely on the specialist dropdown filter."""
    user = owner_membership.user
    category = ServiceCategory.objects.create(salon=salon, name="Other category")
    service = Service.objects.create(
        salon=salon, category=category, name="Unassigned service",
        duration_minutes=45, price_toman=200,
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
        defaults={"display_name": "Specialist", "is_bookable": True},
    )
    staff.services.remove(service)
    customer = Customer.objects.create(
        salon=salon, full_name="Customer", phone="+989121234569",
    )
    start = timezone.localtime(timezone.now() + timedelta(days=2)).replace(
        hour=10, minute=0, second=0, microsecond=0,
    )
    with pytest.raises(SchedulingError):
        create_appointment(
            salon=salon, customer=customer, staff=staff,
            service=service, start=start, actor=user,
        )
    assert not Appointment.objects.filter(
        salon=salon, customer=customer, service=service,
    ).exists()
