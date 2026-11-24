"""Inline reception invoice issue/print: real ledger, scopes and idempotency."""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import complete_appointment
from apps.customers.models import Customer
from apps.finance.models import Invoice, InvoiceLine, Payment
from apps.packages.models import CustomerPackage, PackageSessionUse, ServicePackage
from apps.salons.models import SalonMembership
from tests.test_phase5_daily_operations import day_case  # noqa: F401


def sign_in(client, membership):
    client.force_login(membership.user)
    session = client.session
    session["active_salon_id"] = str(membership.salon_id)
    session.save()


def issue_url(appointment):
    return reverse("reception:issue_invoice", kwargs={"appointment_id": appointment.pk})


def payload(*, key=None, cash=0, card=0, transfer=0, discount=0, print_now=True):
    return {
        "request_key": str(key or uuid4()),
        "cash": cash, "card": card, "transfer": transfer, "discount": discount,
        "print": "1" if print_now else "0",
    }


@pytest.mark.django_db
def test_reception_can_issue_and_print_invoice_with_prior_deposit(
    client, salon, owner_membership, day_case,
):
    customer, _, _, appointment, day = day_case
    complete_error = None
    from apps.appointments.services.confirmation import confirm_pending_appointment
    confirm_pending_appointment(salon=salon, appointment_id=appointment.pk)
    complete_appointment(salon=salon, appointment_id=appointment.pk)
    Payment.objects.create(
        salon=salon, customer=customer, appointment=appointment,
        paid_amount_toman=200_000, total_amount_toman=800_000,
        status=Payment.Status.PARTIAL, method=Payment.Method.CASH,
    )
    sign_in(client, owner_membership)
    desk = client.get(reverse("reception:desk"), {"day": day.isoformat()})
    assert desk.status_code == 200
    html = desk.content.decode()
    assert "صدور فاکتور و چاپ" in html
    assert "ثبت و چاپ فاکتور" in html
    assert "فاکتورهای صادرشده" in html
    assert 'name="request_key"' in html
    assert 'name="cash"' in html and 'name="card"' in html
    assert desk.context["day_operations"][0]["can_checkout"] is True
    request_key = uuid4()
    response = client.post(issue_url(appointment), payload(key=request_key, card=500_000, discount=100_000))
    assert response.status_code == 302
    invoice = Invoice.scoped(salon).get()
    assert response.url == reverse("finance:invoice_detail", args=[invoice.pk]) + "?print=1"
    assert invoice.gross_toman == 800_000
    assert invoice.prior_paid_toman == 200_000
    assert invoice.received_toman == 500_000
    assert invoice.discount_toman == 100_000
    assert invoice.balance_at_issue_toman == 0
    assert InvoiceLine.scoped(salon).filter(invoice=invoice, appointment=appointment).count() == 1
    assert Payment.scoped(salon).filter(invoice=invoice).count() == 1

    print_page = client.get(response.url)
    assert print_page.status_code == 200
    assert print_page.context["auto_print"] is True
    assert 'window.print()' in print_page.content.decode()
    assert customer.phone in print_page.content.decode()
    assert "میز پذیرش" in print_page.content.decode()
    plain = client.get(reverse("finance:invoice_detail", args=[invoice.pk]))
    assert plain.context["auto_print"] is False
    assert "window.print(); }, { once: true }" not in plain.content.decode()

    desk = client.get(reverse("reception:desk"), {"day": day.isoformat()})
    html = desk.content.decode()
    assert "چاپ فاکتور" in html
    assert f"/invoices/{invoice.pk}/?print=1" in html
    assert "صدور فاکتور و چاپ برای" not in html

    # Posting from a stale tab cannot issue a duplicate invoice or charge again.
    again = client.post(issue_url(appointment), payload(key=request_key, card=500_000, discount=100_000))
    assert again.status_code == 302
    assert again.url == response.url
    assert Invoice.scoped(salon).count() == 1
    assert Payment.scoped(salon).filter(invoice=invoice).count() == 1


@pytest.mark.django_db
def test_reception_can_issue_credit_invoice_without_new_receipt(
    client, salon, owner_membership, day_case,
):
    _, _, _, appointment, day = day_case
    from apps.appointments.services.confirmation import confirm_pending_appointment
    confirm_pending_appointment(salon=salon, appointment_id=appointment.pk)
    complete_appointment(salon=salon, appointment_id=appointment.pk)
    sign_in(client, owner_membership)
    posted = client.post(issue_url(appointment), payload(print_now=False))
    assert posted.status_code == 302
    invoice = Invoice.scoped(salon).get()
    assert posted.url == reverse("finance:invoice_detail", args=[invoice.pk])
    assert invoice.received_toman == 0
    assert invoice.balance_at_issue_toman == 800_000
    assert Payment.scoped(salon).filter(invoice=invoice).count() == 0


