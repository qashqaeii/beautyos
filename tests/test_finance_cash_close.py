import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer
from apps.finance.cash_close import close_cash_day
from apps.finance.models import CashClose, Payment


@pytest.mark.django_db
def test_close_is_scoped_idempotent_and_reports_late_receipts(client, owner_membership, salon, salon_b):
    customer=Customer.objects.create(salon=salon,full_name="مشتری",phone="+989121222991")
    other=Customer.objects.create(salon=salon_b,full_name="دیگر",phone="+989121222992")
    Payment.objects.create(salon=salon,customer=customer,paid_amount_toman=200000,method=Payment.Method.CASH)
    Payment.objects.create(salon=salon,customer=customer,paid_amount_toman=300000,method=Payment.Method.CARD)
    Payment.objects.create(salon=salon_b,customer=other,paid_amount_toman=900000,method=Payment.Method.CASH)
    params=dict(salon=salon,day=timezone.localdate(),opening=100000,other_in=10000,cash_out=50000,
        counted=260000,note="",actor=owner_membership.user)
    row=close_cash_day(**params)
    assert row.expected_toman==260000
    assert row.difference_toman==0
    assert row.card_received_toman==300000
    assert close_cash_day(**params).pk==row.pk
    with pytest.raises(ValidationError):
        close_cash_day(**{**params,"counted":270000})
    Payment.objects.create(salon=salon,customer=customer,paid_amount_toman=10000,method=Payment.Method.CASH)
    client.force_login(owner_membership.user)
    response=client.get(reverse("finance:cash_close"))
    assert response.status_code==200
    assert response.context["late_cash_delta"]==10000
    assert CashClose.scoped(salon).count()==1


@pytest.mark.django_db
def test_discrepancy_requires_note(salon,owner_membership):
    params=dict(salon=salon,day=timezone.localdate(),opening=100000,other_in=0,cash_out=0,
        counted=90000,note="",actor=owner_membership.user)
    with pytest.raises(ValidationError):
        close_cash_day(**params)
    assert close_cash_day(**{**params,"note":"اختلاف شمارش"}).difference_toman==-10000
