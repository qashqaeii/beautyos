from uuid import uuid4
import jdatetime
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.customers.models import Customer
from apps.loyalty.models import LoyaltyAccount, LoyaltyPolicy, LoyaltyReward, RewardRedemption, ledger_add_points
from apps.loyalty.rewards import claim_birthday, redeem_reward, change_redemption


@pytest.mark.django_db
def test_reward_redemption_fulfillment_and_cancel(client,salon,salon_b,owner_membership):
    actor=owner_membership.user
    customer=Customer.objects.create(salon=salon,full_name="مشتری",phone="+989121238876")
    ledger_add_points(salon=salon,customer=customer,points=100)
    account=LoyaltyAccount.scoped(salon).get(customer=customer)
    reward=LoyaltyReward.objects.create(salon=salon,title="هدیه",points_cost=60)
    other=LoyaltyReward.objects.create(salon=salon_b,title="هدیه دیگر",points_cost=1)
    args=dict(salon=salon,account_id=account.pk,reward_id=reward.pk,request_key=uuid4(),actor=actor)
    row=redeem_reward(**args)
    assert redeem_reward(**args).pk==row.pk
    account.refresh_from_db()
    assert account.points_balance==40
    with pytest.raises(ValidationError): redeem_reward(**{**args,"request_key":uuid4()})
    with pytest.raises(ValidationError): redeem_reward(**{**args,"request_key":uuid4(),"reward_id":other.pk})
    change_redemption(salon=salon,redemption_id=row.pk,status="cancelled",actor=actor)
    change_redemption(salon=salon,redemption_id=row.pk,status="cancelled",actor=actor)
    account.refresh_from_db()
    assert account.points_balance==100
    row2=redeem_reward(**{**args,"request_key":uuid4()})
    change_redemption(salon=salon,redemption_id=row2.pk,status="fulfilled",actor=actor)
    with pytest.raises(ValidationError): change_redemption(salon=salon,redemption_id=row2.pk,status="cancelled",actor=actor)
    assert RewardRedemption.scoped(salon).count()==2
    client.force_login(actor)
    assert client.get(reverse("loyalty:rewards")).status_code==200


@pytest.mark.django_db
def test_birthday_once_per_jalali_year(client,salon,owner_membership):
    today=jdatetime.date.fromgregorian(date=timezone.localdate())
    customer=Customer.objects.create(salon=salon,full_name="تولد",phone="+989121238877",birth_date=jdatetime.date(1370,today.month,1).togregorian())
    LoyaltyPolicy.objects.create(salon=salon,enabled=True,birthday_points=30)
    args=dict(salon=salon,customer=customer,actor=owner_membership.user)
    first=claim_birthday(**args)
    assert claim_birthday(**args).pk==first.pk
    assert LoyaltyAccount.scoped(salon).get(customer=customer).points_balance==30
    client.force_login(owner_membership.user)
    assert client.get(reverse("loyalty:birthdays")).status_code==200
