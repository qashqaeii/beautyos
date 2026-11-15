from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.customers.models import Customer, CustomerNote
from apps.finance.models import Payment
from apps.salons.models import SalonMembership
from apps.services.models import Service
from apps.staff.models import StaffProfile


@pytest.mark.django_db
def test_customer_detail_hides_finance_for_receptionist(client, salon, owner_membership):
    reception = User.objects.create_user(phone="+989121111111", full_name="پذیرش")
    SalonMembership.objects.create(user=reception, salon=salon, role=SalonMembership.Role.RECEPTIONIST)
    customer = Customer.objects.create(
        salon=salon,
        full_name="مشتری تست",
        phone="+989121222222",
        total_spent_toman=1_500_000,
    )
    client.force_login(reception)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("customers:detail", kwargs={"pk": customer.pk})
    response = client.get(url)
    assert response.status_code == 200
    body = response.content.decode()
    assert "مجموع خرید" not in body
    assert "پرداخت‌ها" not in body


@pytest.mark.django_db
def test_customer_detail_shows_finance_for_manager(client, salon, owner_membership):
    customer = Customer.objects.create(
        salon=salon,
        full_name="مشتری مالی",
        phone="+989121333333",
        total_spent_toman=2_000_000,
    )
    Payment.objects.create(
        salon=salon,
        customer=customer,
        paid_amount_toman=500_000,
        total_amount_toman=500_000,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("customers:detail", kwargs={"pk": customer.pk})
    response = client.get(url)
    body = response.content.decode()
    assert response.status_code == 200
    assert "مجموع خرید" in body
    assert "پرداخت‌ها" in body
    assert "سابقهٔ فعالیت" in body
    assert "Timeline" not in body


@pytest.mark.django_db
def test_customer_add_note_appears_on_detail(client, owner_membership, salon):
    customer = Customer.objects.create(salon=salon, full_name="یادداشت", phone="+989121444444")
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    note_url = reverse("customers:add_note", kwargs={"pk": customer.pk})
    client.post(note_url, {"body": "اولین یادداشت"})
    detail = client.get(reverse("customers:detail", kwargs={"pk": customer.pk}))
    assert "اولین یادداشت" in detail.content.decode()
    note = CustomerNote.objects.get(customer=customer)
    assert note.body == "اولین یادداشت"


@pytest.mark.django_db
def test_customer_detail_upcoming_appointment(client, owner_membership, salon):
    customer = Customer.objects.create(salon=salon, full_name="نوبت", phone="+989121555555")
    service = Service.objects.create(salon=salon, name="کوتاهی", duration_minutes=30, price_toman=200_000)
    membership = SalonMembership.objects.create(
        user=User.objects.create_user(phone="+989121555556", full_name="متخصص"),
        salon=salon,
        role=SalonMembership.Role.SPECIALIST,
    )
    staff = StaffProfile.objects.create(salon=salon, membership=membership, display_name="آرایشگر")
    start = timezone.now() + timedelta(days=2)
    Appointment.objects.create(
        salon=salon,
        customer=customer,
        staff=staff,
        service=service,
        start_at=start,
        end_at=start + timedelta(minutes=30),
        price_toman=200_000,
        status=Appointment.Status.CONFIRMED,
    )
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    response = client.get(reverse("customers:detail", kwargs={"pk": customer.pk}))
    body = response.content.decode()
    assert "نوبت‌های پیش‌رو" in body
    assert "کوتاهی" in body
    assert "آرایشگر" in body
