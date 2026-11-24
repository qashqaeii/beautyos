"""Phase 5 money-safe lifecycle: no unapproved completion or orphaned receipts."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.appointments.services.confirmation import confirm_pending_appointment
from apps.appointments.services.lifecycle import (
    AppointmentLifecycleError, cancel_appointment, complete_appointment,
)
from apps.customers.models import Customer
from apps.finance.checkout import issue_invoice
from apps.finance.ledger import refund_payment
from apps.finance.models import Invoice, Payment
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.fixture
def pending_visit(owner_membership, salon):
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
        defaults={"display_name": "شکوفه قربانی"},
    )
    customer = Customer.objects.create(
        salon=salon, phone="+989121188001", full_name="مریم آذری",
    )
    service = Service.objects.create(salon=salon, name="پاکسازی پوست", price_toman=500_000)
    start = timezone.now() + timedelta(days=3)
    appointment = Appointment.objects.create(
        salon=salon, staff=staff, customer=customer, service=service,
        start_at=start, end_at=start + timedelta(minutes=30),
        price_toman=500_000, status=Appointment.Status.PENDING,
    )
    return appointment


@pytest.mark.django_db
def test_pending_appointment_cannot_complete_before_approval(
    salon, pending_visit
):
    with pytest.raises(AppointmentLifecycleError, match="تأیید"):
        complete_appointment(salon=salon, appointment_id=pending_visit.pk)
    pending_visit.refresh_from_db()
    assert pending_visit.status == Appointment.Status.PENDING
    assert pending_visit.completed_at is None
    confirm_pending_appointment(salon=salon, appointment_id=pending_visit.pk)
    completed = complete_appointment(salon=salon, appointment_id=pending_visit.pk)
    assert completed.status == Appointment.Status.COMPLETED


@pytest.mark.django_db
def test_cannot_cancel_collected_deposit_until_refunded(
    salon, owner_membership, pending_visit
):
    visit = pending_visit
    payment = Payment.objects.create(
        salon=salon, appointment=visit, customer=visit.customer,
        total_amount_toman=500_000, paid_amount_toman=120_000,
        status=Payment.Status.PARTIAL, method=Payment.Method.CARD,
    )
    with pytest.raises(AppointmentLifecycleError, match="مسترد"):
        cancel_appointment(salon=salon, appointment_id=visit.pk)
    visit.refresh_from_db()
    assert visit.status == Appointment.Status.PENDING

    refund_payment(
        salon=salon, payment_id=payment.pk, amount=120_000,
        reason="لغو نوبت قبل از ارائه خدمت",
        request_key=uuid4(), actor=owner_membership.user,
    )
    canceled = cancel_appointment(salon=salon, appointment_id=visit.pk)
    assert canceled.status == Appointment.Status.CANCELLED
    assert canceled.cancelled_at


@pytest.mark.django_db
def test_issued_invoice_cannot_be_orphaned_by_late_cancellation(
    salon, owner_membership, pending_visit
):
    visit = pending_visit
    confirm_pending_appointment(salon=salon, appointment_id=visit.pk)
    complete_appointment(salon=salon, appointment_id=visit.pk)
    invoice = issue_invoice(
        salon=salon, customer_id=visit.customer_id,
        appointment_ids=[visit.pk], request_key=uuid4(), discount=0,
        amounts={"cash": 0, "card": 0, "transfer": 0},
        actor=owner_membership.user,
    )
    assert Invoice.scoped(salon).filter(pk=invoice.pk).exists()
    with pytest.raises(AppointmentLifecycleError, match="فاکتور"):
        cancel_appointment(salon=salon, appointment_id=visit.pk)
    visit.refresh_from_db()
    assert visit.status == Appointment.Status.COMPLETED
    assert Invoice.scoped(salon).get(pk=invoice.pk).lines.count() == 1


@pytest.mark.django_db
def test_detail_page_compact_finance_actions_and_status(
    client, salon, owner_membership, pending_visit
):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    url = reverse("appointments:detail", kwargs={"pk": pending_visit.pk})
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert "appointment-operations.css" in html
    assert "اطلاعات مراجعه" in html
    assert "وضعیت مالی خدمت" in html
    assert "تأیید نوبت" in html
    assert "۵۰۰.۰۰۰" in html
    confirm_pending_appointment(salon=salon, appointment_id=pending_visit.pk)
    complete_appointment(salon=salon, appointment_id=pending_visit.pk)
    response = client.get(url)
    assert "صدور فاکتور و تسویه" in response.content.decode()
