import pytest
from django.core.exceptions import ValidationError

from apps.commissions.models import CommissionEntry
from apps.commissions.services import create_settlement, staff_outstanding_commission


@pytest.mark.django_db
def test_partial_settlement_reduces_outstanding(salon, owner_membership):
    from apps.appointments.models import Appointment
    from apps.customers.models import Customer
    from apps.services.models import Service
    from apps.staff.models import StaffProfile
    from django.utils import timezone

    customer = Customer.objects.create(salon=salon, phone="+989121100200", full_name="مشتری")
    service = Service.objects.create(salon=salon, name="خدمت", duration_minutes=30, price_toman=1_000_000)
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص", "is_bookable": True},
    )
    start = timezone.now()
    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=start + timezone.timedelta(minutes=30),
        status=Appointment.Status.CONFIRMED,
        price_toman=1_000_000,
    )
    appt.status = Appointment.Status.COMPLETED
    appt.save(update_fields=["status", "updated_at"])
    entry = CommissionEntry.objects.get(appointment=appt)
    entry.commission_amount_toman = 400_000
    entry.base_amount_toman = 1_000_000
    entry.status = CommissionEntry.Status.RECOGNIZED
    entry.settled_amount_toman = 0
    entry.save(update_fields=["commission_amount_toman", "base_amount_toman", "status", "settled_amount_toman"])
    assert staff_outstanding_commission(salon=salon, staff=staff) == 400_000
    create_settlement(salon, staff, 100_000, "جزئی")
    entry.refresh_from_db()
    assert entry.settled_amount_toman == 100_000
    assert entry.status == CommissionEntry.Status.RECOGNIZED
    assert staff_outstanding_commission(salon=salon, staff=staff) == 300_000


@pytest.mark.django_db
def test_settlement_rejects_amount_above_outstanding(salon, owner_membership):
    from apps.commissions.models import CommissionEntry
    from apps.staff.models import StaffProfile

    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص", "is_bookable": True},
    )
    CommissionEntry.objects.create(
        salon=salon,
        appointment=None,
        staff=staff,
        base_amount_toman=0,
        commission_amount_toman=400_000,
        status=CommissionEntry.Status.RECOGNIZED,
    )
    with pytest.raises(ValidationError):
        create_settlement(salon, staff, 500_000)