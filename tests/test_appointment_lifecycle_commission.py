"""Appointment complete/cancel and commission lifecycle tests."""

from __future__ import annotations

import threading
from datetime import timedelta

import pytest
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connections
from django.db.models import Sum
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import (
    CANCELLED_CANNOT_COMPLETE_MSG,
    AppointmentLifecycleError,
    cancel_appointment,
    complete_appointment,
)
from apps.commissions.models import CommissionEntry
from apps.commissions.services import (
    audit_appointment_commission_consistency,
    create_settlement,
    net_commission_effect_for_appointment,
)
from apps.customers.models import Customer
from apps.services.models import Service
from apps.staff.models import StaffProfile


def _is_postgresql() -> bool:
    return "postgresql" in settings.DATABASES["default"]["ENGINE"]


requires_postgresql = pytest.mark.skipif(
    not _is_postgresql(),
    reason="PostgreSQL required for concurrent lifecycle tests",
)


def _booking_appt(salon, owner_membership, *, price=1_000_000):
    customer = Customer.objects.create(salon=salon, full_name="علی", phone="+989121115501")
    service = Service.objects.create(
        salon=salon,
        name="خدمت پورسانت",
        duration_minutes=30,
        price_toman=price,
    )
    staff = StaffProfile.objects.get_or_create(
        salon=salon,
        membership=owner_membership,
        defaults={"display_name": "متخصص LC", "is_bookable": True},
    )[0]
    start = timezone.now() + timedelta(days=3)
    appt = Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        price_toman=price,
        status=Appointment.Status.CONFIRMED,
    )
    return appt, staff


def _auth_client(user, salon) -> Client:
    client = Client()
    client.force_login(user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()
    return client


def _detail_post(user, salon, appt_id, action):
    client = _auth_client(user, salon)
    url = reverse("appointments:detail", kwargs={"pk": appt_id})
    return client.post(url, {"action": action})


def _concurrent_service(call):
    barrier = threading.Barrier(2)
    results: list = [None, None]

    def worker(idx):
        connections.close_all()
        try:
            barrier.wait(timeout=15)
            results[idx] = call()
        except Exception as exc:
            results[idx] = exc
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results


@pytest.mark.django_db
def test_cancelled_appointment_cannot_complete_no_commission(salon, owner_membership):
    appt, _ = _booking_appt(salon, owner_membership)
    cancel_appointment(salon=salon, appointment_id=appt.pk)
    with pytest.raises(AppointmentLifecycleError, match=CANCELLED_CANNOT_COMPLETE_MSG):
        complete_appointment(salon=salon, appointment_id=appt.pk)
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.CANCELLED
    assert CommissionEntry.objects.filter(appointment=appt).count() == 0


@pytest.mark.django_db
def test_cancelled_then_complete_via_http(salon, owner_membership):
    appt, _ = _booking_appt(salon, owner_membership)
    cancel_appointment(salon=salon, appointment_id=appt.pk)
    resp = _detail_post(owner_membership.user, salon, appt.pk, "complete")
    assert resp.status_code == 302
    assert CANCELLED_CANNOT_COMPLETE_MSG in resp.wsgi_request._messages._queued_messages[0].message
    assert CommissionEntry.objects.filter(appointment=appt).count() == 0


@pytest.mark.django_db
def test_complete_then_cancel_zeros_net_commission(salon, owner_membership):
    appt, _ = _booking_appt(salon, owner_membership, price=500_000)
    complete_appointment(salon=salon, appointment_id=appt.pk)
    assert CommissionEntry.objects.filter(appointment=appt).exclude(status=CommissionEntry.Status.VOID).count() == 1
    assert net_commission_effect_for_appointment(appt) == 200_000
    cancel_appointment(salon=salon, appointment_id=appt.pk)
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.CANCELLED
    assert net_commission_effect_for_appointment(appt) == 0
    primary = CommissionEntry.objects.get(appointment=appt)
    assert primary.status == CommissionEntry.Status.VOID


@pytest.mark.django_db
def test_complete_settle_cancel_keeps_settlement_and_posts_adjustment(salon, owner_membership):
    appt, staff = _booking_appt(salon, owner_membership, price=1_000_000)
    complete_appointment(salon=salon, appointment_id=appt.pk)
    entry = CommissionEntry.objects.get(appointment=appt)
    assert entry.commission_amount_toman == 400_000
    create_settlement(salon, staff, entry.commission_amount_toman, "تست")
    entry.refresh_from_db()
    assert entry.status == CommissionEntry.Status.SETTLED

    cancel_appointment(salon=salon, appointment_id=appt.pk)
    entry.refresh_from_db()
    assert entry.status == CommissionEntry.Status.SETTLED
    reversal = entry.reversal_entries.get()
    assert reversal.commission_amount_toman == -400_000
    assert reversal.status == CommissionEntry.Status.RECOGNIZED
    assert net_commission_effect_for_appointment(appt) == 0

    staff_outstanding = (
        CommissionEntry.scoped(salon)
        .filter(staff=staff, status=CommissionEntry.Status.RECOGNIZED)
        .aggregate(t=Sum("commission_amount_toman"))["t"]
        or 0
    )
    assert staff_outstanding == -400_000


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_complete_single_commission(salon, owner_membership):
    appt, _ = _booking_appt(salon, owner_membership)

    def do_complete():
        return complete_appointment(salon=salon, appointment_id=appt.pk)

    results = _concurrent_service(do_complete)
    assert all(not isinstance(r, Exception) for r in results)
    assert CommissionEntry.objects.filter(appointment=appt).exclude(status=CommissionEntry.Status.VOID).count() == 1


@pytest.mark.django_db(transaction=True)
@requires_postgresql
def test_concurrent_cancel_completed_single_reversal(salon, owner_membership):
    appt, _ = _booking_appt(salon, owner_membership)
    complete_appointment(salon=salon, appointment_id=appt.pk)

    def do_cancel():
        return cancel_appointment(salon=salon, appointment_id=appt.pk)

    _concurrent_service(do_cancel)
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.CANCELLED
    assert net_commission_effect_for_appointment(appt) == 0
    assert CommissionEntry.objects.filter(reverses_entry__isnull=False).count() in (0, 1)
    primary = CommissionEntry.objects.get(appointment=appt)
    assert primary.status == CommissionEntry.Status.VOID


@pytest.mark.django_db
def test_reversal_failure_rolls_back_cancel(salon, owner_membership, monkeypatch):
    appt, _ = _booking_appt(salon, owner_membership)
    complete_appointment(salon=salon, appointment_id=appt.pk)

    def boom(appointment):
        raise ValidationError("خطای آزمایشی برگشت پورسانت")

    monkeypatch.setattr(
        "apps.appointments.services.lifecycle.reverse_commission_for_appointment",
        boom,
    )
    with pytest.raises(ValidationError):
        cancel_appointment(salon=salon, appointment_id=appt.pk)
    appt.refresh_from_db()
    assert appt.status == Appointment.Status.COMPLETED
    assert CommissionEntry.objects.get(appointment=appt).status == CommissionEntry.Status.RECOGNIZED


@pytest.mark.django_db
def test_audit_reports_cancelled_with_active_commission(salon, owner_membership):
    appt, _ = _booking_appt(salon, owner_membership)
    complete_appointment(salon=salon, appointment_id=appt.pk)
    appt.status = Appointment.Status.CANCELLED
    appt.save(update_fields=["status", "updated_at"])
    issues = audit_appointment_commission_consistency(salon=salon)
    assert any(i["appointment_id"] == appt.pk for i in issues)