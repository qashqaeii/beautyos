from datetime import timedelta
import jdatetime
import pytest
from django.urls import reverse
from django.utils import timezone
from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.retention.models import AutomationPolicy,AutomationMessage
from apps.retention.automation import prepare_automation
from apps.salons.models import SalonSettings
from apps.services.models import Service
from apps.staff.models import StaffProfile

@pytest.mark.django_db
def test_automation_idempotent_and_suppresses_stale_intents(client,salon,salon_b,owner_membership):
    now=timezone.now()
    jd=jdatetime.date.fromgregorian(date=timezone.localdate(now))
    # Use today's exact Jalali date to cover leap days as well.
    customer=Customer.objects.create(salon=salon,full_name="مشتری",phone="+989121230421",birth_date=jd.togregorian(),marketing_consent=True)
    foreign=Customer.objects.create(salon=salon_b,full_name="دیگر",phone="+989121230422",marketing_consent=True,birth_date=jd.togregorian())
    staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    service=Service.objects.create(salon=salon,name="خدمت",price_toman=100000)
    a=Appointment.objects.create(salon=salon,customer=customer,staff=staff,service=service,
        start_at=now+timedelta(hours=12),end_at=now+timedelta(hours=13),status=Appointment.Status.CONFIRMED)
    assert prepare_automation(salon,now)==0
    AutomationPolicy.objects.create(salon=salon,reminder_enabled=True,birthday_enabled=True)
    SalonSettings.objects.filter(salon=salon).update(sms_marketing_enabled=True,sms_transactional_enabled=True)
    assert prepare_automation(salon,now)==2
    assert prepare_automation(salon,now)==0
    assert not AutomationMessage.scoped(salon_b).exists()
    Customer.scoped(salon).filter(pk=customer.pk).update(marketing_consent=False)
    Appointment.scoped(salon).filter(pk=a.pk).update(status=Appointment.Status.CANCELLED)
    assert prepare_automation(salon,now)==0
    assert AutomationMessage.scoped(salon).filter(status="skipped").count()==2
    client.force_login(owner_membership.user)
    assert client.get(reverse("retention:automation")).status_code==200
    assert client.post(reverse("retention:automation"),{"action":"save","reminder_enabled":"on"}).status_code==302
    assert not AutomationPolicy.scoped(salon).get().birthday_enabled
