"""Regression checks for the opt-in Phase 5 delivery queue."""
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.retention.automation import queue_appointment_event
from apps.retention.delivery import dispatch_due, reconcile_delivery
from apps.retention.models import AutomationMessage, AutomationPolicy
from apps.services.models import Service
from apps.staff.models import StaffProfile


class FakeDelivery:
    def __init__(self):
        self.calls = 0

    def send(self, row, phone):
        self.calls += 1
        raise TimeoutError("Response unavailable")

    def lookup(self, row):
        return "delivered", "10001"


@pytest.mark.django_db
@override_settings(BEAUTYOS_AUTOMATION_SEND_ENABLED=True)
def test_event_once_and_unknown_not_retried(salon, owner_membership):
    now = timezone.now()
    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121000000")
    staff, _ = StaffProfile.objects.get_or_create(salon=salon, membership=owner_membership)
    service = Service.objects.create(salon=salon, name="خدمت", price_toman=100000)
    appt = Appointment.objects.create(salon=salon, customer=customer, staff=staff, service=service,
        start_at=now+timedelta(hours=12), end_at=now+timedelta(hours=13),
        status=Appointment.Status.CONFIRMED)
    AutomationPolicy.objects.create(salon=salon, confirmation_enabled=True)
    assert queue_appointment_event(appt, "confirmation", now) == 1
    assert queue_appointment_event(appt, "confirmation", now) == 0
    gateway = FakeDelivery()
    assert dispatch_due(salon, now, transport=gateway)["unknown"] == 1
    assert dispatch_due(salon, now, transport=gateway)["accepted"] == 0
    assert gateway.calls == 1
    assert reconcile_delivery(salon, now+timedelta(minutes=6), transport=gateway) == 1
    assert AutomationMessage.scoped(salon).get().status == "delivered"


@pytest.mark.django_db
@override_settings(BEAUTYOS_AUTOMATION_SEND_ENABLED=False)
def test_dispatch_requires_global_opt_in(salon):
    gateway = FakeDelivery()
    assert dispatch_due(salon, transport=gateway)["disabled"]
    assert gateway.calls == 0
