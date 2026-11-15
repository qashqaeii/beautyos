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
