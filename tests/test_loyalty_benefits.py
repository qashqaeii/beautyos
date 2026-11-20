from datetime import timedelta
from uuid import uuid4
import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import complete_appointment,cancel_appointment
from apps.customers.models import Customer
from apps.finance.checkout import issue_invoice
from apps.loyalty.benefits import register_referral
from apps.loyalty.models import LoyaltyAccount,LoyaltyPolicy,LoyaltyVoucher
from apps.services.models import Service
from apps.staff.models import StaffProfile

@pytest.mark.django_db
def test_referral_and_invoice_voucher(client,salon,salon_b,owner_membership):
    actor=owner_membership.user
    a=Customer.objects.create(salon=salon,full_name="معرف",phone="+989121239111")
    b=Customer.objects.create(salon=salon,full_name="جدید",phone="+989121239112")
    foreign=Customer.objects.create(salon=salon_b,full_name="دیگر",phone="+989121239113")
    staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    service=Service.objects.create(salon=salon,name="خدمت",price_toman=500000)
    now=timezone.now()
    def book(customer,h):
        start=now+timedelta(hours=h)
        return Appointment.objects.create(salon=salon,customer=customer,staff=staff,service=service,start_at=start,end_at=start+timedelta(minutes=30),status=Appointment.Status.CONFIRMED,price_toman=500000)
    complete_appointment(salon=salon,appointment_id=book(a,-2).pk)
    LoyaltyPolicy.objects.create(salon=salon,enabled=True,referral_points=25,spend_per_point_toman=100000)
    args=dict(salon=salon,referrer_id=a.pk,referred_id=b.pk,actor=actor)
    ref=register_referral(**args)
    assert register_referral(**args).pk==ref.pk
    with pytest.raises(ValidationError):register_referral(**{**args,"referred_id":foreign.pk})
    visit=book(b,-1)
    complete_appointment(salon=salon,appointment_id=visit.pk)
    assert LoyaltyAccount.scoped(salon).get(customer=a).points_balance==25
    voucher=LoyaltyVoucher.objects.create(salon=salon,customer=b,title="هدیه",amount_toman=100000,expires_on=timezone.localdate())
    data=dict(salon=salon,customer_id=b.pk,appointment_ids=[visit.pk],request_key=uuid4(),discount=0,amounts={"cash":0,"card":400000,"transfer":0},actor=actor,voucher_id=voucher.pk)
    invoice=issue_invoice(**data)
    assert issue_invoice(**data).pk==invoice.pk
    assert invoice.discount_toman==100000 and invoice.balance_at_issue_toman==0
    voucher.refresh_from_db()
    assert voucher.invoice_id==invoice.pk
    another=book(b,1)
    complete_appointment(salon=salon,appointment_id=another.pk)
    with pytest.raises(ValidationError):issue_invoice(**{**data,"appointment_ids":[another.pk],"request_key":uuid4()})
    cancel_appointment(salon=salon,appointment_id=visit.pk)
    assert LoyaltyAccount.scoped(salon).get(customer=a).points_balance==0
    client.force_login(actor)
    for name in ("referrals","vouchers"):
        assert client.get(reverse("loyalty:"+name)).status_code==200
