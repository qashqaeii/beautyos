from datetime import timedelta
from uuid import uuid4
import pytest
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.customers.models import Customer
from apps.expenses.models import Expense
from apps.finance.models import Payment
from apps.finance.ledger import refund_payment
from apps.finance.checkout import issue_invoice
from apps.services.models import Service
from apps.staff.models import StaffProfile
from apps.salons.models import SalonMembership

@pytest.mark.django_db
def test_refund_reopens_appointment_and_later_receipt_links_invoice(client,salon,owner_membership):
    actor=owner_membership.user
    customer=Customer.objects.create(salon=salon,full_name="تست",phone="+989121239981")
    staff,_=StaffProfile.objects.get_or_create(salon=salon,membership=owner_membership)
    service=Service.objects.create(salon=salon,name="خدمت",price_toman=100000)
    now=timezone.now()
    appt=Appointment.objects.create(salon=salon,customer=customer,staff=staff,service=service,
        start_at=now,end_at=now+timedelta(minutes=30),status=Appointment.Status.COMPLETED,completed_at=now,price_toman=100000)
    invoice=issue_invoice(salon=salon,customer_id=customer.pk,appointment_ids=[appt.pk],
        request_key=uuid4(),discount=0,amounts={"cash":100000,"card":0,"transfer":0},actor=actor)
    payment=invoice.payments.get()
    refund_payment(salon=salon,payment_id=payment.pk,amount=20000,reason="اصلاح دریافت",request_key=uuid4(),actor=actor)
    from apps.dashboard.role_services import appointment_payment_summary
    assert appointment_payment_summary(appt)["owed_toman"]==20000
    client.force_login(actor)
    response=client.post(reverse("finance:payment_create"),{"customer":customer.pk,"appointment":appt.pk,
        "total_amount_toman":20000,"discount_toman":0,"paid_amount_toman":20000,"method":"card","status":"paid"})
    assert response.status_code==302
    assert invoice.payments.count()==2
    assert appointment_payment_summary(appt)["owed_toman"]==0
    Expense.objects.create(salon=salon,category=Expense.Category.INVENTORY_PURCHASE,amount_toman=50000,expense_date=timezone.localdate())
    page=client.get(reverse("finance:overview"))
    data=page.context["dashboard"]
    assert data["received"]==120000 and data["net_received"]==100000
    assert data["inventory_purchases"]==50000 and data["general_expenses"]==0
    assert data["operating_estimate"]==data["total_earned"]-data["specialist_cost"]-data["other_cost"]
    report=client.get(reverse("finance:export_report"))
    assert report.status_code==200 and report.content.startswith(b"\xef\xbb\xbf")

@pytest.mark.django_db
def test_reception_staff_cannot_access_private_reports(client,salon):
    user=User.objects.create_user(phone="+989121239982")
    SalonMembership.objects.create(salon=salon,user=user,role=SalonMembership.Role.RECEPTIONIST)
    client.force_login(user)
    for name in ("accounts","staff_finance","recurring","materials","export_report"):
        assert client.get(reverse("finance:"+name)).status_code==403
    assert client.get(reverse("finance:product_sales")).status_code==200
