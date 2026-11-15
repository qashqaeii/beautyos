import pytest
from django.urls import reverse

from apps.customers.models import Customer


@pytest.mark.django_db
def test_customer_list_view_toggle_preserves_search(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    Customer.objects.create(salon=salon, full_name="زهرا", phone="+989123456789")
    Customer.objects.create(salon=salon, full_name="مریم", phone="+989123456788")

    base = reverse("customers:list")
    response = client.get(f"{base}?q=زهرا&view=card")
    html = response.content.decode()
    assert "زهرا" in html
    assert "مریم" not in html

    response = client.get(f"{base}?q=زهرا&view=table")
    html = response.content.decode()
    assert "customers-list-table" in html
    assert "زهرا" in html
    assert "مریم" not in html


@pytest.mark.django_db
def test_customer_list_filter_empty_state(client, owner_membership, salon):
    client.force_login(owner_membership.user)
    session = client.session
    session["active_salon_id"] = str(salon.id)
    session.save()

    Customer.objects.create(salon=salon, full_name="علی", phone="+989111111111")
    response = client.get(reverse("customers:list"), {"q": "ناموجود"})
    assert response.status_code == 200
    assert "نتیجه‌ای یافت نشد" in response.content.decode()
