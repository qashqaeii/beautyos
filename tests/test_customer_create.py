import pytest
from django.urls import reverse
from django.utils import timezone

from apps.customers.models import Customer


@pytest.mark.django_db
def test_customer_create_minimal_fields(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("customers:create")
    get = client.get(url)
    assert get.status_code == 302
    assert "create=1" in get.url

    list_resp = client.get(reverse("customers:list"), {"create": "1"})
    html = list_resp.content.decode()
    assert 'name="email"' not in html
    assert 'name="status"' not in html
    assert 'name="tags"' not in html
    assert "customer-create-modal-title" in html

    response = client.post(
        url,
        {
            "full_name": "سارا احمدی",
            "phone_input": "09121234567",
        },
    )
    assert response.status_code == 302
    customer = Customer.objects.get(salon=salon, full_name="سارا احمدی")
    assert customer.phone.endswith("9121234567") or "9121234567" in customer.phone
    assert customer.status == Customer.Status.NEW
    assert customer.marketing_consent is False


@pytest.mark.django_db
def test_customer_create_phone_error_shows_under_field(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    url = reverse("customers:create")
    response = client.post(
        url,
        {
            "full_name": "علی",
            "phone_input": "123",
        },
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "موبایل معتبر نیست" in html
    assert "customer-create-modal-title" in html


@pytest.mark.django_db
def test_customer_create_rejects_future_birth_date(client, owner_membership, salon):
    from datetime import timedelta

    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
    url = reverse("customers:create")
    response = client.post(
        url,
        {
            "full_name": "نازنین",
            "phone_input": "09123334455",
            "birth_date": tomorrow,
        },
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "آینده" in html
    assert not Customer.objects.filter(salon=salon, full_name="نازنین").exists()
