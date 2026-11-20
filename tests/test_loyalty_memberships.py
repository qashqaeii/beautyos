from datetime import timedelta
from uuid import uuid4
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.customers.models import Customer
from apps.loyalty.models import LoyaltyAccount,LoyaltyPolicy,MembershipCycle
from apps.loyalty.memberships import buy_membership
from apps.loyalty.insights import loyalty_insights
from apps.packages.models import CustomerPackage,ServicePackage

@pytest.mark.django_db
def test_membership_renewal_uses_package_ledger_once(client,salon,salon_b,owner_membership):
    actor=owner_membership.user
    customer=Customer.objects.create(salon=salon,full_name="عضو",phone="+989121238199")
    foreign=Customer.objects.create(salon=salon_b,full_name="دیگر",phone="+989121238198")
    package=ServicePackage.objects.create(salon=salon,name="ماهانه",price_toman=500000,session_count=4,validity_days=30)
    LoyaltyPolicy.objects.create(salon=salon,enabled=True,spend_per_point_toman=100000)
    args=dict(salon=salon,customer_id=customer.pk,package_id=package.pk,request_key=uuid4(),actor=actor)
    first=buy_membership(**args)
    assert buy_membership(**args).pk==first.pk
    assert LoyaltyAccount.scoped(salon).get(customer=customer).points_balance==5
    with pytest.raises(ValidationError):buy_membership(**{**args,"request_key":uuid4(),"renewed_from_id":first.pk})
    with pytest.raises(ValidationError):buy_membership(**{**args,"request_key":uuid4(),"customer_id":foreign.pk})
    first.purchase.expires_at=timezone.now()-timedelta(days=1)
    first.purchase.save(update_fields=["expires_at"])
    second=buy_membership(**{**args,"request_key":uuid4(),"renewed_from_id":first.pk})
    assert second.renewed_from_id==first.pk
    assert CustomerPackage.scoped(salon).count()==2 and MembershipCycle.scoped(salon).count()==2
    assert LoyaltyAccount.scoped(salon).get(customer=customer).points_balance==10
    data=loyalty_insights(salon)
    assert data["total"]==1 and data["active_cycles"]==1
    assert sum(row["count"] for row in data["segments"])==1
    client.force_login(actor)
    for name in ("memberships","insights"):
        assert client.get(reverse("loyalty:"+name)).status_code==200
