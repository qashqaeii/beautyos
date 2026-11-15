from datetime import time, timedelta

import pytest
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.dashboard.role_services import appointment_payment_summary
from apps.finance.models import Payment
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours


def _appt_post_fields(start, staff, service, **extra):
    local = timezone.localtime(start)
    base = {
        "staff": staff.pk,
        "service": service.pk,
        "appointment_date": local.date().isoformat(),
        "appointment_time": local.strftime("%H:%M"),
        "notes": "",
        "status": Appointment.Status.CONFIRMED,
    }
    base.update(extra)
    return base


def _booking_setup(salon, owner_membership, *, price_toman=1_000_000, day_offset=10):
    cat = ServiceCategory.objects.create(salon=salon, name="deposit-cat")
    service = Service.objects.create(
        salon=salon,
        category=cat,
        name="خدمت بیعانه",
        duration_minutes=60,
        price_toman=price_toman,
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص بیعانه", "is_bookable": True},
    )
    staff.services.add(service)
    customer = Customer.objects.create(salon=salon, full_name="مشتری بیعانه", phone="+989121119991")
    start = timezone.localtime(timezone.now() + timedelta(days=day_offset)).replace(
        hour=14, minute=0, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    return customer, staff, service, start


@pytest.mark.django_db
def test_appointment_without_deposit_no_payment(client, salon, owner_membership):
    customer, staff, service, start = _booking_setup(salon, owner_membership)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        customer=customer.pk,
        customer_search=f"{customer.full_name}",
    )
    resp = client.post("/appointments/new/", fields, follow=True)
    assert resp.status_code == 200, resp.content.decode()[:2000]
    appt = Appointment.objects.filter(customer=customer).order_by("-id").first()
    assert appt is not None
    assert Payment.scoped(salon).filter(appointment=appt).count() == 0
    summary = appointment_payment_summary(appt)
    assert summary["owed_toman"] == 1_000_000
    assert summary["paid_toman"] == 0


@pytest.mark.django_db
def test_appointment_deposit_creates_single_partial_payment(client, salon, owner_membership):
    customer, staff, service, start = _booking_setup(salon, owner_membership)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        customer=customer.pk,
        customer_search=f"{customer.full_name}",
        deposit_amount_toman="300000",
        deposit_method=Payment.Method.CASH,
    )
    resp = client.post("/appointments/new/", fields, follow=True)
    assert resp.status_code == 200, resp.content.decode()[:2000]
    appt = Appointment.objects.filter(customer=customer).order_by("-id").first()
    assert appt is not None
    assert appt.price_toman == 1_000_000
    payments = list(Payment.scoped(salon).filter(appointment=appt))
    assert len(payments) == 1
    pay = payments[0]
    assert pay.total_amount_toman == 1_000_000
    assert pay.paid_amount_toman == 300_000
    assert pay.status == Payment.Status.PARTIAL
    summary = appointment_payment_summary(appt)
    assert summary["paid_toman"] == 300_000
    assert summary["owed_toman"] == 700_000


@pytest.mark.django_db
def test_appointment_deposit_rejects_amount_above_price(client, salon, owner_membership):
    customer, staff, service, start = _booking_setup(salon, owner_membership, day_offset=11)
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    before = Appointment.objects.count()
    fields = _appt_post_fields(
        start,
        staff,
        service,
        customer=customer.pk,
        customer_search=f"{customer.full_name}",
        deposit_amount_toman="۱.۵۰۰.۰۰۰",
        deposit_method=Payment.Method.CASH,
    )
    resp = client.post("/appointments/new/", fields)
    assert resp.status_code == 200
    assert Appointment.objects.count() == before
    assert "بیشتر از مبلغ نوبت" in resp.content.decode()
