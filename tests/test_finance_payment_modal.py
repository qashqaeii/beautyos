import pytest
from django.urls import reverse

from apps.customers.models import Customer
from apps.finance.models import Payment


@pytest.mark.django_db
def test_finance_list_payment_query_opens_modal(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("finance:overview")
    response = client.get(f"{url}?range=today&payment=1")
    assert response.status_code == 200
    html = response.content.decode()
    assert "finance-payment-create-form" in html
    assert "luna-modal--extended" in html
    assert 'aria-describedby="finance-payment-modal-title-description"' in html
    assert "ثبت پرداخت مشتری" in html
    assert "paymentOpen: true" in html


@pytest.mark.django_db
def test_payment_create_get_redirects_to_finance_modal(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    overview = reverse("finance:overview")
    url = reverse("finance:payment_create")
    response = client.get(f"{url}?next={overview}%3Frange%3Dtoday")
    assert response.status_code == 302
    assert "payment=1" in response.url
    assert "range=today" in response.url


@pytest.mark.django_db
def test_payment_create_post_success(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    customer = Customer.objects.create(salon=salon, full_name="سارا", phone="+989121111199")
    url = reverse("finance:payment_create")
    overview = reverse("finance:overview")
    response = client.post(
        url,
        {
            "next": f"{overview}?range=today",
            "finance_tab": "income",
            "finance_range": "today",
            "customer": customer.pk,
            "total_amount_toman": "500000",
            "discount_toman": "0",
            "paid_amount_toman": "200000",
            "method": Payment.Method.CASH,
            "status": Payment.Status.PARTIAL,
            "notes": "",
        },
    )
    assert response.status_code == 302
    assert Payment.objects.filter(salon=salon, customer=customer).exists()


@pytest.mark.django_db
def test_invalid_payment_never_renders_reports_for_receptionist(client, salon):
    from apps.accounts.models import User
    from apps.salons.models import SalonMembership

    user = User.objects.create_user(phone="+989121277799")
    SalonMembership.objects.create(user=user, salon=salon, role=SalonMembership.Role.RECEPTIONIST)
    client.force_login(user)
    response = client.post(reverse("finance:payment_create"), {"next": reverse("finance:overview")})
    assert response.status_code == 200
    assert "finance/payment_modal_page.html" in [t.name for t in response.templates]
    assert "finance/overview.html" not in [t.name for t in response.templates]


@pytest.mark.django_db
def test_payment_form_validates_appointment_picker_without_sliced_queryset(salon, owner_membership):
    from datetime import timedelta
    from django.utils import timezone
    from apps.appointments.models import Appointment
    from apps.finance.forms import PaymentForm
    from apps.services.models import Service, ServiceCategory
    from apps.staff.models import StaffProfile

    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121277701")
    other = Customer.objects.create(salon=salon, full_name="مشتری دوم", phone="+989121277702")
    category = ServiceCategory.objects.create(salon=salon, name="تست پرداخت")
    service = Service.objects.create(salon=salon, category=category, name="خدمت", duration_minutes=30, price_toman=100000)
    staff, _ = StaffProfile.objects.get_or_create(salon=salon, membership=owner_membership)
    start = timezone.now()
    appointment = Appointment.objects.create(salon=salon, customer=customer, staff=staff, service=service,
        start_at=start, end_at=start + timedelta(minutes=30), price_toman=100000)
    data = {"customer": customer.pk, "appointment": appointment.pk, "total_amount_toman": 100000,
        "discount_toman": 0, "paid_amount_toman": 100000, "method": Payment.Method.CASH, "status": Payment.Status.PAID}
    assert PaymentForm(data, salon=salon).is_valid()
    form = PaymentForm({**data, "customer": other.pk}, salon=salon)
    assert not form.is_valid()
    assert "appointment" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("discount,paid,status", [(110,0,"pending"),(0,110,"paid"),(0,50,"paid"),(0,0,"partial"),(0,100,"refunded")])
def test_payment_rejects_inconsistent_amount_or_status(salon, discount, paid, status):
    from apps.finance.forms import PaymentForm
    customer = Customer.objects.create(salon=salon, full_name="مشتری", phone="+989121277733")
    form = PaymentForm({"customer":customer.pk, "total_amount_toman":100,
        "discount_toman":discount, "paid_amount_toman":paid,"method":"cash","status":status}, salon=salon)
    assert not form.is_valid()
