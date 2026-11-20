from datetime import timedelta
from uuid import uuid4
import pytest
from django.urls import reverse
from django.utils import timezone
from apps.appointments.models import Appointment
from apps.appointments.services.lifecycle import complete_appointment, cancel_appointment
from apps.customers.models import Customer
from apps.finance.models import Payment
from apps.finance.ledger import refund_payment
from apps.loyalty.automation import award_payment
from apps.loyalty.models import LoyaltyAccount, LoyaltyAward, LoyaltyPolicy, ledger_add_points, ledger_redeem_points
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.mark.django_db
def test_payment_award_refund_after_redeeming(salon, salon_b, owner_membership):
    customer=Customer.objects.create(salon=salon,full_name="عضو",phone="+989121234471")
    payment=Payment.objects.create(salon=salon,customer=customer,paid_amount_toman=900000,status=Payment.Status.PAID,method="card")
    assert award_payment(payment) is None
    policy=LoyaltyPolicy.objects.create(salon=salon,enabled=True,spend_per_point_toman=100000)
    first=award_payment(payment)
    assert award_payment(payment).pk==first.pk
    ledger_redeem_points(salon=salon,customer=customer,points=8)
    policy.enabled=False
    policy.spend_per_point_toman=200000
    policy.save()
    args=dict(salon=salon,payment_id=payment.pk,amount=400000,reason="برگشت وجه",request_key=uuid4(),actor=owner_membership.user)
    row=refund_payment(**args)
    assert refund_payment(**args).pk==row.pk
    assert LoyaltyAccount.scoped(salon).get(customer=customer).points_balance==-3
    first.refresh_from_db()
    assert first.remaining_points==5
    with pytest.raises(ValueError):
        ledger_add_points(salon=salon_b,customer=customer,points=1)
    assert not LoyaltyAccount.scoped(salon_b).exists()


@pytest.mark.django_db
def test_visit_awards_and_policy_ui(client,salon,owner_membership):
    client.force_login(owner_membership.user)
    response=client.post(reverse("loyalty:program"),{"enabled":"on","spend_per_point_toman":"100,000","visit_points":4})
    assert response.status_code==302
    customer=Customer.objects.create(salon=salon,full_name="عضو",phone="+989121234472")
    staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    service=Service.objects.create(salon=salon,name="خدمت",price_toman=500000)
    now=timezone.now()
    a=Appointment.objects.create(salon=salon,customer=customer,staff=staff,service=service,start_at=now,end_at=now+timedelta(minutes=30),price_toman=500000,status=Appointment.Status.CONFIRMED)
    complete_appointment(salon=salon,appointment_id=a.pk)
    complete_appointment(salon=salon,appointment_id=a.pk)
    assert LoyaltyAward.scoped(salon).count()==1
    assert LoyaltyAccount.scoped(salon).get(customer=customer).points_balance==4
    cancel_appointment(salon=salon,appointment_id=a.pk)
    assert LoyaltyAccount.scoped(salon).get(customer=customer).points_balance==0
    assert client.get(reverse("loyalty:program")).status_code==200
    assert client.get(reverse("loyalty:overview")).status_code==200
