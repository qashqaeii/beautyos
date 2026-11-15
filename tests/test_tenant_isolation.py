import pytest

from apps.accounts.models import User
from apps.customers.models import Customer


@pytest.mark.django_db
def test_customer_scoped_per_salon(salon, salon_b):
    Customer.objects.create(salon=salon, full_name="علی", phone="+989131111111")
    Customer.objects.create(salon=salon_b, full_name="رضا", phone="+989132222222")

    assert Customer.scoped(salon).count() == 1
    assert Customer.scoped(salon_b).count() == 1
    assert Customer.scoped(salon).first().full_name == "علی"


@pytest.mark.django_db
def test_dashboard_with_membership(client, user, owner_membership):
    client.force_login(user)
    response = client.get("/app/")
    assert response.status_code == 200


@pytest.mark.django_db
def test_dashboard_redirect_without_salon(client, user):
    client.force_login(user)
    response = client.get("/app/")
    assert response.status_code == 302
    assert "/onboarding/create/" in response.url
