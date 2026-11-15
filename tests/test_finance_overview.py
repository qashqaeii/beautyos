from datetime import datetime, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.utils.dates import jalali_month_bounds, jalali_three_previous_months_bounds
from apps.customers.models import Customer
from apps.finance.models import Payment, SalonDebt
from apps.finance.services import income_metrics
from apps.dashboard.role_services import day_bounds


@pytest.mark.django_db
def test_income_metrics_deposit_and_settle_on_different_days(client, owner_membership, salon):
    customer = Customer.objects.create(salon=salon, full_name="زهرا", phone="+989121111100")
    yesterday = timezone.localdate() - timedelta(days=1)
    today = timezone.localdate()
    tz = timezone.get_current_timezone()

    p1 = Payment.objects.create(
        salon=salon,
        customer=customer,
        paid_amount_toman=100_000,
        status=Payment.Status.PARTIAL,
    )
    p2 = Payment.objects.create(
        salon=salon,
        customer=customer,
        paid_amount_toman=400_000,
        status=Payment.Status.PAID,
    )
    Payment.objects.filter(pk=p1.pk).update(
        created_at=timezone.make_aware(datetime.combine(yesterday, datetime.min.time()), tz)
    )
    Payment.objects.filter(pk=p2.pk).update(
        created_at=timezone.make_aware(datetime.combine(today, datetime.min.time()), tz)
    )

    start, end = day_bounds(today)
    metrics = income_metrics(salon, start, end)
    assert metrics["total_received"] == 400_000
    assert metrics["settled_customer_count"] == 1
    assert metrics["deposit_customer_count"] == 0


@pytest.mark.django_db
def test_salon_debt_partial_payment(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    debt = SalonDebt.objects.create(
        salon=salon,
        creditor_name="تامین‌کننده",
        creditor_type=SalonDebt.CreditorType.BRAND,
        principal_toman=1_000_000,
    )
    url = reverse("finance:overview") + "?tab=debts"
    response = client.post(
        url,
        {"action": "pay_debt", "debt_id": debt.pk, "amount_toman": 400_000},
    )
    assert response.status_code == 302
    debt.refresh_from_db()
    assert debt.balance_toman == 600_000
    assert debt.is_closed is False

    client.post(url, {"action": "pay_debt", "debt_id": debt.pk, "amount_toman": 600_000})
    debt.refresh_from_db()
    assert debt.is_closed is True
    assert debt.balance_toman == 0


@pytest.mark.django_db
def test_jalali_month_bounds():
    start, end = jalali_month_bounds()
    assert start <= end


@pytest.mark.django_db
def test_jalali_three_months_bounds():
    start, end = jalali_three_previous_months_bounds()
    assert start <= end
