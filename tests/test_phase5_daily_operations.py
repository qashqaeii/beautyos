"""Phase 5: real salon-day lifecycle from reception to audited invoice."""
from datetime import datetime, time, timedelta
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.audit.models import AuditLog
from apps.commissions.models import CommissionEntry
from apps.customers.models import Customer
from apps.finance.checkout import issue_invoice
from apps.finance.models import Invoice, Payment
from apps.salons.models import SalonMembership
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.fixture
def day_case(salon, owner_membership):
    customer = Customer.objects.create(
        salon=salon, full_name="نرگس امینی", phone="+989121111444",
    )
    service = Service.objects.create(
        salon=salon, name="مراقبت و ترمیم مو",
        price_toman=800_000, duration_minutes=60,
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
        defaults={"display_name": "مهسا مهربان", "is_active": True, "is_bookable": True},
    )
    day = timezone.localdate() + timedelta(days=1)
    start = timezone.make_aware(
        datetime.combine(day, time(10, 0)), timezone.get_current_timezone(),
    )
    appointment = Appointment.objects.create(
        salon=salon, customer=customer, service=service, staff=staff,
        start_at=start, end_at=start + timedelta(hours=1),
        status=Appointment.Status.PENDING, source=Appointment.Source.PUBLIC,
        price_toman=800_000,
    )
    return customer, staff, service, appointment, day


