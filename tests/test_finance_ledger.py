from uuid import uuid4
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.customers.models import Customer
from apps.finance.models import FinancialAccount, Payment, Refund, AccountMovement
from apps.finance.ledger import refund_payment, post_movement, account_balance

@pytest.mark.django_db
def test_refund_and_accounts(client, salon, salon_b, owner_membership):
    customer=Customer.objects.create(salon=salon,full_name="تست",phone="+989121233199")
    p=Payment.objects.create(salon=salon,customer=customer,paid_amount_toman=100000,method="cash")
    params=dict(salon=salon,payment_id=p.pk,amount=40000,reason="برگشت",request_key=uuid4(),actor=owner_membership.user)
    refund=refund_payment(**params)
    assert refund_payment(**params).pk==refund.pk
    with pytest.raises(ValidationError): refund_payment(**{**params,"request_key":uuid4(),"amount":70000})
    assert Refund.scoped(salon).count()==1
    customer.refresh_from_db()
    assert customer.total_spent_toman==60000
    today=timezone.localdate()
    cash=FinancialAccount.objects.create(salon=salon,name="صندوق",kind="cash",opening_day=today,opening_toman=50000)
    bank=FinancialAccount.objects.create(salon=salon,name="بانک",kind="bank",opening_day=today)
    other=FinancialAccount.objects.create(salon=salon_b,name="دیگر",kind="bank",opening_day=today)
    def post(**kw):
        return post_movement(salon=salon,actor=owner_membership.user,request_key=uuid4(),**kw)
    post(kind="payment",source_id=p.pk,to_id=cash.pk)
    post(kind="refund",source_id=refund.pk,from_id=cash.pk)
    post(kind="transfer",from_id=cash.pk,to_id=bank.pk,amount=60000)
    assert account_balance(cash)==50000 and account_balance(bank)==60000
    with pytest.raises(ValidationError): post(kind="payment",source_id=p.pk,to_id=cash.pk)
    with pytest.raises(ValidationError): post(kind="transfer",from_id=bank.pk,to_id=other.pk,amount=1)
    assert AccountMovement.scoped(salon).count()==3
    client.force_login(owner_membership.user)
    assert client.get(reverse("finance:accounts")).status_code==200
    assert client.get(reverse("finance:refund",args=[p.pk])).status_code==200