@pytest.mark.django_db
def test_reception_rejects_pending_and_excess_payment_before_any_write(
    client, salon, owner_membership, day_case,
):
    _, _, _, appointment, day = day_case
    sign_in(client, owner_membership)
    assert client.get(issue_url(appointment)).status_code == 405
    not_completed = client.post(issue_url(appointment), payload(cash=1_000))
    assert not_completed.status_code == 302
    assert Invoice.scoped(salon).count() == 0

    from apps.appointments.services.confirmation import confirm_pending_appointment
    confirm_pending_appointment(salon=salon, appointment_id=appointment.pk)
    complete_appointment(salon=salon, appointment_id=appointment.pk)
    overpaid = client.post(issue_url(appointment), payload(cash=900_000))
    assert overpaid.status_code == 302
    assert "checkout" in overpaid.url
    assert Invoice.scoped(salon).count() == 0
    invalid = client.post(issue_url(appointment), payload(cash=-1))
    assert invalid.status_code == 302
    assert Invoice.scoped(salon).count() == 0


@pytest.mark.django_db
def test_reception_cannot_double_invoice_package_covered_visit(
    client, salon, owner_membership, day_case,
):
    customer, _, _, appointment, day = day_case
    from apps.appointments.services.confirmation import confirm_pending_appointment
    confirm_pending_appointment(salon=salon, appointment_id=appointment.pk)
    complete_appointment(salon=salon, appointment_id=appointment.pk)
    pkg = ServicePackage.objects.create(salon=salon, name="پکیج پوست", price_toman=800_000, session_count=2)
    purchase = CustomerPackage.objects.create(
        salon=salon, customer=customer, package=pkg,
        sessions_total=2, price_paid_toman=800_000,
        expires_at=appointment.start_at + timedelta(days=10),
    )
    PackageSessionUse.objects.create(
        salon=salon, customer_package=purchase, appointment=appointment,
    )
    sign_in(client, owner_membership)
    desk = client.get(reverse("reception:desk"), {"day": day.isoformat()})
    assert desk.context["day_operations"][0]["can_checkout"] is False
    assert "صدور فاکتور و چاپ برای" not in desk.content.decode()
    assert client.post(issue_url(appointment), payload()).status_code == 302
    assert not Invoice.scoped(salon).exists()


@pytest.mark.django_db
def test_reception_invoice_is_tenant_scoped_role_protected_and_csrf_checked(
    salon, salon_b, owner_membership, day_case,
):
    _, _, _, appointment, _ = day_case
    foreign_client = Client()
    foreign_user = User.objects.create_user(phone="+989121172224", full_name="مالک دیگر")
    foreign_member = SalonMembership.objects.create(
        salon=salon_b, user=foreign_user, role=SalonMembership.Role.OWNER,
    )
    sign_in(foreign_client, foreign_member)
    assert foreign_client.post(issue_url(appointment), payload()).status_code == 404

    specialist_client = Client()
    specialist = User.objects.create_user(phone="+989121172225", full_name="متخصص")
    specialist_member = SalonMembership.objects.create(
        salon=salon, user=specialist, role=SalonMembership.Role.SPECIALIST,
    )
    sign_in(specialist_client, specialist_member)
    assert specialist_client.post(issue_url(appointment), payload()).status_code == 403

    strict = Client(enforce_csrf_checks=True)
    sign_in(strict, owner_membership)
    assert strict.post(issue_url(appointment), payload()).status_code == 403
    assert not Invoice.scoped(salon).exists()


@pytest.mark.django_db
def test_other_salon_invoice_cannot_be_printed_by_reception(
    client, salon, salon_b, owner_membership, day_case,
):
    _, _, _, appointment, _ = day_case
    other_customer = Customer.objects.create(
        salon=salon_b, full_name="مشتری سالن دیگر", phone="+989121172226",
    )
    invoice = Invoice.objects.create(
        salon=salon_b, customer=other_customer, customer_name=other_customer.full_name,
        request_key=uuid4(), request_digest="not-an-issue-result", gross_toman=0,
    )
    sign_in(client, owner_membership)
    url = reverse("finance:invoice_detail", args=[invoice.pk]) + "?print=1"
    assert client.get(url).status_code == 404
