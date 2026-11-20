from datetime import timedelta
from uuid import uuid4

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.finance.checkout import issue_invoice, appointment_amounts
from apps.finance.models import Invoice, InvoiceLine, Payment
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.mark.django_db
def test_multi_service_checkout_idempotent_and_tenant_scoped(client, owner_membership, salon, salon_b):
    customer=Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121234990")
    staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    service=Service.objects.create(salon=salon,name="خدمت",price_toman=500000)
    now=timezone.now()
    appts=[]
    for i in range(2):
        start=now+timedelta(hours=i)
        appts.append(Appointment.objects.create(salon=salon,customer=customer,staff=staff,service=service,
            start_at=start,end_at=start+timedelta(minutes=30),completed_at=now,status=Appointment.Status.COMPLETED,price_toman=500000))
    Payment.objects.create(salon=salon,customer=customer,appointment=appts[0],total_amount_toman=500000,
        paid_amount_toman=100000,status=Payment.Status.PARTIAL)
    params=dict(salon=salon,customer_id=customer.pk,appointment_ids=[a.pk for a in appts],
        request_key=uuid4(),discount=100000,amounts={"cash":200000,"card":300000,"transfer":0},actor=owner_membership.user)
    invoice=issue_invoice(**params)
    assert invoice.gross_toman==1000000
    assert invoice.prior_paid_toman==100000
    assert invoice.received_toman==500000
    assert invoice.balance_at_issue_toman==300000
    assert sum(appointment_amounts(a)[3] for a in appts)==300000
    count=Payment.scoped(salon).count()
    assert issue_invoice(**params).pk==invoice.pk
    assert Payment.scoped(salon).count()==count
    with pytest.raises(ValidationError):
        issue_invoice(**{**params,"discount":200000})
    with pytest.raises(ValidationError):
        issue_invoice(**{**params,"request_key":uuid4()})
    assert InvoiceLine.scoped(salon).count()==2
    client.force_login(owner_membership.user)
    assert client.get(reverse("finance:checkout",args=[customer.pk])).status_code==200
    assert client.get(reverse("finance:invoice_detail",args=[invoice.pk])).status_code==200
    other=Customer.objects.create(salon=salon_b,full_name="دیگر",phone="+989121234991")
    assert client.get(reverse("finance:checkout",args=[other.pk])).status_code==404


@pytest.mark.django_db
def test_checkout_rejects_uncompleted_and_foreign_ids(salon,owner_membership):
    customer=Customer.objects.create(salon=salon,full_name="مشتری",phone="+989121234992")
    with pytest.raises(ValidationError):
        issue_invoice(salon=salon,customer_id=customer.pk,appointment_ids=[999999],request_key=uuid4(),
            discount=0,amounts={"cash":0,"card":0,"transfer":0},actor=owner_membership.user)
    assert not Invoice.scoped(salon).exists()