def authenticate(client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_salon_id"] = str(membership.salon_id)
    session.save()


def route(action, appointment):
    return reverse("reception:" + action, kwargs={"pk": appointment.pk})


@pytest.mark.django_db
def test_phase5_day_queue_shows_actions_real_payment_and_tenant_data(
    client, salon, salon_b, owner_membership, day_case
):
    customer, staff, service, appointment, day = day_case
    other_customer = Customer.objects.create(salon=salon_b, phone="+989121111445", full_name="مشتری خصوصی بتا")
    other_service = Service.objects.create(salon=salon_b, name="خدمت خصوصی", price_toman=400_000)
    other_staff = StaffProfile.objects.create(salon=salon_b, display_name="متخصص بتا")
    Appointment.objects.create(
        salon=salon_b, customer=other_customer, staff=other_staff, service=other_service,
        start_at=appointment.start_at, end_at=appointment.end_at, status=Appointment.Status.CONFIRMED,
    )
    authenticate(client, owner_membership)
    response = client.get(reverse("reception:desk"), {"day": day.isoformat()})
    assert response.status_code == 200
    text = response.content.decode()
    assert "جریان کار امروز سالن" in text
    assert "تأیید نوبت" in text
    assert "نرگس امینی" in text
    assert "800,000" in text or "۸۰۰٬۰۰۰" in text or "۸۰۰,۰۰۰" in text
    assert "مشتری خصوصی بتا" not in text
    assert response.context["day_operations_summary"]["total"] == 1
    assert response.context["day_operations_summary"]["pending"] == 1
    assert response.context["day_operations"][0]["appointment"].pk == appointment.pk


@pytest.mark.django_db
def test_phase5_pending_must_be_confirmed_then_checkin_then_complete_and_invoice(
    client, owner_membership, salon, day_case
):
    customer, staff, service, appointment, day = day_case
    authenticate(client, owner_membership)
    payload = {"day": day.isoformat()}
    assert client.get(route("confirm", appointment)).status_code == 405
    assert client.get(route("checkin", appointment)).status_code == 405
    assert client.get(route("complete", appointment)).status_code == 405

    # Cannot skip the confirmation step.
    assert client.post(route("checkin", appointment), payload).status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.PENDING
    assert client.post(route("complete", appointment), payload).status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.PENDING

    response = client.post(route("confirm", appointment), payload)
    assert response.status_code == 302
    assert "day=" in response.url
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    assert client.post(route("confirm", appointment), payload).status_code == 302

    assert client.post(route("checkin", appointment), payload).status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CHECKED_IN
    assert client.post(route("checkin", appointment), payload).status_code == 302

    assert client.post(route("complete", appointment), payload).status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.COMPLETED
    assert appointment.completed_at is not None
    assert client.post(route("complete", appointment), payload).status_code == 302
    assert CommissionEntry.scoped(salon).filter(appointment=appointment).count() == 1
    assert AuditLog.scoped(salon).filter(
        entity_type="appointment", entity_id=str(appointment.pk),
        message="تکمیل مراجعه در پذیرش",
    ).count() == 1
    assert AuditLog.scoped(salon).filter(
        entity_type="appointment", entity_id=str(appointment.pk),
        message="ثبت ورود مشتری در پذیرش",
    ).count() == 1

    response = client.get(reverse("reception:desk"), {"day": day.isoformat()})
    assert response.context["day_operations_summary"]["completed"] == 1
    assert response.context["day_operations_summary"]["outstanding_toman"] == 800_000
    assert "رفتن به صندوق" in response.content.decode()

    invoice = issue_invoice(
        salon=salon, customer_id=customer.pk,
        appointment_ids=[appointment.pk], request_key=uuid4(), discount=0,
        amounts={"cash": 300_000, "card": 500_000, "transfer": 0},
        actor=owner_membership.user,
    )
    assert invoice.gross_toman == 800_000
    assert invoice.received_toman == 800_000
    assert invoice.balance_at_issue_toman == 0
    assert Payment.scoped(salon).filter(invoice=invoice).count() == 2
    assert Invoice.scoped(salon).count() == 1

    response = client.get(reverse("reception:desk"), {"day": day.isoformat()})
    assert "مشاهده فاکتور" in response.content.decode()
    assert "رفتن به صندوق" not in response.content.decode()
    assert response.context["day_operations_summary"]["outstanding_toman"] == 0


@pytest.mark.django_db
def test_phase5_paid_deposit_stays_part_of_one_obligation(
    client, owner_membership, salon, day_case
):
    customer, staff, service, appointment, day = day_case
    Payment.objects.create(
        salon=salon, customer=customer, appointment=appointment,
        paid_amount_toman=150_000, total_amount_toman=800_000,
        status=Payment.Status.PARTIAL, method=Payment.Method.CASH,
    )
    authenticate(client, owner_membership)
    payload = {"day": day.isoformat()}
    for action in ("confirm", "checkin", "complete"):
        assert client.post(route(action, appointment), payload).status_code == 302
    response = client.get(reverse("reception:desk"), {"day": day.isoformat()})
    assert response.context["day_operations_summary"]["outstanding_toman"] == 650_000
    invoice = issue_invoice(
        salon=salon, customer_id=customer.pk, appointment_ids=[appointment.pk],
        request_key=uuid4(), discount=0,
        amounts={"cash": 0, "card": 650_000, "transfer": 0},
        actor=owner_membership.user,
    )
    assert invoice.prior_paid_toman == 150_000
    assert invoice.received_toman == 650_000
    assert invoice.balance_at_issue_toman == 0


@pytest.mark.django_db
def test_phase5_post_actions_are_csrf_protected(salon, owner_membership, day_case):
    _, _, _, appointment, _ = day_case
    test_client = Client(enforce_csrf_checks=True)
    authenticate(test_client, owner_membership)
    for action in ("confirm", "checkin", "complete"):
        assert test_client.post(route(action, appointment)).status_code == 403
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.PENDING


@pytest.mark.django_db
def test_phase5_cross_tenant_or_specialist_cannot_operate_reception(
    client, salon_b, owner_membership, day_case
):
    _, _, _, appointment, day = day_case
    other_user = User.objects.create_user(phone="+989121118887", full_name="مالک سالن دیگر")
    other_membership = SalonMembership.objects.create(
        user=other_user, salon=salon_b, role=SalonMembership.Role.OWNER,
    )
    authenticate(client, other_membership)
    for action in ("confirm", "checkin", "complete"):
        assert client.post(route(action, appointment), {"day": day.isoformat()}).status_code == 404
    user = User.objects.create_user(phone="+989121118888", full_name="متخصص بدون اختیار")
    specialist = SalonMembership.objects.create(
        user=user, salon=owner_membership.salon, role=SalonMembership.Role.SPECIALIST,
    )
    authenticate(client, specialist)
    for action in ("confirm", "checkin", "complete"):
        assert client.post(route(action, appointment), {"day": day.isoformat()}).status_code == 403
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.PENDING
