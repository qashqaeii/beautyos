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


@pytest.mark.django_db
def test_editorial_checkout_customer_picker_is_paginated_tenant_scoped_and_real(
    client, owner_membership, salon, salon_b,
):
    from django.contrib.staticfiles import finders

    for index in range(8):
        Customer.objects.create(
            salon=salon, full_name=f"مشتری خدمات {index}",
            phone=f"+989121780{index:04d}",
        )
    Customer.objects.create(
        salon=salon_b, full_name="مشتری سالن دیگر",
        phone="+989121799999",
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()

    url = reverse("finance:checkout_customers")
    first = client.get(url)
    assert first.status_code == 200
    html = first.content.decode()
    assert 'class="checkout-workspace checkout-workspace--search"' in html
    assert html.count('class="checkout-workspace__customer-row"') == 6
    assert first.context["customers_page"].paginator.count == 8
    assert "مشتری سالن دیگر" not in html
    assert "checkout-editorial.css" in html
    assert "فاکتورهای امروز" in html
    assert "از اعتماد شما سپاسگزاریم" in html
    assert "page=2" in html
    assert finders.find("css/checkout-editorial.css")

    second = client.get(url, {"page": "2"})
    assert second.status_code == 200
    assert len(second.context["customers"]) == 2
    filtered = client.get(url, {"q": "خدمات 3"})
    assert filtered.status_code == 200
    assert filtered.context["customers_page"].paginator.count == 1
    assert "مشتری خدمات 3" in filtered.content.decode()


@pytest.mark.django_db
def test_editorial_checkout_preserves_payment_fields_and_empty_state(
    client, owner_membership, salon,
):
    customer = Customer.objects.create(
        salon=salon, full_name="نگار امینی", phone="+989121780100",
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.get(reverse("finance:checkout", args=[customer.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "checkout-workspace--builder" in html
    assert "خدمت قابل صدور وجود ندارد" in html
    assert "ثبت فاکتور و پرداخت" in html
    assert 'name="request_key"' in html
    assert 'name="appointment"' not in html
    assert 'type="submit"' in html
    for key in ("discount", "cash", "card", "transfer"):
        assert f'name="{key}"' in html
    assert "از اعتماد شما سپاسگزاریم" in html


@pytest.mark.django_db
def test_editorial_invoice_detail_is_printable_and_keeps_issue_time_amounts(
    client, owner_membership, salon,
):
    customer = Customer.objects.create(
        salon=salon, full_name="مریم رضایی", phone="+989121780101",
    )
    staff, _ = StaffProfile.objects.get_or_create(
        salon=salon, membership=owner_membership,
    )
    service = Service.objects.create(
        salon=salon, name="مراقبت پوست", price_toman=760000,
    )
    now = timezone.now()
    appt = Appointment.objects.create(
        salon=salon, customer=customer, staff=staff, service=service,
        start_at=now - timedelta(days=1),
        end_at=now - timedelta(days=1) + timedelta(minutes=40),
        completed_at=now, status=Appointment.Status.COMPLETED,
        price_toman=760000,
    )
    invoice = issue_invoice(
        salon=salon, customer_id=customer.pk,
        appointment_ids=[appt.pk], request_key=uuid4(), discount=60000,
        amounts={"cash": 200000, "card": 0, "transfer": 0},
        actor=owner_membership.user,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.pk)
    session.save()
    response = client.get(reverse("finance:invoice_detail", args=[invoice.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "checkout-workspace--issued" in html
    assert "مانده هنگام صدور" not in html
    assert "مراقبت پوست" in html
    assert "مریم رضایی" in html
    assert "چاپ / ذخیره PDF" in html
    assert "window.print()" in html
    assert "از اعتماد شما سپاسگزاریم" in html
    assert "checkout-workspace__balance" not in html
    assert "مانده فعلی خدمات فعال" not in html
    invoice.refresh_from_db()
    assert invoice.gross_toman == 760000
    assert invoice.discount_toman == 60000
    assert invoice.received_toman == 200000
    assert invoice.balance_at_issue_toman == 500000
