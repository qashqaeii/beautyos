"""Concurrent internal booking (/appointments/new/) — requires PostgreSQL."""

from __future__ import annotations

import threading
from datetime import time, timedelta

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import Client
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer, CustomerActivity
from apps.finance.models import Payment
from apps.services.models import Service, ServiceCategory
from apps.staff.models import StaffProfile, StaffWorkHours

def _is_postgresql() -> bool:
    return "postgresql" in settings.DATABASES["default"]["ENGINE"]


requires_postgresql = pytest.mark.skipif(
    not _is_postgresql(),
    reason="PostgreSQL required (set DATABASE_URL in .env)",
)

OVERLAP_MSG = "این بازه با نوبت دیگری تداخل دارد"


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


def _concurrent_booking_setup(salon, owner_membership, *, day_offset=28):
    cat = ServiceCategory.objects.create(salon=salon, name="conc-cat")
    service = Service.objects.create(
        salon=salon,
        category=cat,
        name="خدمت هم‌زمان",
        duration_minutes=60,
        price_toman=1_000_000,
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص هم‌زمان", "is_bookable": True},
    )
    staff.services.add(service)
    start = timezone.localtime(timezone.now() + timedelta(days=day_offset)).replace(
        hour=11, minute=0, second=0, microsecond=0
    )
    weekday = (start.date().weekday() + 2) % 7
    StaffWorkHours.objects.get_or_create(
        salon=salon,
        staff=staff,
        weekday=weekday,
        defaults={"start_time": time(8, 0), "end_time": time(22, 0)},
    )
    return staff, service, start


def _auth_client(user, salon) -> Client:
    client = Client()
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    return client


def _concurrent_posts(user, salon, fields_a, fields_b):
    barrier = threading.Barrier(2)
    results: list[dict] = [{}, {}]

    def worker(fields, idx):
        connections.close_all()
        try:
            client = _auth_client(user, salon)
            barrier.wait(timeout=15)
            resp = client.post("/appointments/new/", fields)
            results[idx] = {
                "status": resp.status_code,
                "body": resp.content.decode(),
                "url": resp.url,
            }
        except Exception as exc:  # pragma: no cover
            results[idx] = {"error": repr(exc)}
        finally:
            connections.close_all()

    threads = [
        threading.Thread(target=worker, args=(fields_a, 0)),
        threading.Thread(target=worker, args=(fields_b, 1)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_new_customer_deposit_single_winner(salon, owner_membership):
    """test_concurrent_new_customer_deposit_single_winner"""
    staff, service, start = _concurrent_booking_setup(salon, owner_membership)
    phone_a = "09121111301"
    phone_b = "09121111302"
    phone_a_e164 = "+989121111301"
    phone_b_e164 = "+989121111302"

    fields_a = _appt_post_fields(
        start,
        staff,
        service,
        new_customer_mode="on",
        new_customer_first_name="مشتری",
        new_customer_last_name="اول",
        new_customer_phone=phone_a,
        deposit_amount_toman="200000",
        deposit_method=Payment.Method.CASH,
    )
    fields_b = _appt_post_fields(
        start,
        staff,
        service,
        new_customer_mode="on",
        new_customer_first_name="مشتری",
        new_customer_last_name="دوم",
        new_customer_phone=phone_b,
        deposit_amount_toman="250000",
        deposit_method=Payment.Method.CARD,
    )

    before_customers = Customer.scoped(salon).count()
    before_appts = Appointment.scoped(salon).filter(staff=staff, start_at=start).count()
    before_payments = Payment.scoped(salon).count()

    results = _concurrent_posts(owner_membership.user, salon, fields_a, fields_b)

    assert not results[0].get("error") and not results[1].get("error"), results

    statuses = {results[0]["status"], results[1]["status"]}
    assert statuses == {200, 302}, results

    bodies = [results[0]["body"], results[1]["body"]]
    overlap_hits = sum(1 for b in bodies if OVERLAP_MSG in b)
    success_hits = sum(1 for r in results if r["status"] == 302)
    assert success_hits == 1
    assert overlap_hits == 1

    appt_count = Appointment.scoped(salon).filter(staff=staff, start_at=start).count()
    assert appt_count == before_appts + 1

    customers_a = Customer.scoped(salon).filter(phone=phone_a_e164).count()
    customers_b = Customer.scoped(salon).filter(phone=phone_b_e164).count()
    assert customers_a + customers_b == 1
    assert Customer.scoped(salon).count() == before_customers + 1

    assert Payment.scoped(salon).count() == before_payments + 1
    winner_phone = phone_a_e164 if customers_a == 1 else phone_b_e164
    winner = Customer.scoped(salon).get(phone=winner_phone)
    appt = Appointment.scoped(salon).get(staff=staff, start_at=start)
    assert appt.customer_id == winner.pk
    pay = Payment.scoped(salon).get(appointment=appt)
    assert pay.customer_id == winner.pk
    assert pay.paid_amount_toman in (200_000, 250_000)
    assert pay.method in (Payment.Method.CASH, Payment.Method.CARD)

    loser_phone = phone_b_e164 if winner_phone == phone_a_e164 else phone_a_e164
    assert not Customer.scoped(salon).filter(phone=loser_phone).exists()
    assert not Payment.scoped(salon).filter(customer__phone=loser_phone).exists()


@pytest.mark.django_db
def test_deposit_failure_rolls_back_customer_appointment_and_payment(
    client, salon, owner_membership, monkeypatch
):
    """test_deposit_failure_rolls_back_customer_appointment_and_payment"""
    staff, service, start = _concurrent_booking_setup(salon, owner_membership, day_offset=29)
    phone = "09121111399"
    phone_e164 = "+989121111399"

    def failing_deposit(*, salon, customer, appointment, amount_toman, method):
        assert customer.pk
        assert appointment.pk
        raise ValidationError("خطای آزمایشی ثبت بیعانه")

    monkeypatch.setattr("apps.appointments.views.create_appointment_deposit", failing_deposit)

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    before_customers = Customer.scoped(salon).count()
    before_appts = Appointment.scoped(salon).count()
    before_payments = Payment.scoped(salon).count()
    before_activity = CustomerActivity.objects.filter(salon=salon).count()

    fields = _appt_post_fields(
        start,
        staff,
        service,
        new_customer_mode="on",
        new_customer_first_name="تست",
        new_customer_last_name="Rollback",
        new_customer_phone=phone,
        deposit_amount_toman="150000",
        deposit_method=Payment.Method.CASH,
    )
    resp = client.post("/appointments/new/", fields)
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "خطای آزمایشی ثبت بیعانه" in body or "بیعانه" in body.lower()

    assert Customer.scoped(salon).count() == before_customers
    assert not Customer.scoped(salon).filter(phone=phone_e164).exists()
    assert Appointment.scoped(salon).count() == before_appts
    assert Payment.scoped(salon).count() == before_payments
    assert CustomerActivity.objects.filter(salon=salon).count() == before_activity