from datetime import timedelta
from uuid import uuid4

import jdatetime
import pytest
from django.test import override_settings
from django.utils import timezone

from apps.customers.models import Customer
from apps.retention.automation import prepare_automation
from apps.retention.campaigns import create_campaign, prepare_campaign, schedule_campaign
from apps.retention.delivery import dispatch_due
from apps.retention.models import AutomationMessage, AutomationPolicy, Campaign
from apps.salons.models import SalonSettings


class FakeGateway:
    def __init__(self):
        self.calls = 0

    def send(self, row, phone):
        self.calls += 1
        return str(10000 + row.pk)


@pytest.mark.django_db
@override_settings(BEAUTYOS_AUTOMATION_SEND_ENABLED=True)
def test_opt_out_checked_on_delivery(salon):
    now = timezone.now()
    birthday = jdatetime.date.fromgregorian(date=timezone.localdate(now)).togregorian()
    customer = Customer.objects.create(salon=salon, full_name="مشتری",
        phone="+989121000001", birth_date=birthday, marketing_consent=True)
    AutomationPolicy.objects.create(salon=salon, birthday_enabled=True)
    SalonSettings.objects.filter(salon=salon).update(sms_marketing_enabled=True)
    assert prepare_automation(salon, now) == 1
    Customer.objects.filter(pk=customer.pk).update(marketing_consent=False)
    gateway = FakeGateway()
    assert dispatch_due(salon, now, transport=gateway)["accepted"] == 0
    assert gateway.calls == 0
    assert AutomationMessage.scoped(salon).get().status == "skipped"


@pytest.mark.django_db
@override_settings(BEAUTYOS_AUTOMATION_SEND_ENABLED=True)
def test_campaign_schedule_without_automation_policy(salon, owner_membership):
    Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121000002", marketing_consent=True)
    SalonSettings.objects.filter(salon=salon).update(sms_marketing_enabled=True)
    campaign = create_campaign(salon=salon, title="تست", segment=Campaign.Segment.NEW,
        message="سلام {name}", request_key=uuid4(), actor=owner_membership.user)
    prepare_campaign(salon=salon, campaign_id=campaign.pk, actor=owner_membership.user)
    when = timezone.now()
    schedule_campaign(salon=salon, campaign_id=campaign.pk, scheduled_at=when,
        actor=owner_membership.user)
    assert prepare_automation(salon, when+timedelta(seconds=5)) == 1
    assert prepare_automation(salon, when+timedelta(seconds=5)) == 0
    gateway = FakeGateway()
    assert dispatch_due(salon, when+timedelta(seconds=5), transport=gateway)["accepted"] == 1
    assert gateway.calls == 1



@pytest.mark.django_db
@override_settings(BEAUTYOS_AUTOMATION_SEND_ENABLED=True)
def test_daily_marketing_cap_and_tenant_isolation(salon, salon_b):
    now = timezone.now()
    birthday = jdatetime.date.fromgregorian(date=timezone.localdate(now)).togregorian()
    AutomationPolicy.objects.create(salon=salon, birthday_enabled=True, daily_marketing_cap=1)
    SalonSettings.objects.filter(salon=salon).update(sms_marketing_enabled=True)
    for idx in (1, 2):
        Customer.objects.create(
            salon=salon, full_name="مشتری", phone=f"+98912122000{idx}",
            birth_date=birthday, marketing_consent=True,
        )
    assert prepare_automation(salon, now) == 2
    gateway = FakeGateway()
    assert dispatch_due(salon, now, transport=gateway)["accepted"] == 1
    assert dispatch_due(salon, now, transport=gateway)["accepted"] == 0
    assert gateway.calls == 1
    assert AutomationMessage.scoped(salon).filter(status="pending").count() == 1
    assert not AutomationMessage.scoped(salon_b).exists()
