from datetime import timedelta
from uuid import uuid4
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.customers.models import Customer
from apps.retention.models import FollowUp,Campaign,CampaignRecipient
from apps.retention.services import sync_follow_up_queue
from apps.retention.campaigns import create_campaign,prepare_campaign
from apps.salons.models import SalonSettings,SalonMembership
from apps.accounts.models import User

@pytest.mark.django_db
def test_followup_cycle_does_not_resurrect(salon):
    customer=Customer.objects.create(salon=salon,full_name="مشتری",phone="+989121277771")
    Customer.scoped(salon).filter(pk=customer.pk).update(created_at=timezone.now()-timedelta(days=95))
    assert sync_follow_up_queue(salon)==1
    assert sync_follow_up_queue(salon)==0
    row=FollowUp.scoped(salon).get()
    assert row.priority==FollowUp.Priority.HIGH
    row.status=FollowUp.Status.DONE
    row.save(update_fields=["status"])
    sync_follow_up_queue(salon)
    assert FollowUp.scoped(salon).count()==1
    assert not FollowUp.scoped(salon).filter(status="open").exists()

@pytest.mark.django_db
def test_campaign_consent_tenant_and_idempotency(client,salon,salon_b,owner_membership):
    actor=owner_membership.user
    for s,consent,phone in [(salon,True,"+989121277772"),(salon,False,"+989121277773"),(salon_b,True,"+989121277774")]:
        Customer.objects.create(salon=s,full_name="مشتری",phone=phone,marketing_consent=consent)
    args=dict(salon=salon,title="بازگشت",segment=Campaign.Segment.NEW,message="{name} عزیز، {salon}",request_key=uuid4(),actor=actor)
    row=create_campaign(**args)
    assert create_campaign(**args).pk==row.pk
    with pytest.raises(ValidationError):prepare_campaign(salon=salon,campaign_id=row.pk,actor=actor)
    SalonSettings.objects.filter(salon=salon).update(sms_marketing_enabled=True)
    assert prepare_campaign(salon=salon,campaign_id=row.pk,actor=actor).status=="prepared"
    prepare_campaign(salon=salon,campaign_id=row.pk,actor=actor)
    target=CampaignRecipient.scoped(salon).get()
    assert target.customer.marketing_consent and target.message_snapshot=="مشتری عزیز، "+salon.name
    with pytest.raises(ValidationError):prepare_campaign(salon=salon_b,campaign_id=row.pk,actor=actor)
    client.force_login(actor)
    assert client.get(reverse("retention:campaigns")).status_code==200
    assert client.get(reverse("retention:campaign_detail",args=[row.pk])).status_code==200
    user=User.objects.create_user(phone="+989121277775")
    SalonMembership.objects.create(salon=salon,user=user,role=SalonMembership.Role.RECEPTIONIST)
    client.force_login(user)
    assert client.get(reverse("retention:campaigns")).status_code==403
