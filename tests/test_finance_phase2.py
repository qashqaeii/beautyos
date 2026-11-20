from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.commissions.models import CommissionEntry
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.mark.django_db
def test_dashboard_distinguishes_earned_receipts_and_expense(client, owner_membership, salon, salon_b):
    now = timezone.now()
    customer = Customer.objects.create(salon=salon, full_name="مشتری تست", phone="+989121232343")
    other = Customer.objects.create(salon=salon_b, full_name="مشتری دیگر", phone="+989121232344")
    staff, _ = StaffProfile.objects.get_or_create(salon=salon, membership=owner_membership)
    service = Service.objects.create(salon=salon, name="خدمت", price_toman=1000000)
    appt = Appointment.objects.create(salon=salon, customer=customer, service=service, staff=staff,
        start_at=now, end_at=now+timedelta(minutes=30), completed_at=now,
        status=Appointment.Status.COMPLETED, price_toman=1000000)
    payment = Payment.objects.create(salon=salon, customer=customer, appointment=appt, total_amount_toman=1000000,
        discount_toman=100000, paid_amount_toman=400000, status=Payment.Status.PARTIAL, method=Payment.Method.CARD)
    Payment.objects.create(salon=salon_b, customer=other, paid_amount_toman=900000)
    Expense.objects.create(salon=salon, amount_toman=100000, expense_date=timezone.localdate())
    CommissionEntry.objects.update_or_create(salon=salon, appointment=appt, defaults={
        "staff":staff,"base_amount_toman":1000000,"commission_amount_toman":300000})
    client.force_login(owner_membership.user)
    page = client.get(reverse("finance:overview"))
    assert page.status_code == 200
    data=page.context["dashboard"]
    assert data["earned"] == 900000
    assert data["received"] == 400000
    assert data["commission"] == 300000
    assert data["operating_estimate"] == 500000
    assert data["receivable_total"] == 500000
    receipt = client.get(reverse("finance:receipt", args=[payment.pk]))
    assert receipt.status_code == 200
    hidden = Payment.objects.filter(salon=salon_b).first()
    assert client.get(reverse("finance:receipt", args=[hidden.pk])).status_code == 404


@pytest.mark.django_db
def test_dashboard_tabs_and_empty_state(client, owner_membership):
    client.force_login(owner_membership.user)
    for tab in ("income","cash","receipts","debts","reports","commissions"):
        response=client.get(reverse("finance:overview"), {"tab":tab})
        assert response.status_code == 200
        assert response.context["tab"] == tab
    response=client.get(reverse("finance:overview"))
    assert response.context["dashboard"]["operating_estimate"] == 0
    assert not response.context["dashboard"]["chart"]["has_data"]
